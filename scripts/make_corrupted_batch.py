"""DQ-002: gera data/production/batch_corrupted.parquet a partir da Produção-base.

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

BATCH_SIZE = 1_000

logger = logging.getLogger("make_corrupted_batch")


def main() -> None:
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    main()
