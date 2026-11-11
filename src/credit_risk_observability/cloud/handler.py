"""AWS-002 e AWS-003: o pipeline como função Lambda.

O que faz: recebe um lote pelo S3 (ou pelo agendamento semanal), passa pelo contrato, pelo modelo,
pelo relatório de drift e pelas réguas de alerta, grava os relatórios no S3 e publica as métricas.
Por que existe: é o mesmo fluxo de scripts/run_weekly_pipeline.py, em ferramentas de mercado (ADR-007).
Onde entra no fluxo: é o ponto de entrada da imagem de contêiner; a infra está em infra/.

Termos usados aqui:
- Lambda: serviço que roda uma função sob demanda e cobra só pelo tempo de execução.
- EMF (Embedded Metric Format): uma linha JSON no log que o CloudWatch transforma em métrica.
- Contrato reprovado não é erro da função: ela termina bem e publica a métrica que dispara o alarme.
  Erro de verdade (arquivo faltando, lote de tamanho sem régua) levanta exceção.
"""

import json
import logging
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import unquote_plus

METRICS_NAMESPACE = "CreditRisk/Pipeline"
PIPELINE_NAME = "credit-risk-observability"

# O gatilho só observa incoming/, e os relatórios vão para reports/: prefixos separados impedem
# que a função grave um arquivo que a dispara de novo.
INCOMING_PREFIX = "incoming/"
REPORTS_PREFIX = "reports/"
REFERENCE_KEY = "seed/reference.parquet"
MODEL_KEY = "seed/baseline_logreg.joblib"
THRESHOLDS_KEY = "seed/alert_thresholds.json"
CONTROL_KEY = "seed/controle.parquet"

# No Lambda, só /tmp aceita escrita; o resto do sistema de arquivos é somente leitura.
WORK_ROOT = Path("/tmp/pipeline")

_METRIC_UNITS = {
    "LotesProcessados": "Count",
    "LotesReprovados": "Count",
    "LinhasEntrada": "Count",
    "LinhasRejeitadas": "Count",
    "FeaturesComDrift": "Count",
    "AlertasDrift": "Count",
    "AUC": "None",
    "TaxaDefault": "None",
}


def build_logger() -> logging.Logger:
    """Cria o logger que escreve JSON puro na saída padrão.

    Recebe: nada.
    Faz: usa um formato só com a mensagem e não repassa ao logger raiz. O logger raiz do Lambda
        acrescenta data e identificador antes do texto, e aí o Logs Insights não leria os campos.
    Devolve: o logger. Chamar de novo não duplica o handler, porque ele é trocado.
    """
    logger = logging.getLogger("cloud_pipeline")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Sempre um handler novo: sys.stdout pode ter sido trocado entre execuções (nos testes, é).
    logger.handlers = [logging.StreamHandler(sys.stdout)]
    logger.handlers[0].setFormatter(logging.Formatter("%(message)s"))
    return logger


def build_emf_line(metrics: dict[str, float], extra_fields: dict) -> str:
    """Monta a linha EMF que o CloudWatch transforma em métricas.

    Recebe: as métricas e os campos que acompanham a linha (como o run_id).
    Faz: declara o namespace, a dimensão e as unidades no bloco _aws, e põe os valores na raiz.
    Devolve: o JSON em uma linha. Exemplo: {"_aws": {...}, "Pipeline": "...", "AUC": 0.71}.
    """
    directive = {
        "Namespace": METRICS_NAMESPACE,
        "Dimensions": [["Pipeline"]],
        "Metrics": [{"Name": name, "Unit": _METRIC_UNITS[name]} for name in metrics],
    }
    document = {
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [directive]},
        "Pipeline": PIPELINE_NAME,
        **extra_fields,
        **metrics,
    }
    return json.dumps(document, ensure_ascii=False)


def resolve_batch_keys(event: dict) -> list[str]:
    """Descobre quais lotes este evento pede para processar.

    Recebe: o evento do Lambda.
    Faz: num evento do S3, decodifica a chave, porque o S3 troca espaço por "+", e ignora o que
        estiver fora de incoming/. Sem "Records", é o agendamento: processa o lote de controle.
    Devolve: a lista de chaves. Exemplo: "incoming/a+b.parquet" vira ["incoming/a b.parquet"].
    """
    if "Records" not in event:
        return [CONTROL_KEY]
    keys = [unquote_plus(record["s3"]["object"]["key"]) for record in event["Records"]]
    return [key for key in keys if key.startswith(INCOMING_PREFIX)]


