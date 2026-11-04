"""Baseline: LogisticRegression com pré-processamento dentro do Pipeline.

O que faz: monta o modelo e calcula as métricas de qualidade.
Por que existe: o projeto não busca o melhor modelo, e sim observar um modelo em produção. O
    baseline é o modelo simples que serve de ponto de comparação.
Onde entra no fluxo: scripts/train_baseline.py chama estas funções depois do split.
"""

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

    Recebe: nada; as colunas vêm de config.py.
    Faz: monta o pré-processamento e o modelo, ainda sem treinar.
    Devolve: o Pipeline, pronto para o fit.
    """
    # One-hot: transforma cada código em uma coluna de 0 e 1. StandardScaler: põe os números na
    # mesma escala (média 0, desvio 1), para fatura não pesar mais que idade só por ser maior.
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
    """KS de crédito: maior distância entre as curvas acumuladas de bons e maus (max TPR - FPR).

    Não confundir com o teste KS de drift: este mede o quanto o modelo separa bons de maus,
    e aquele mede o quanto a distribuição de uma coluna mudou.

    Recebe: os resultados reais (0 ou 1) e os scores do modelo.
    Faz: encontra o corte de score com a maior diferença entre bons e maus.
    Devolve: um número de 0 a 1. Exemplo: separação perfeita dá 1,0; score igual para todos, 0,0.
    """
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return float(np.max(tpr - fpr))


def evaluate(y_true: pd.Series, y_score: np.ndarray, threshold: float) -> dict:
    """Calcula as métricas do modelo em um conjunto de clientes.

    Recebe: os resultados reais, as probabilidades previstas e o limiar de decisão.
    Faz: mede o modelo. Não usa acurácia: com 22% de default, dizer sempre "paga" acertaria 78%.
    Devolve: um dicionário de métricas, com 4 casas decimais.
    """
    # Probabilidade igual ou acima do limiar vira a previsão "vai dar default".
    y_pred = (y_score >= threshold).astype(int)
    return {
        "rows": len(y_true),
        "default_rate": round(float(np.mean(y_true)), 4),
        # AUC: chance de um mau receber score maior que um bom. 0,5 é sorteio, 1,0 é perfeito.
        "roc_auc": round(float(roc_auc_score(y_true, y_score)), 4),
        "ks": round(ks_statistic(y_true, y_score), 4),
        # Recall: dos que deram default, quantos o modelo pegou.
        "recall_default": round(float(recall_score(y_true, y_pred)), 4),
        # Precisão: dos que o modelo apontou, quantos deram default mesmo.
        "precision_default": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        # F1: resume recall e precisão em um número.
        "f1_default": round(float(f1_score(y_true, y_pred)), 4),
        # Brier: erro médio das probabilidades. Quanto menor, melhor.
        "brier": round(float(brier_score_loss(y_true, y_score)), 4),
        "predicted_default_rate": round(float(y_pred.mean()), 4),
    }
