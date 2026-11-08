"""OBS-002: simula semanas de produção com drift crescente e registra cada uma no MLflow.

O que faz: divide a Produção-base em 4 lotes semanais disjuntos de 2.000 clientes, aplica drift
crescente (0, 1/3, 2/3 e cheio, de data drift e de concept drift juntos), acrescenta uma semana com
lote corrompido e passa cada lote pelo pipeline: contrato, relatório de drift, réguas de alerta.
Cada semana vira um evento em logs/pipeline.jsonl e um run do MLflow com o mesmo run_id.
Por que existe: um painel de monitoramento só faz sentido como série no tempo; é ela que mostra o
modelo degradando aos poucos, e é ela que aparece no vídeo.
Onde entra no fluxo: depois de train_baseline.py e calibrate_alerts.py.

Uso:
    uv run python scripts/run_weekly_pipeline.py
    uv run mlflow ui --backend-store-uri sqlite:///mlflow.db   # abre o painel em localhost:5000

Saídas: outputs/weekly/semana_<N>/ (fora do git), mlflow.db e mlartifacts/ (fora do git).
Exit code (o número que o programa devolve ao terminar): 0 = todas as semanas registradas, mesmo
as barradas ou com alerta, porque registrar é o trabalho deste script; 1 = faltam os limites.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import sklearn

from credit_risk_observability.config import (
    ALERT_THRESHOLDS_PATH,
    MODEL_PATH,
    PRODUCTION_BASE_PATH,
    REFERENCE_PATH,
    SEED,
    TARGET,
    WEEKLY_BATCH_SIZE,
    WEEKLY_RUNS_DIR,
)
from credit_risk_observability.contracts.corrupt import inject_defects
from credit_risk_observability.contracts.schema import SCHEMA
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.drift.detect import (
    add_section_to_html,
    analyze_batch,
    render_summary_section,
)
from credit_risk_observability.drift.scenarios import apply_concept_drift, apply_data_drift
from credit_risk_observability.model.predict import load_model
from credit_risk_observability.monitoring import events
from credit_risk_observability.monitoring.alerts import (
    AlertThresholds,
    evaluate_alerts,
    ks_by_feature,
)
from credit_risk_observability.monitoring.events import new_run_id, pipeline_step
from credit_risk_observability.monitoring.tracking import (
    PipelineRun,
    log_pipeline_run,
    setup_tracking,
)

logger = logging.getLogger("run_weekly_pipeline")

# Intensidade do drift em cada semana: 0 é o controle, 1 é o cenário cheio do DRIFT-001.
WEEK_INTENSITIES = (0.0, 0.33, 0.67, 1.0)
DRIFT_METHOD = "PSI (Evidently, limite 0,25) + KS (scipy, Bonferroni) + bootstrap de AUC e default"


@dataclass
class Week:
    """Um lote semanal e como ele foi gerado."""

    number: int
    name: str
    batch: pd.DataFrame
    intensity: float | None  # None na semana corrompida: ali não há drift, há dado sujo
    labels_flipped: int = 0


def build_weeks(base: pd.DataFrame, batch_size: int, seed: int) -> list[Week]:
    """Monta as semanas: 4 com drift crescente e 1 com lote corrompido.

    Recebe: a Produção-base, o tamanho do lote e a seed.
    Faz: embaralha a Produção-base uma vez e fatia em lotes disjuntos, para nenhum cliente aparecer
        em duas semanas. Em cada lote aplica primeiro o concept drift (troca rótulos) e depois o
        data drift (muda entradas): um mexe no y, o outro no X, e a ordem não interfere.
        A semana corrompida usa o que sobra da Produção-base, com os defeitos do DQ-002.
    Devolve: a lista de semanas. Exemplo: 9.000 clientes e lotes de 2.000 dão 4 semanas e sobram
        1.000 para a corrompida.
    """
    shuffled = base.sample(frac=1, random_state=seed).reset_index(drop=True)
    needed = batch_size * len(WEEK_INTENSITIES)
    if len(shuffled) <= needed:
        raise ValueError(f"Produção-base com {len(shuffled)} linhas: precisa de mais de {needed}")

    weeks = []
    for number, intensity in enumerate(WEEK_INTENSITIES, start=1):
        chunk = shuffled.iloc[(number - 1) * batch_size : number * batch_size].reset_index(
            drop=True
        )
        batch, concept = apply_concept_drift(chunk, intensity, seed)
        batch, _ = apply_data_drift(batch, intensity)
        weeks.append(Week(number, f"semana_{number}", batch, intensity, concept["labels_flipped"]))

    leftover = shuffled.iloc[needed:].reset_index(drop=True)
    corrupted, _ = inject_defects(leftover, batch_size=len(leftover), seed=seed)
    number = len(WEEK_INTENSITIES) + 1
    weeks.append(Week(number, f"semana_{number}_corrompida", corrupted, None))
    return weeks


def _file_sha256(path: Path) -> str:
    """Impressão digital do arquivo do modelo: identifica a versão sem depender do nome."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_week(
    week: Week,
    reference: pd.DataFrame,
    model,
    model_version: str,
    thresholds: AlertThresholds,
    output_dir: Path,
) -> PipelineRun:
    """Passa uma semana pelo pipeline e monta o que vai para o MLflow.

    Recebe: a semana, a Referência, o modelo, a versão do modelo, os limites e a pasta de saída.
    Faz: etapa 1, contrato (lote barrado para aqui, com as falhas salvas); etapa 2, relatório de
        drift e réguas de alerta. As duas etapas gravam no log com o mesmo run_id.
    Devolve: o PipelineRun da semana, ainda não gravado.
    """
    run_id = new_run_id()
    week_dir = output_dir / week.name
    week_dir.mkdir(parents=True, exist_ok=True)
    run = PipelineRun(
        name=week.name,
        run_id=run_id,
        step=week.number,
        params={
            "lote": week.name,
            "semana": week.number,
            "intensidade_drift": week.intensity,
            "tamanho_lote": len(week.batch),
            "modelo_sha256": model_version[:12],
            "scikit_learn": sklearn.__version__,
            "contrato": SCHEMA.name,
            "metodo_drift": DRIFT_METHOD,
            "limites_calibrados_para_n": thresholds.batch_size,
        },
    )

    with pipeline_step(logger, "validacao", run_id=run_id) as step:
        step.detalhe["lote"] = week.name
        validation = validate_batch(week.batch)
        step.linhas_entrada = validation.rows
        step.linhas_rejeitadas = validation.rejected_rows
        if validation.passed:
            step.succeed("validation_passed")
        else:
            # Para o MLflow vai só regra e posição (ADR-005); o detalhe fica na pasta local.
            cases_path = week_dir / "falhas_contrato.csv"
            validation.minimized_failures.to_csv(cases_path, index=False)
            validation.failure_cases.to_csv(week_dir / "failure_cases.csv", index=False)
            run.artifacts.append(cases_path)
            step.fail(
                "validation_failed",
                motivo=f"{len(validation.failures_by_rule)} regras do contrato violadas",
                falhas_por_regra=validation.failures_by_rule,
            )
    run.metrics.update(
        duracao_validacao_s=step_duration(run_id, "validacao"),
        linhas_entrada=validation.rows,
        linhas_rejeitadas=validation.rejected_rows,
    )
    run.tags.update(status="falha" if not validation.passed else "sucesso")

    if validation.passed:
        _run_drift_step(week, reference, model, thresholds, week_dir, run)

    run.artifacts.append(_export_events(run_id, week_dir))
    return run