def process_batch(
    batch_path: Path,
    batch_name: str,
    reference_path: Path,
    model_path: Path,
    thresholds_path: Path,
    output_dir: Path,
    logger: logging.Logger,
) -> dict:
    """Passa um lote pelo pipeline, sem nada de AWS.

    Recebe: os caminhos do lote, da Referência, do modelo e dos limites, a pasta de saída e o logger.
    Faz: etapa 1, contrato; etapa 2, relatório de drift e réguas, com o mesmo run_id. As importações
        pesadas ficam aqui dentro porque o Lambda dá só 10 s para carregar o módulo.
    Devolve: {"run_id", "lote", "status", "metrics"}. Num lote reprovado, status é "falha".
    """
    import pandas as pd

    from credit_risk_observability.config import TARGET
    from credit_risk_observability.contracts.validate import validate_batch
    from credit_risk_observability.drift.detect import (
        add_section_to_html,
        analyze_batch,
        render_summary_section,
    )
    from credit_risk_observability.model.predict import load_model
    from credit_risk_observability.monitoring.alerts import (
        AlertThresholds,
        evaluate_alerts,
        ks_by_feature,
    )
    from credit_risk_observability.monitoring.events import new_run_id, pipeline_step

    run_id = new_run_id()
    output_dir.mkdir(parents=True, exist_ok=True)
    batch = pd.read_parquet(batch_path)

    with pipeline_step(logger, "validacao", run_id=run_id) as step:
        step.detalhe["lote"] = batch_name
        validation = validate_batch(batch)
        step.linhas_entrada = validation.rows
        step.linhas_rejeitadas = validation.rejected_rows
        if validation.passed:
            step.succeed("validation_passed")
        else:
            # Só regra e posição da linha: o arquivo com os valores nunca sai daqui (ADR-005).
            validation.minimized_failures.to_csv(output_dir / "falhas_contrato.csv", index=False)
            step.fail(
                "validation_failed",
                motivo=f"{len(validation.failures_by_rule)} regras do contrato violadas",
                falhas_por_regra=validation.failures_by_rule,
            )

    metrics = {
        "LotesProcessados": 1,
        "LotesReprovados": 0 if validation.passed else 1,
        "LinhasEntrada": validation.rows,
        "LinhasRejeitadas": validation.rejected_rows,
    }
    if not validation.passed:
        return {"run_id": run_id, "lote": batch_name, "status": "falha", "metrics": metrics}

    with pipeline_step(logger, "relatorio_drift", run_id=run_id) as step:
        step.detalhe["lote"] = batch_name
        step.linhas_entrada = len(batch)
        thresholds = AlertThresholds.from_json(thresholds_path)
        if thresholds.batch_size != len(batch):
            # Régua de um tamanho aplicada a outro dá alarme falso: melhor recusar com clareza.
            raise ValueError(
                f"Limites calibrados para {thresholds.batch_size} linhas; o lote tem {len(batch)}"
            )
        reference = pd.read_parquet(reference_path)
        snapshot, analysis = analyze_batch(reference, batch, load_model(model_path))
        ks = ks_by_feature(reference, batch)
        psi = {name: item["psi"] for name, item in analysis["feature_drift"]["features"].items()}
        auc = analysis["performance"]["roc_auc"]
        default_rate = float(batch[TARGET].mean())
        alerts = evaluate_alerts(thresholds, psi, ks, auc, default_rate)

        summary = {"run_id": run_id, "batch": batch_name, **analysis, "alertas": alerts}
        html = snapshot.get_html_str(as_iframe=False)
        (output_dir / f"drift_report_{batch_name}.html").write_text(
            add_section_to_html(html, render_summary_section(summary)), encoding="utf-8"
        )
        (output_dir / f"drift_report_{batch_name}.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        step.succeed(
            "drift_report_generated",
            alertas=[rule for rule in ("psi", "ks", "auc", "taxa_default") if alerts[rule]],
            roc_auc=auc,
            diagnostico=analysis["diagnosis"]["text"],
        )

    metrics.update(
        FeaturesComDrift=len(set(alerts["psi"]) | set(alerts["ks"])),
        AlertasDrift=int(alerts["algum_alerta"]),
        AUC=auc,
        TaxaDefault=default_rate,
    )
    return {"run_id": run_id, "lote": batch_name, "status": "sucesso", "metrics": metrics}


def handler(event: dict, context: object, s3_client: object | None = None) -> dict:
    """Ponto de entrada do Lambda.

    Recebe: o evento, o contexto do Lambda e, nos testes, um cliente S3 falso.
    Faz: baixa os arquivos para /tmp, processa, envia os relatórios e publica as métricas.
    Devolve: o resultado do último lote, ou {"status": "ignorado"} se não houver o que processar.
    """
    keys = resolve_batch_keys(event)
    if not keys:
        return {"status": "ignorado"}

    from credit_risk_observability.monitoring import events

    if s3_client is None:
        import boto3

        s3_client = boto3.client("s3")

    bucket = os.environ["BUCKET_NAME"]
    logger = build_logger()
    result: dict = {}
    for key in keys:
        # Pasta limpa a cada lote: entre execuções, o Lambda pode reaproveitar o mesmo /tmp.
        shutil.rmtree(WORK_ROOT, ignore_errors=True)
        input_dir = WORK_ROOT / "entrada"
        output_dir = WORK_ROOT / "saida"
        input_dir.mkdir(parents=True)
        events.PIPELINE_LOG_PATH = WORK_ROOT / "pipeline.jsonl"
        try:
            paths = {}
            for name, source in (
                ("batch", key),
                ("reference", REFERENCE_KEY),
                ("model", MODEL_KEY),
                ("thresholds", THRESHOLDS_KEY),
            ):
                paths[name] = input_dir / Path(source).name
                s3_client.download_file(bucket, source, str(paths[name]))

            result = process_batch(
                paths["batch"],
                Path(key).stem,
                paths["reference"],
                paths["model"],
                paths["thresholds"],
                output_dir,
                logger,
            )
            for path in sorted(output_dir.glob("*")):
                target = f"{REPORTS_PREFIX}{result['run_id']}/{path.name}"
                s3_client.upload_file(str(path), bucket, target)
            extra_fields = {"run_id": result["run_id"], "lote": result["lote"]}
            print(build_emf_line(result["metrics"], extra_fields), flush=True)
        finally:
            # O lote tem dados de clientes: ele não fica no disco depois da execução.
            shutil.rmtree(WORK_ROOT, ignore_errors=True)
    return result
