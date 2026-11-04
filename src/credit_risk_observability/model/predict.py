"""Carregar o modelo salvo e pontuar um lote.

O que faz: lê o modelo do disco e calcula a probabilidade de default de cada cliente.
Por que existe: treino e uso em produção usam a mesma função, com as mesmas colunas.
Onde entra no fluxo: scripts/train_baseline.py usa predict_proba para medir o modelo.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from credit_risk_observability.config import MODEL_FEATURES


def load_model(path: Path) -> Pipeline:
    """Carrega o modelo treinado.

    Recebe: o caminho do arquivo .joblib.
    Faz: lê o Pipeline salvo pelo treino. Só carregue arquivos de confiança: joblib executa código.
    Devolve: o Pipeline, pronto para predizer.
    """
    return joblib.load(path)


def predict_proba(model: Pipeline, df: pd.DataFrame) -> np.ndarray:
    """Probabilidade de default. Seleciona as colunas pelo nome, na ordem do treino.

    Recebe: o modelo e a tabela de clientes, que pode ter colunas a mais (SEX, MARRIAGE, default).
    Faz: usa só MODEL_FEATURES e pega a coluna 1 do resultado, a da classe "deu default".
    Devolve: um array com uma probabilidade por cliente. Exemplo: [0.12, 0.81].
    """
    return model.predict_proba(df[MODEL_FEATURES])[:, 1]
