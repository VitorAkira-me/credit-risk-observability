"""Download do dataset UCI e padronização dos nomes de colunas."""

import logging
from pathlib import Path

import pandas as pd

from credit_risk_observability.config import (
    FEATURE_COLUMNS,
    ID_COLUMN,
    TARGET,
    UCI_DATASET_ID,
)

logger = logging.getLogger(__name__)


def standardize_columns(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    ids: pd.DataFrame,
    variables: pd.DataFrame,
) -> pd.DataFrame:
    """Troca X1..X23 pelos nomes oficiais e junta ID, features e alvo num DataFrame."""
    feature_vars = variables[variables["role"] == "Feature"]
    rename = dict(zip(feature_vars["name"], feature_vars["description"], strict=True))
    features = features.rename(columns=rename)

    if list(features.columns) != FEATURE_COLUMNS:
        raise ValueError(f"Colunas inesperadas vindas do UCI: {list(features.columns)}")

    target = targets.iloc[:, 0].rename(TARGET)
    return pd.concat([ids[[ID_COLUMN]], features, target], axis=1)


def fetch_raw() -> pd.DataFrame:
    """Baixa o dataset via ucimlrepo (sem login) e devolve com colunas padronizadas."""
    from ucimlrepo import fetch_ucirepo

    logger.info("Baixando dataset UCI id=%s", UCI_DATASET_ID)
    dataset = fetch_ucirepo(id=UCI_DATASET_ID)
    data = dataset.data
    return standardize_columns(data.features, data.targets, data.ids, dataset.variables)


def load_or_download_raw(path: Path, refresh: bool = False) -> pd.DataFrame:
    """Usa o raw em disco se existir; baixa só na primeira vez ou com refresh=True."""
    if path.exists() and not refresh:
        logger.info("Raw encontrado em %s, sem novo download", path)
        return pd.read_parquet(path)

    df = fetch_raw()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Raw salvo em %s (%d linhas)", path, len(df))
    return df
