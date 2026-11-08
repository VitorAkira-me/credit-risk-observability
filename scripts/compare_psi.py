"""DRIFT-003: compara o PSI e o KS calculados à mão com os números do Evidently.

O que faz: para cada feature numérica, calcula o PSI com a psi() do Akira e o KS com o scipy, nos
mesmos lotes do DRIFT-002, e põe lado a lado com o que o Evidently gravou em reports/drift/*.json.
Por que existe: "rodou" não é "funcionou". Se os números não batem, a diferença ensina algo
(faixas diferentes? epsilon diferente?), e a explicação vai para a spec do DRIFT-003.
Onde entra no fluxo: depois de prepare_data.py e make_drift_batch.py; não grava nada.

Uso:
    uv run python scripts/compare_psi.py
    uv run python scripts/compare_psi.py --bins 20 --feature LIMIT_BAL
"""

import argparse
import json
import sys

import pandas as pd
from scipy import stats

from credit_risk_observability.config import (
    CATEGORICAL_COLUMNS,
    DRIFT_REPORTS_DIR,
    FEATURE_COLUMNS,
    PRODUCTION_DIR,
    REFERENCE_PATH,
)
from credit_risk_observability.drift.manual import psi

BATCHES = ("production_base", "batch_data_drift_i100")
NUMERIC = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]


def main(argv: list[str] | None = None) -> int:
    """Imprime a tabela de comparação, lote a lote."""
    parser = argparse.ArgumentParser(description="Compara PSI e KS à mão com o Evidently")
    parser.add_argument("--bins", type=int, default=10, help="quantas faixas a sua psi() usa")
    parser.add_argument("--feature", action="append", help="limita a algumas features")
    args = parser.parse_args(argv)
    features = args.feature or NUMERIC

    reference = pd.read_parquet(REFERENCE_PATH)
    for batch_name in BATCHES:
        batch = pd.read_parquet(PRODUCTION_DIR / f"{batch_name}.parquet")
        report = json.loads(
            (DRIFT_REPORTS_DIR / f"drift_report_{batch_name}.json").read_text(encoding="utf-8")
        )["feature_drift"]["features"]
        print(f"\n{batch_name}")
        print(
            f"{'feature':12s} {'PSI à mão':>10s} {'PSI Evid.':>10s} {'diferença':>10s}"
            f" {'KS p scipy':>11s} {'KS p Evid.':>11s}"
        )
        for feature in features:
            try:
                manual = psi(reference[feature].to_numpy(), batch[feature].to_numpy(), args.bins)
            except NotImplementedError:
                print("psi() ainda não implementada: termine src/.../drift/manual.py primeiro.")
                return 1
            ks = stats.ks_2samp(reference[feature], batch[feature]).pvalue
            evidently = report[feature]
            print(
                f"{feature:12s} {manual:10.4f} {evidently['psi']:10.4f} "
                f"{manual - evidently['psi']:+10.4f} {ks:11.3g} {evidently['ks_p_value']:11.3g}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
