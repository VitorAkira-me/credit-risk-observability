"""DRIFT-002: gera o relatório de drift de um lote, em HTML e em JSON.

O que faz: confere o lote no contrato, pontua com o modelo, mede o drift e grava o relatório.
Por que existe: é a evidência da Etapa 2: quais features mudaram e se o modelo sentiu.
Onde entra no fluxo: depois de run_validation.py; o JSON alimenta a observabilidade (Etapa 3).

Uso:
    uv run python scripts/run_drift_report.py data/production/production_base.parquet
    uv run python scripts/run_drift_report.py data/production/batch_data_drift_i100.parquet
    uv run python scripts/run_drift_report.py data/production/batch_concept_drift_i100.parquet

Exit code (o número que o programa devolve ao terminar): 0 = relatório gravado, seja qual for o
diagnóstico, porque decidir o que vira alerta é papel do OBS-002; 1 = lote reprovado no contrato.
"""

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import platform
import sys
import time

import evidently
import pandas as pd
import sklearn

from credit_risk_observability.config import (
    DRIFT_REPORTS_DIR,
    MODEL_PATH,
    REFERENCE_PATH,
)
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.data.split import file_sha256
from credit_risk_observability.drift.detect import (
    add_section_to_html,
    analyze_batch,
    render_summary_section,
)
from credit_risk_observability.model.predict import load_model
from credit_risk_observability.monitoring.events import log_event, new_run_id

logger = logging.getLogger("run_drift_report")


def build_provenance(batch_path: Path, reference_path: Path, model_path: Path) -> dict:
    """Registra de onde vieram os números do relatório.

    Recebe: os caminhos do lote, da Referência e do modelo.
    Faz: junta os hashes (impressão digital de cada arquivo) e as versões das bibliotecas.
        Guarda só o nome dos arquivos, porque um caminho completo publicaria detalhes da máquina.
    Devolve: um dicionário pronto para virar JSON.
    """
    return {
        "batch_file": batch_path.name,
        "batch_sha256": file_sha256(batch_path),
        "reference_file": reference_path.name,
        "reference_sha256": file_sha256(reference_path),
        "model_file": model_path.name,
        "model_sha256": file_sha256(model_path),
        "versions": {
            "python": platform.python_version(),
            "evidently": evidently.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
        },
    }


def main(
    argv: list[str] | None = None,
    reference_path: Path = REFERENCE_PATH,
    model_path: Path = MODEL_PATH,
    reports_dir: Path = DRIFT_REPORTS_DIR,
) -> int:
    """Gera o relatório de um lote.

    Recebe: os argumentos da linha de comando e os caminhos (os testes passam pastas temporárias).
    Faz: confere o contrato, mede os três blocos e grava drift_report_<lote>.html e .json.
    Devolve: o exit code, 0 se o relatório foi gravado e 1 se o lote foi reprovado.
    """
    parser = argparse.ArgumentParser(
        description="Gera o relatório de drift de um lote (DRIFT-002)"
    )
    parser.add_argument("batch", type=Path, help="arquivo parquet do lote")
    args = parser.parse_args(argv)

    start = time.perf_counter()
    run_id = new_run_id()
    batch_name = args.batch.stem
    batch = pd.read_parquet(args.batch)

    # Dado sujo não é drift: lote reprovado não chega ao modelo nem gera relatório.
    validation = validate_batch(batch)
    if not validation.passed:
        log_event(
            logger,
            "drift_report_rejected",
            level=logging.ERROR,
            run_id=run_id,
            batch=batch_name,
            rows=validation.rows,
            failures_by_rule=validation.failures_by_rule,
        )
        print(f"Lote {batch_name} REPROVADO no contrato: relatório não gerado.")
        return 1

    reference = pd.read_parquet(reference_path)
    model = load_model(model_path)
    snapshot, analysis = analyze_batch(reference, batch, model)

    summary = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "batch": batch_name,
        "rows": {"batch": len(batch), "reference": len(reference)},
        "provenance": build_provenance(args.batch, reference_path, model_path),
        **analysis,
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    html_path = reports_dir / f"drift_report_{batch_name}.html"
    summary_path = reports_dir / f"drift_report_{batch_name}.json"
    evidently_html = snapshot.get_html_str(as_iframe=False)
    html_path.write_text(
        add_section_to_html(evidently_html, render_summary_section(summary)), encoding="utf-8"
    )
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    changed_by_psi = summary["feature_drift"]["changed_by_psi"]
    changed_by_ks = summary["feature_drift"]["changed_by_ks"]
    performance = summary["performance"]
    diagnosis = summary["diagnosis"]["text"]
    log_event(
        logger,
        "drift_report_generated",
        run_id=run_id,
        batch=batch_name,
        rows=len(batch),
        changed_by_psi=changed_by_psi,
        changed_by_ks=changed_by_ks,
        roc_auc=performance["roc_auc"],
        diagnosis=diagnosis,
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
    )
    print(
        f"Lote {batch_name}: {len(batch)} linhas.\n"
        f"  Features que mudaram pelo PSI: {', '.join(changed_by_psi) or 'nenhuma'}.\n"
        f"  Features que mudaram pelo KS: {', '.join(changed_by_ks) or 'nenhuma'}.\n"
        f"  AUC: {performance['roc_auc']:.4f} "
        f"(limite de queda: {performance['control_ci_low']}).\n"
        f"  Diagnóstico: {diagnosis}.\n"
        f"  Relatório: {html_path.name}"
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    sys.exit(main())
