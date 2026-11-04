"""DQ-002: gera data/production/batch_corrupted.parquet a partir da Produção-base.

O que faz: cria um lote com defeitos conhecidos e contados.
Por que existe: para provar que o portão de validação bloqueia dado sujo.
Onde entra no fluxo: depois de prepare_data.py e antes de run_validation.py.

Uso:
    uv run python scripts/make_corrupted_batch.py

Também grava as contagens esperadas por regra em batch_corrupted_expected.json, para conferir
se a validação encontra exatamente os defeitos injetados.
"""

import json
import logging

import pandas as pd

from credit_risk_observability.config import (
    CORRUPTED_BATCH_PATH,
    CORRUPTED_EXPECTED_PATH,
    PRODUCTION_BASE_PATH,
    SEED,
)
from credit_risk_observability.contracts.corrupt import DEFECTS, inject_defects

BATCH_SIZE = 1_000  # linhas sorteadas da Produção-base, antes de acrescentar as duplicadas

logger = logging.getLogger("make_corrupted_batch")


def main() -> None:
    """Gera o lote corrompido e o gabarito.

    Recebe: nada; lê a Produção-base de config.py.
    Faz: injeta os defeitos e grava o lote e as contagens esperadas por regra.
    Devolve: nada. Exemplo: as 1.000 linhas viram 1.020, com 160 falhas esperadas.
    """
    production = pd.read_parquet(PRODUCTION_BASE_PATH)
    batch, expected = inject_defects(production, batch_size=BATCH_SIZE, seed=SEED)

    batch.to_parquet(CORRUPTED_BATCH_PATH, index=False)
    CORRUPTED_EXPECTED_PATH.write_text(
        json.dumps(
            {"rows": len(batch), "defects": DEFECTS, "expected_failures": expected}, indent=2
        ),
        encoding="utf-8",
    )
    logger.info("Lote corrompido: %s (%d linhas)", CORRUPTED_BATCH_PATH, len(batch))
    logger.info("Falhas esperadas: %s", expected)
    print(
        f"Lote corrompido gravado: {len(batch)} linhas, {sum(expected.values())} falhas esperadas "
        "no contrato. O próximo passo, run_validation.py, precisa bloquear este lote."
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    main()
