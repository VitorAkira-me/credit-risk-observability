"""Baseline: LogisticRegression com pré-processamento dentro do Pipeline."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from credit_risk_observability.config import MODEL_CATEGORICAL, MODEL_NUMERIC, SEED


def build_pipeline() -> Pipeline:
    """Pré-processamento + modelo num objeto só.

    O scaler aprende média e desvio só no treino (fit) e reaplica na validação e na produção:
    sem vazamento. Códigos raros de EDUCATION (< 1%) viram uma categoria "infrequente", e
    códigos nunca vistos não quebram a predição.
    """
    preprocess = ColumnTransformer(
        [
            (
                "cat",
                OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=0.01),
                MODEL_CATEGORICAL,
            ),
            ("num", StandardScaler(), MODEL_NUMERIC),
        ]
    )
    # class_weight="balanced": com 22% de default, sem peso o modelo aprende a dizer "paga".
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEED)
    return Pipeline([("preprocess", preprocess), ("model", model)])


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """KS de crédito: maior distância entre as curvas acumuladas de bons e maus (max TPR - FPR)."""
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return float(np.max(tpr - fpr))


def evaluate(y_true: pd.Series, y_score: np.ndarray, threshold: float) -> dict:
    y_pred = (y_score >= threshold).astype(int)
    return {
        "rows": len(y_true),
        "default_rate": round(float(np.mean(y_true)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_score)), 4),
        "ks": round(ks_statistic(y_true, y_score), 4),
        "recall_default": round(float(recall_score(y_true, y_pred)), 4),
        "precision_default": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "f1_default": round(float(f1_score(y_true, y_pred)), 4),
        "brier": round(float(brier_score_loss(y_true, y_score)), 4),
        "predicted_default_rate": round(float(y_pred.mean()), 4),
    }
