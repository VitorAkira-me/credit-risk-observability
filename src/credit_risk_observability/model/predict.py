"""Carregar o modelo salvo e pontuar um lote."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from credit_risk_observability.config import MODEL_FEATURES


def load_model(path: Path) -> Pipeline:
    return joblib.load(path)


def predict_proba(model: Pipeline, df: pd.DataFrame) -> np.ndarray:
    """Probabilidade de default. Seleciona as colunas pelo nome, na ordem do treino."""
    return model.predict_proba(df[MODEL_FEATURES])[:, 1]
