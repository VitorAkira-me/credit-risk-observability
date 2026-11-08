"""GOV-003: mede se o modelo trata grupos de clientes de forma diferente.

O que faz: calcula, por grupo (sexo, faixa etária), a taxa de aprovação e a aprovação entre os
bons pagadores, e resume as diferenças em duas métricas de justiça. Também testa se tirar `SEX`
do modelo resolve: mede o quanto as outras features "adivinham" o sexo (proxy) e compara a
disparidade de um modelo com e sem os atributos sensíveis.
Por que existe: "o modelo é justo?" só se responde com número. E retirar a coluna não basta se
outras colunas carregam a mesma informação (ADR-004).
Onde entra no fluxo: scripts/run_fairness.py, com Referência, Produção-base e lotes com drift.

Vocabulário:
- Aprovado: o modelo prevê que o cliente paga (score abaixo do limiar de decisão).
- Paridade demográfica: todos os grupos aprovados na mesma proporção, sem olhar quem paga.
- Igualdade de oportunidade: entre os que de fato pagam, todos os grupos aprovados na mesma
  proporção. Diferença aqui é um bom pagador sendo negado por causa do grupo.
- Regra dos 4/5: a razão entre a menor e a maior taxa de aprovação abaixo de 0,8 é sinal de
  impacto desigual (critério usado em auditorias de discriminação nos EUA).
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from credit_risk_observability.config import (
    DECISION_THRESHOLD,
    MODEL_CATEGORICAL,
    MODEL_FEATURES,
    MODEL_NUMERIC,
    SEED,
    SENSITIVE_EXCLUDED,
    TARGET,
)
from credit_risk_observability.model.predict import predict_proba

SEX_LABELS = {1: "masculino", 2: "feminino"}  # códigos documentados pelo UCI
AGE_BINS = [0, 29, 39, 49, 200]
AGE_LABELS = ["até 29", "30 a 39", "40 a 49", "50 ou mais"]
FOUR_FIFTHS = 0.8


def add_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta as colunas de grupo usadas na auditoria: sexo por extenso e faixa etária.

    Recebe: os clientes.
    Faz: traduz o código de SEX e corta AGE em 4 faixas. Não altera a tabela recebida.
    Devolve: uma cópia com "grupo_sexo" e "grupo_idade".
    """
    out = df.copy()
    out["grupo_sexo"] = out["SEX"].map(SEX_LABELS).fillna("outro")
    out["grupo_idade"] = pd.cut(out["AGE"], AGE_BINS, labels=AGE_LABELS).astype(str)
    return out


def group_metrics(df: pd.DataFrame, approved: np.ndarray, group_col: str) -> pd.DataFrame:
    """Taxas por grupo: aprovação geral, aprovação entre bons pagadores e default real.

    Recebe: os clientes (com o alvo e a coluna de grupo) e a decisão do modelo (True = aprovado).
    Faz: agrupa e calcula as taxas. Só números agregados: nenhuma linha de cliente sai daqui.
    Devolve: uma tabela com uma linha por grupo. Exemplo: "feminino", 5.400 clientes, 70% aprovados.
    """
    data = pd.DataFrame(
        {"grupo": df[group_col].to_numpy(), "aprovado": approved, "default": df[TARGET].to_numpy()}
    )
    rows = []
    for group, part in data.groupby("grupo", sort=True):
        good = part[part["default"] == 0]
        rows.append(
            {
                "grupo": group,
                "clientes": len(part),
                "taxa_default_real": round(float(part["default"].mean()), 4),
                "taxa_aprovacao": round(float(part["aprovado"].mean()), 4),
                "aprovacao_bons_pagadores": round(float(good["aprovado"].mean()), 4),
            }
        )
    return pd.DataFrame(rows)


def fairness_gaps(metrics: pd.DataFrame) -> dict[str, float]:
    """Resume a tabela por grupo em três números.

    Recebe: o resultado de group_metrics.
    Faz: diferença entre a maior e a menor taxa (paridade e oportunidade) e a razão entre a menor e
        a maior aprovação (regra dos 4/5).
    Devolve: {"paridade_demografica": 0.05, "razao_impacto": 0.93, "igualdade_oportunidade": 0.04,
        "passa_regra_4_5": True}.
    """
    approval = metrics["taxa_aprovacao"]
    good = metrics["aprovacao_bons_pagadores"]
    ratio = float(approval.min() / approval.max()) if approval.max() > 0 else 0.0
    return {
        "paridade_demografica": round(float(approval.max() - approval.min()), 4),
        "razao_impacto": round(ratio, 4),
        "igualdade_oportunidade": round(float(good.max() - good.min()), 4),
        "passa_regra_4_5": ratio >= FOUR_FIFTHS,
    }


