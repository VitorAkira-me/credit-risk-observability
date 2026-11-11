"""DRIFT-003: compara o PSI e o KS calculados à mão com os números do Evidently.

O que faz: para cada feature numérica, calcula o PSI com a psi() e o KS com o scipy, nos mesmos
lotes do DRIFT-002, e põe lado a lado com o que o Evidently gravou em reports/drift/*.json. A coluna
"mesmas faixas" usa as faixas do Evidently na psi(): o que sobra de diferença é o preenchimento de zeros.
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

import numpy as np
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


def evidently_edges(reference: np.ndarray, current: np.ndarray) -> np.ndarray:
    """Reproduz as faixas que o Evidently usa no PSI.

    Recebe: os valores da Referência e do lote.
    Faz: com mais de 20 valores distintos na Referência, usa faixas de largura igual pela regra de
        Sturges sobre os dois conjuntos juntos; com 20 ou menos, uma faixa por valor (SPIKE-001).
    Devolve: as bordas. Exemplo: os valores 0, 1 e 2 dão as bordas -0.5, 0.5, 1.5 e 2.5.
    """
    combined = np.concatenate([reference, current])
    if len(np.unique(reference)) > 20:
        return np.histogram_bin_edges(combined, bins="sturges")
    values = np.unique(combined).astype(float)
    middles = (values[:-1] + values[1:]) / 2
    return np.concatenate([[values[0] - 0.5], middles, [values[-1] + 0.5]])


def main(argv: list[str] | None = None) -> int:
    """Imprime a tabela de comparação, lote a lote.

    Recebe: os argumentos da linha de comando.
    Faz: calcula PSI e KS por feature e imprime ao lado dos números do Evidently.
    Devolve: o exit code, 0 se a comparação rodou e 1 se a psi() não estiver implementada.
    """
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
            f"{'feature':12s} {'PSI quantis':>11s} {'mesmas faixas':>13s} {'PSI Evid.':>10s}"
            f" {'diferença':>10s} {'KS p scipy':>11s} {'KS p Evid.':>11s}"
        )
        for feature in features:
            try:
                reference_values = reference[feature].to_numpy()
                batch_values = batch[feature].to_numpy()
                manual = psi(reference_values, batch_values, args.bins)
                same_edges = evidently_edges(reference_values, batch_values)
                manual_same_edges = psi(reference_values, batch_values, same_edges)
            except NotImplementedError:
                print("psi() ainda não implementada: termine src/.../drift/manual.py primeiro.")
                return 1
            ks = stats.ks_2samp(reference[feature], batch[feature]).pvalue
            evidently = report[feature]
            print(
                f"{feature:12s} {manual:11.4f} {manual_same_edges:13.4f} {evidently['psi']:10.4f} "
                f"{manual_same_edges - evidently['psi']:+10.4f} {ks:11.3g} "
                f"{evidently['ks_p_value']:11.3g}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