def _run_drift_step(
    week: Week,
    reference: pd.DataFrame,
    model,
    thresholds: AlertThresholds,
    week_dir: Path,
    run: PipelineRun,
) -> None:
    """Etapa 2: relatório de drift e réguas de alerta. Preenche métricas, tags e artefatos."""
    with pipeline_step(logger, "relatorio_drift", run_id=run.run_id) as step:
        step.detalhe["lote"] = week.name
        step.linhas_entrada = len(week.batch)
        snapshot, analysis = analyze_batch(reference, week.batch, model)
        ks = ks_by_feature(reference, week.batch)
        psi = {f: v["psi"] for f, v in analysis["feature_drift"]["features"].items()}
        auc = analysis["performance"]["roc_auc"]
        default_rate = float(week.batch[TARGET].mean())
        alerts = evaluate_alerts(thresholds, psi, ks, auc, default_rate)

        summary = {"run_id": run.run_id, "batch": week.name, **analysis, "alertas": alerts}
        html_path = week_dir / "drift_report.html"
        summary_path = week_dir / "drift_report.json"
        html = snapshot.get_html_str(as_iframe=False)
        html_path.write_text(
            add_section_to_html(html, render_summary_section(summary)), encoding="utf-8"
        )
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        step.succeed(
            "drift_report_generated",
            alertas=[rule for rule in ("psi", "ks", "auc", "taxa_default") if alerts[rule]],
            roc_auc=auc,
        )

    run.artifacts += [html_path, summary_path]
    run.metrics.update(
        duracao_drift_s=step_duration(run.run_id, "relatorio_drift"),
        roc_auc=auc,
        taxa_default=default_rate,
        n_features_psi=len(alerts["psi"]),
        n_features_ks=len(alerts["ks"]),
        psi_max=max(psi.values()),
        rotulos_trocados=week.labels_flipped,
        **{f"psi_{feature}": value for feature, value in psi.items()},
    )
    run.tags.update(
        drift_alert=alerts["drift_alert"],
        alerta_ks=bool(alerts["ks"]),
        alerta_auc=alerts["auc"],
        alerta_taxa_default=alerts["taxa_default"],
        algum_alerta=alerts["algum_alerta"],
        diagnostico=analysis["diagnosis"]["text"],
    )