def audit(df: pd.DataFrame, model: Pipeline, features: list[str] | None = None) -> dict:
    """Auditoria completa de um conjunto de clientes: por sexo e por faixa etária.

    Recebe: os clientes (com alvo), o modelo e as colunas que ele espera (padrão: as do ML-001).
    Faz: pontua, decide (aprovado = score abaixo do limiar) e mede cada recorte.
    Devolve: {"sexo": {"grupos": [...], "diferencas": {...}}, "idade": {...}}.
    """
    grouped = add_groups(df)
    if features is None:
        scores = predict_proba(model, grouped)
    else:
        scores = model.predict_proba(grouped[features])[:, 1]
    approved = scores < DECISION_THRESHOLD
    result = {
        "clientes": len(df),
        # A AUC entra para pesar o custo de cada mitigação: justiça e performance juntas.
        "roc_auc": round(float(roc_auc_score(df[TARGET], scores)), 4),
        "taxa_aprovacao_geral": round(float(approved.mean()), 4),
    }
    for name, column in (("sexo", "grupo_sexo"), ("idade", "grupo_idade")):
        metrics = group_metrics(grouped, approved, column)
        result[name] = {"grupos": metrics.to_dict("records"), "diferencas": fairness_gaps(metrics)}
    return result


def proxy_strength(reference: pd.DataFrame, target_column: str = "SEX") -> float:
    """O quanto as features do modelo conseguem adivinhar um atributo que ficou de fora.

    Recebe: a Referência e o atributo (SEX por padrão).
    Faz: treina uma regressão logística que prevê o atributo a partir das MODEL_FEATURES, com
        validação cruzada em 5 partes (cada cliente é previsto por um modelo que não o viu).
    Devolve: a AUC. 0,5 = as features não sabem nada do sexo; perto de 1 = sabem tudo.
    """
    y = (reference[target_column] == reference[target_column].min()).astype(int)
    pipeline = Pipeline(
        [
            ("preprocess", _preprocess(MODEL_CATEGORICAL, MODEL_NUMERIC)),
            ("model", LogisticRegression(max_iter=1000, random_state=SEED)),
        ]
    )
    scores = cross_val_predict(
        pipeline, reference[MODEL_FEATURES], y, cv=5, method="predict_proba"
    )[:, 1]
    return round(float(roc_auc_score(y, scores)), 4)


def build_counterfactual(categorical: list[str], numeric: list[str]) -> Pipeline:
    """O mesmo modelo do ML-001 com outro conjunto de colunas, para experimentos contrafactuais.

    Recebe: as colunas categóricas e numéricas.
    Faz: monta o pipeline com o mesmo pré-processamento e o mesmo modelo, ainda sem treinar.
    Devolve: o Pipeline. Serve só para responder "e se o modelo usasse (ou não) tal coluna?";
        nunca é usado para decidir crédito.
    """
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEED)
    return Pipeline([("preprocess", _preprocess(categorical, numeric)), ("model", model)])


# Contrafactuais do ADR-004: opção A (com SEX e MARRIAGE) e opção C (também sem AGE).
COUNTERFACTUALS = {
    "com_sexo_e_estado_civil": ([*MODEL_CATEGORICAL, *SENSITIVE_EXCLUDED], MODEL_NUMERIC),
    "sem_idade": (MODEL_CATEGORICAL, [c for c in MODEL_NUMERIC if c != "AGE"]),
}


def _preprocess(categorical: list[str], numeric: list[str]) -> ColumnTransformer:
    """Mesmo pré-processamento do ML-001: one-hot nos códigos, escala nos números."""
    return ColumnTransformer(
        [
            (
                "cat",
                OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=0.01),
                categorical,
            ),
            ("num", StandardScaler(), numeric),
        ]
    )
