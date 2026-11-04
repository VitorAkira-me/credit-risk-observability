"""Download do dataset UCI e padronização dos nomes de colunas.

O que faz: traz os 30.000 clientes do repositório UCI e guarda uma cópia local (o raw).
Por que existe: o UCI chama as colunas de X1 a X23, e o projeto usa os nomes oficiais.
Onde entra no fluxo: é o primeiro passo, chamado por scripts/prepare_data.py.
"""

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
    """Troca X1..X23 pelos nomes oficiais e junta ID, features e alvo num DataFrame.

    Recebe: as tabelas separadas do UCI (features, alvo, IDs e o dicionário de variáveis).
    Faz: renomeia as features, confere se a lista bate com FEATURE_COLUMNS e junta tudo.
    Devolve: uma tabela só. Exemplo: ID + 23 features + default dão 25 colunas.
    """
    # No dicionário do UCI, a coluna "description" guarda o nome oficial de cada feature.
    feature_vars = variables[variables["role"] == "Feature"]
    rename = dict(zip(feature_vars["name"], feature_vars["description"], strict=True))
    features = features.rename(columns=rename)

    # Melhor parar aqui do que treinar sem perceber que o UCI mudou as colunas.
    if list(features.columns) != FEATURE_COLUMNS:
        raise ValueError(f"Colunas inesperadas vindas do UCI: {list(features.columns)}")

    # O alvo vem numa tabela de uma coluna só: pega essa coluna e dá o nome "default".
    target = targets.iloc[:, 0].rename(TARGET)
    return pd.concat([ids[[ID_COLUMN]], features, target], axis=1)


def fetch_raw() -> pd.DataFrame:
    """Baixa o dataset via ucimlrepo (sem login) e devolve com colunas padronizadas.

    Recebe: nada; o dataset é o de UCI_DATASET_ID.
    Faz: chama o UCI pela internet e padroniza o resultado.
    Devolve: a tabela completa, com 30.000 linhas.
    """
    # Importa aqui dentro: só quem precisa baixar carrega esta biblioteca.
    from ucimlrepo import fetch_ucirepo

    logger.info("Baixando dataset UCI id=%s", UCI_DATASET_ID)
    dataset = fetch_ucirepo(id=UCI_DATASET_ID)
    data = dataset.data
    return standardize_columns(data.features, data.targets, data.ids, dataset.variables)


def load_or_download_raw(path: Path, refresh: bool = False) -> pd.DataFrame:
    """Usa o raw em disco se existir; baixa só na primeira vez ou com refresh=True.

    Recebe: o caminho do raw e se o download deve ser refeito.
    Faz: lê o arquivo local ou baixa e salva. Assim, repetir o pipeline não depende da internet.
    Devolve: a tabela completa.
    """
    if path.exists() and not refresh:
        logger.info("Raw encontrado em %s, sem novo download", path)
        return pd.read_parquet(path)

    df = fetch_raw()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Raw salvo em %s (%d linhas)", path, len(df))
    return df