def _read_events(run_id: str) -> list[dict]:
    """Os eventos do log desta execução, na ordem em que foram gravados."""
    lines = events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()
    return [e for e in map(json.loads, lines) if e["run_id"] == run_id]


def step_duration(run_id: str, etapa: str) -> float | None:
    """Lê a duração de uma etapa no próprio log: a mesma fonte para o arquivo e para o MLflow."""
    found = [e["duracao_s"] for e in _read_events(run_id) if e["etapa"] == etapa]
    return found[-1] if found else None


def _export_events(run_id: str, week_dir: Path) -> Path:
    """Copia para a pasta da semana só as linhas do log desta execução, para anexar ao run."""
    path = week_dir / "eventos.jsonl"
    lines = [json.dumps(e, ensure_ascii=False) for e in _read_events(run_id)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(
    argv: list[str] | None = None,
    thresholds_path: Path = ALERT_THRESHOLDS_PATH,
    output_dir: Path = WEEKLY_RUNS_DIR,
    reference_path: Path = REFERENCE_PATH,
    base_path: Path = PRODUCTION_BASE_PATH,
    model_path: Path = MODEL_PATH,
    tracking_uri: str | None = None,
) -> int:
    """Roda todas as semanas e registra cada uma.

    Recebe: os argumentos e os caminhos (os testes passam pastas e banco temporários).
    Faz: lê os limites calibrados, monta as semanas e passa cada uma pelo pipeline.
    Devolve: o exit code.
    """
    parser = argparse.ArgumentParser(description="Simula semanas de produção (OBS-002)")
    parser.add_argument("--batch-size", type=int, default=WEEKLY_BATCH_SIZE)
    args = parser.parse_args(argv)

    if not thresholds_path.exists():
        print(f"Faltam os limites ({thresholds_path.name}): rode calibrate_alerts.py antes.")
        return 1
    thresholds = AlertThresholds.from_json(thresholds_path)
    if thresholds.batch_size != args.batch_size:
        # Régua de um tamanho aplicada a outro é exatamente o erro que este card corrige.
        raise ValueError(
            f"Limites calibrados para {thresholds.batch_size} linhas, lote de {args.batch_size}"
        )

    reference = pd.read_parquet(reference_path)
    model = load_model(model_path)
    model_version = _file_sha256(model_path)
    weeks = build_weeks(pd.read_parquet(base_path), args.batch_size, SEED)
    if tracking_uri is None:
        setup_tracking()
    else:
        setup_tracking(tracking_uri=tracking_uri, artifacts_dir=output_dir / "mlartifacts")

    for week in weeks:
        run = run_week(week, reference, model, model_version, thresholds, output_dir)
        log_pipeline_run(run)
        auc = run.metrics.get("roc_auc")
        print(
            f"{week.name}: {run.tags['status']}, "
            f"AUC {auc if auc is None else round(auc, 4)}, "
            f"taxa de default {np.round(run.metrics.get('taxa_default', np.nan), 4)}, "
            f"PSI máx {np.round(run.metrics.get('psi_max', np.nan), 3)}, "
            f"alertas: drift={run.tags.get('drift_alert')}, ks={run.tags.get('alerta_ks')}, "
            f"auc={run.tags.get('alerta_auc')}, default={run.tags.get('alerta_taxa_default')}"
        )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    sys.exit(main())
