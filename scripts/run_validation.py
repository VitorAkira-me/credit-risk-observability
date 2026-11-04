"""DQ-002: portão de ingestão. Valida um lote contra o contrato antes de ele seguir no pipeline.

O que faz: confere um lote, registra o resultado no log e devolve um exit code.
Por que existe: dado sujo precisa parar aqui, antes de virar uma predição errada.
Onde entra no fluxo: é o último passo de um lote nesta etapa; só um lote aprovado segue adiante.

Uso:
    uv run python scripts/run_validation.py data/production/production_base.parquet
    uv run python scripts/run_validation.py data/production/batch_corrupted.parquet

Exit code é o número que o programa devolve ao terminar.
Exit code 0 = lote aprovado, pode seguir para o modelo.
Exit code 1 = lote bloqueado; falhas em reports/validation/<lote>_failure_cases.csv.
Um orquestrador (Airflow, CI, `&&` no shell) usa o exit code para não executar o passo seguinte.
"""

import argparse
import json
import logging
from pathlib import Path
import sys
import time

import pandas as pd

from credit_risk_observability.config import VALIDATION_REPORTS_DIR
from credit_risk_observability.contracts.schema import SCHEMA
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.monitoring.events import log_event, new_run_id

logger = logging.getLogger("run_validation")


def main(argv: list[str] | None = None, reports_dir: Path = VALIDATION_REPORTS_DIR) -> int:
    """Valida um lote e informa o resultado.

    Recebe: os argumentos da linha de comando e a pasta de relatórios (temporária nos testes).
    Faz: aplica o contrato, registra o evento e, se reprovar, grava as falhas em reports_dir.
    Devolve: o exit code. Exemplo: batch_corrupted.parquet devolve 1.
    """
    parser = argparse.ArgumentParser(description="Valida um lote contra o contrato de dados")
    parser.add_argument("batch", type=Path, help="arquivo parquet do lote")
    args = parser.parse_args(argv)

    # Mede a duração da leitura e da validação: é a latência que o OBS-001 vai acompanhar.
    start = time.perf_counter()
    result = validate_batch(pd.read_parquet(args.batch))
    fields = {
        "run_id": new_run_id(),
        "batch": args.batch.name,
        "schema": SCHEMA.name,
        "rows": result.rows,
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
    }

    if result.passed:
        log_event(logger, "validation_passed", **fields)
        print(
            f"Lote {args.batch.name}: APROVADO no contrato, com {result.rows} linhas. "
            "Pode seguir no pipeline."
        )
        return 0

    # Só um lote reprovado gera arquivos: um relatório vazio a cada aprovação seria ruído.
    reports_dir.mkdir(parents=True, exist_ok=True)
    cases_path = reports_dir / f"{args.batch.stem}_failure_cases.csv"
    summary_path = reports_dir / f"{args.batch.stem}_summary.json"
    result.failure_cases.to_csv(cases_path, index=False)
    summary = {**fields, "failures_by_rule": result.failures_by_rule}
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    log_event(
        logger,
        "validation_failed",
        level=logging.ERROR,
        **fields,
        failed_rules=len(result.failures_by_rule),
        failures_by_rule=result.failures_by_rule,
        failure_cases=str(cases_path.name),
    )
    print(
        f"Lote {args.batch.name}: BLOQUEADO no contrato, com {len(result.failures_by_rule)} "
        f"regras em falha. Detalhes em {cases_path.name}."
    )
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    sys.exit(main())
