"""DATA-001: baixa o raw, gera a EDA curta e separa Referência / Produção.

Uso:
    uv run python scripts/prepare_data.py            # reaproveita o raw se já existir
    uv run python scripts/prepare_data.py --refresh  # força novo download
"""

import argparse
import json
import logging

from credit_risk_observability.config import (
    EDA_REPORT_PATH,
    PRODUCTION_BASE_PATH,
    PRODUCTION_SIZE,
    RAW_PATH,
    REFERENCE_PATH,
    SEED,
    SPLIT_METADATA_PATH,
)
from credit_risk_observability.data.download import load_or_download_raw
from credit_risk_observability.data.eda import render_markdown, summarize
from credit_risk_observability.data.split import build_metadata, split_reference_production

logger = logging.getLogger("prepare_data")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara Referência e Produção (DATA-001)")
    parser.add_argument("--refresh", action="store_true", help="baixa o raw de novo")
    args = parser.parse_args()

    raw = load_or_download_raw(RAW_PATH, refresh=args.refresh)

    EDA_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EDA_REPORT_PATH.write_text(render_markdown(summarize(raw)), encoding="utf-8")
    logger.info("EDA salva em %s", EDA_REPORT_PATH)

    reference, production = split_reference_production(raw, PRODUCTION_SIZE, SEED)
    for df, path in ((reference, REFERENCE_PATH), (production, PRODUCTION_BASE_PATH)):
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        logger.info("Salvo %s (%d linhas)", path, len(df))

    metadata = build_metadata(RAW_PATH, reference, production, PRODUCTION_SIZE, SEED)
    SPLIT_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("Metadata: %s", json.dumps(metadata))

    if metadata["shared_ids"] != 0:
        raise SystemExit("Vazamento: Referência e Produção compartilham IDs")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    main()
