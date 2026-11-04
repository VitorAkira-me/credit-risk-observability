"""Testes de model/: provam que o modelo aprende, é medido certo e ignora atributos sensíveis.

O que faz: treina com dados sintéticos e confere o resultado e as métricas.
Por que existe: o baseline é a régua do projeto; com a régua errada, toda medição de queda erra.
Onde entra no fluxo: roda no pytest, sem depender de data/ nem de rede.
"""

import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import MODEL_FEATURES, SENSITIVE_EXCLUDED
from credit_risk_observability.model.predict import predict_proba
from credit_risk_observability.model.train import build_pipeline, evaluate, ks_statistic


@pytest.fixture
def fake_reference() -> pd.DataFrame:
    """Dados sintéticos com sinal: quanto maior PAY_0, mais default."""
    rng = np.random.default_rng(0)
    n = 2_000
    df = pd.DataFrame({col: rng.normal(size=n) for col in MODEL_FEATURES})
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["PAY_0"] = rng.integers(-2, 4, n)
    df["default"] = (rng.random(n) < 1 / (1 + np.exp(-(df["PAY_0"] - 1)))).astype(int)
    return df


def test_sensitive_columns_are_not_model_features():
    """ADR-004: SEX e MARRIAGE não entram no modelo."""
    assert not set(SENSITIVE_EXCLUDED) & set(MODEL_FEATURES)


def test_pipeline_learns_signal(fake_reference):
    """Com sinal real nos dados, o modelo precisa passar de AUC 0,7 (0,5 seria sorteio)."""
    model = build_pipeline().fit(fake_reference[MODEL_FEATURES], fake_reference["default"])

    scores = predict_proba(model, fake_reference)

    assert evaluate(fake_reference["default"], scores, threshold=0.5)["roc_auc"] > 0.7


def test_pipeline_handles_unseen_education_code(fake_reference):
    """Um código nunca visto não pode derrubar a predição."""
    model = build_pipeline().fit(fake_reference[MODEL_FEATURES], fake_reference["default"])
    batch = fake_reference.head(3).copy()
    batch["EDUCATION"] = 99

    scores = predict_proba(model, batch)

    assert np.all((scores >= 0) & (scores <= 1))


def test_ks_statistic_extremes():
    """Separação perfeita dá KS 1, e score igual para todos dá KS 0."""
    y = np.array([0, 0, 1, 1])

    assert ks_statistic(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert ks_statistic(y, np.array([0.5, 0.5, 0.5, 0.5])) == 0.0


def test_evaluate_counts_predicted_defaults():
    """Conta feita à mão: 2 de 4 acima do limiar e 1 dos 2 defaults encontrado."""
    y = pd.Series([0, 1, 1, 0])

    m = evaluate(y, np.array([0.2, 0.7, 0.4, 0.6]), threshold=0.5)

    assert m["predicted_default_rate"] == 0.5
    assert m["recall_default"] == 0.5
