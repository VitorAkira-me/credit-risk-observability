"""Testes do GOV-003: métricas de justiça entre grupos e teste de proxy.

O que faz: confere as métricas com números feitos à mão e o detector de proxy com dados
sintéticos em que a resposta é conhecida.
Por que existe: uma métrica de justiça com a conta errada daria um "aprovado" falso na auditoria.
Onde entra no fluxo: roda no pytest; não lê data/ nem grava em reports/.
"""

import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import (
    BILL_COLUMNS,
    FEATURE_COLUMNS,
    PAY_AMOUNT_COLUMNS,
    PAY_STATUS_COLUMNS,
    TARGET,
)
from credit_risk_observability.governance.fairness import (
    add_groups,
    fairness_gaps,
    group_metrics,
    proxy_strength,
)


def test_parity_ratio_and_four_fifths_with_known_numbers():
    """Grupo A aprovado 100%, grupo B 50%: paridade 0,5, razão 0,5, reprovado na regra dos 4/5."""
    df = pd.DataFrame({"g": ["A"] * 4 + ["B"] * 4, TARGET: [0, 0, 0, 0, 0, 0, 0, 0]})
    approved = np.array([True, True, True, True, True, True, False, False])

    gaps = fairness_gaps(group_metrics(df, approved, "g"))

    assert gaps["paridade_demografica"] == pytest.approx(0.5)
    assert gaps["razao_impacto"] == pytest.approx(0.5)
    assert gaps["passa_regra_4_5"] is False


def test_equal_opportunity_only_looks_at_good_payers():
    """Mesma aprovação geral, mas no grupo B o modelo nega justamente o bom pagador."""
    df = pd.DataFrame({"g": ["A", "A", "B", "B"], TARGET: [0, 1, 0, 1]})
    approved = np.array([True, False, False, True])

    metrics = group_metrics(df, approved, "g").set_index("grupo")
    gaps = fairness_gaps(metrics.reset_index())

    assert gaps["paridade_demografica"] == 0  # os dois grupos: 50% aprovados
    assert metrics.loc["A", "aprovacao_bons_pagadores"] == 1.0
    assert metrics.loc["B", "aprovacao_bons_pagadores"] == 0.0
    assert gaps["igualdade_oportunidade"] == 1.0


@pytest.mark.parametrize(
    ("age", "group"),
    [(21, "até 29"), (29, "até 29"), (30, "30 a 39"), (49, "40 a 49"), (50, "50 ou mais")],
)
def test_age_bins_boundaries(age, group):
    """As bordas das faixas: 29 ainda é "até 29"; 50 já é "50 ou mais"."""
    df = pd.DataFrame({"SEX": [1], "AGE": [age]})

    assert add_groups(df)["grupo_idade"].iloc[0] == group


def make_clients(n: int, sex_leaks_into_limit: bool) -> pd.DataFrame:
    """Clientes sintéticos; opcionalmente, o limite de crédito revela o sexo (proxy perfeito)."""
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"SEX": rng.choice([1, 2], n)})
    for col in FEATURE_COLUMNS:
        if col != "SEX":
            df[col] = 0
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["MARRIAGE"] = rng.choice([1, 2], n)
    df["AGE"] = rng.integers(21, 70, n)
    for col in [*PAY_STATUS_COLUMNS, *BILL_COLUMNS, *PAY_AMOUNT_COLUMNS]:
        df[col] = rng.integers(0, 100, n)
    df["LIMIT_BAL"] = (
        df["SEX"] * 50_000 if sex_leaks_into_limit else rng.integers(1, 50, n) * 10_000
    )
    df[TARGET] = rng.choice([0, 1], n)
    return df


def test_proxy_strength_detects_a_leaking_feature():
    """Se o limite revela o sexo, a AUC do proxy vai a 1; se não revela, fica perto de 0,5."""
    assert proxy_strength(make_clients(1_000, sex_leaks_into_limit=True)) > 0.99
    assert proxy_strength(make_clients(1_000, sex_leaks_into_limit=False)) < 0.6
