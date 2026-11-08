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

Privacidade (ADR-005): o CSV versionado tem só a regra e a posição da linha, nunca o valor barrado.
O detalhe completo, com os valores, vai para outputs/validation/ (local, fora do git).
Um orquestrador (Airflow, CI, `&&` no shell) usa o exit code para não executar o passo seguinte.
"""

import argparse
import json
import logging
from pathlib import Path
import sys

import pandas as pd

from credit_risk_observability.config import VALIDATION_DETAIL_DIR, VALIDATION_REPORTS_DIR
from credit_risk_observability.contracts.schema import SCHEMA
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.monitoring.events import pipeline_step

logger = logging.getLogger("run_validation")


def main(
    argv: list[str] | None = None,
    reports_dir: Path = VALIDATION_REPORTS_DIR,
    detail_dir: Path = VALIDATION_DETAIL_DIR,
) -> int:
    """Valida um lote e informa o resultado.

    Recebe: os argumentos da linha de comando, a pasta de relatórios e a pasta do detalhe local
        (as duas temporárias nos testes).
    Faz: aplica o contrato, registra o evento e, se reprovar, grava as falhas em reports_dir.
    Devolve: o exit code. Exemplo: batch_corrupted.parquet devolve 1.
    """
    parser = argparse.ArgumentParser(description="Valida um lote contra o contrato de dados")
    parser.add_argument("batch", type=Path, help="arquivo parquet do lote")
    args = parser.parse_args(argv)

    # pipeline_step mede a duração (leitura + validação) e grava o evento ao sair do bloco.
    with pipeline_step(logger, "validacao") as step:
        step.detalhe.update(lote=args.batch.name, contrato=SCHEMA.name)
        result = validate_batch(pd.read_parquet(args.batch))
        step.linhas_entrada = result.rows
        step.linhas_rejeitadas = result.rejected_rows

        if result.passed:
            step.succeed("validation_passed")
            print(
                f"Lote {args.batch.name}: APROVADO no contrato, com {result.rows} linhas. "
                "Pode seguir no pipeline."
            )
            return 0

        # Só um lote reprovado gera arquivos: um relatório vazio a cada aprovação seria ruído.
        reports_dir.mkdir(parents=True, exist_ok=True)
        cases_path = reports_dir / f"{args.batch.stem}_failure_cases.csv"
        summary_path = reports_dir / f"{args.batch.stem}_summary.json"
        # Versionado: só regra e posição. Local: o detalhe com os valores, para investigar.
        result.minimized_failures.to_csv(cases_path, index=False)
        detail_dir.mkdir(parents=True, exist_ok=True)
        result.failure_cases.to_csv(detail_dir / f"{args.batch.stem}_detalhe.csv", index=False)
        summary = {
            "run_id": step.run_id,
            "batch": args.batch.name,
            "schema": SCHEMA.name,
            "rows": result.rows,
            "rejected_rows": result.rejected_rows,
            "failures_by_rule": result.failures_by_rule,
        }
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        step.fail(
            "validation_failed",
            motivo=f"{len(result.failures_by_rule)} regras do contrato violadas",
            falhas_por_regra=result.failures_by_rule,
            arquivo_falhas=cases_path.name,
        )
        print(
            f"Lote {args.batch.name}: BLOQUEADO no contrato, com {len(result.failures_by_rule)} "
            f"regras em falha e {result.rejected_rows} linhas rejeitadas. "
            f"Detalhes em {cases_path.name}."
        )
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    sys.exit(main())
