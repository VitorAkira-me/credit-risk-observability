"""Testes do GOV-004: impacto no negócio e experimento de dose-resposta.

O que faz: confere as contagens de erro com números feitos à mão e as propriedades do experimento
com dados sintéticos (dose zero não muda nada; cada drift só mexe no que deveria mexer).
Por que existe: a análise causal do README se apoia nesses números.
Onde entra no fluxo: roda no pytest; não lê data/ nem grava em reports/.
"""

import numpy as np
import pandas as pd

from credit_risk_observability.config import (
    BILL_COLUMNS,
    FEATURE_COLUMNS,
    MODEL_FEATURES,
    PAY_AMOUNT_COLUMNS,
    PAY_STATUS_COLUMNS,
    TARGET,
)
from credit_risk_observability.governance.causal import business_impact, dose_response
from credit_risk_observability.model.train import build_pipeline


def test_business_impact_counts_the_two_costly_errors():
    """Calote aprovado e bom cliente negado, e a exposição soma o limite dos calotes aprovados."""
    df = pd.DataFrame({TARGET: [1, 1, 0, 0], "LIMIT_BAL": [100, 200, 300, 400]})
    scores = np.array([0.1, 0.9, 0.9, 0.1])  # aprova a 1ª e a 4ª linhas

    impact = business_impact(df, scores)

    assert impact["calote_aprovado"] == 1  # a 1ª: aprovada e deu calote
    assert impact["bom_cliente_negado"] == 1  # a 3ª: negada e pagaria
    assert impact["exposicao_calote_aprovado"] == 100
    assert impact["taxa_aprovacao"] == 0.5


def make_clients(n: int, seed: int) -> pd.DataFrame:
    """Clientes sintéticos com default ligado a PAY_0 e taxa abaixo de 50% no quartil de fatura."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({col: 0 for col in FEATURE_COLUMNS}, index=range(n))
    df["LIMIT_BAL"] = rng.integers(1, 50, n) * 10_000
    df["SEX"] = rng.choice([1, 2], n)
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["MARRIAGE"] = rng.choice([1, 2], n)
    df["AGE"] = rng.integers(21, 70, n)
    for col in PAY_STATUS_COLUMNS:
        df[col] = rng.integers(-2, 5, n)
    for col in BILL_COLUMNS:
        df[col] = rng.integers(-5_000, 200_000, n)
    for col in PAY_AMOUNT_COLUMNS:
        df[col] = rng.integers(0, 20_000, n)
    df[TARGET] = (rng.random(n) < 1 / (1 + np.exp(-2 * (df["PAY_0"] - 2)))).astype("int64")
    return df


def test_dose_response_isolates_each_drift():
    """Dose zero igual nos dois; data drift não mexe no alvo; concept drift sobe o default."""
    reference = make_clients(3_000, seed=1)
    model = build_pipeline().fit(reference[MODEL_FEATURES], reference[TARGET])

    rows = pd.DataFrame(dose_response(make_clients(1_000, seed=2), model, doses=(0.0, 0.5, 1.0)))

    by = {(r.cenario, r.dose): r for r in rows.itertuples()}
    assert by[("data_drift", 0.0)].roc_auc == by[("concept_drift", 0.0)].roc_auc
    data = rows[rows["cenario"] == "data_drift"]["taxa_default"]
    assert data.nunique() == 1  # data drift mexe no X, nunca no y
    concept = rows[rows["cenario"] == "concept_drift"]["taxa_default"].tolist()
    assert concept == sorted(concept) and concept[0] < concept[-1]
