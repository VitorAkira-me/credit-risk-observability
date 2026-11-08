"""GOV-004: experimentos de intervenção para separar causa de correlação na degradação.

O que faz: aplica cada tipo de drift SOZINHO, em doses crescentes, na Produção-base, e mede o que
acontece com o modelo (AUC) e com o negócio (calote aprovado, bom cliente negado).
Por que existe: nas semanas simuladas (OBS-002), o PSI de LIMIT_BAL e a queda de AUC subiram
juntos, porque os dois drifts foram aplicados ao mesmo tempo. Olhando só a série, não dá para dizer
qual causou a queda. Intervindo em um de cada vez, dá: se a AUC cai com a dose de um e não se move
com a dose do outro, a causa está isolada. É o mesmo raciocínio de um teste A/B.
Onde entra no fluxo: scripts/run_causal_analysis.py.

Dose-resposta: se a causa é real, mais dose dá mais efeito, de forma gradual (e dose zero, nenhum).
"""

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from credit_risk_observability.config import DECISION_THRESHOLD, SEED, TARGET
from credit_risk_observability.drift.scenarios import apply_concept_drift, apply_data_drift
from credit_risk_observability.model.predict import predict_proba

DOSES = (0.0, 0.25, 0.5, 0.75, 1.0)
SCENARIOS = ("data_drift", "concept_drift")


def business_impact(df: pd.DataFrame, scores: np.ndarray) -> dict[str, float]:
    """O que a decisão do modelo custa ao negócio neste lote.

    Recebe: os clientes (com o resultado real) e os scores do modelo.
    Faz: aprova quem tem score abaixo do limiar e conta os dois erros que custam dinheiro:
        calote aprovado (o banco empresta e não recebe) e bom cliente negado (o banco perde a
        receita de quem pagaria). A exposição soma o limite de crédito dos calotes aprovados.
    Devolve: as contagens e a exposição em NT$ (dólar de Taiwan, a moeda do dataset).
    """
    approved = scores < DECISION_THRESHOLD
    default = df[TARGET].to_numpy() == 1
    bad_approved = approved & default
    return {
        "taxa_aprovacao": round(float(approved.mean()), 4),
        "calote_aprovado": int(bad_approved.sum()),
        "bom_cliente_negado": int((~approved & ~default).sum()),
        "exposicao_calote_aprovado": int(df.loc[bad_approved, "LIMIT_BAL"].sum()),
    }


def _apply(scenario: str, base: pd.DataFrame, dose: float) -> pd.DataFrame:
    """Aplica UM cenário de drift, com a dose pedida, e devolve o lote."""
    if scenario == "data_drift":
        return apply_data_drift(base, dose)[0]
    return apply_concept_drift(base, dose, SEED)[0]


def dose_response(base: pd.DataFrame, model: Pipeline, doses=DOSES) -> list[dict]:
    """Mede modelo e negócio em cada dose de cada drift, aplicado sozinho.

    Recebe: a Produção-base (sem drift), o modelo e as doses (0 = nada, 1 = cenário cheio).
    Faz: para cada cenário e dose, gera o lote, pontua e mede. O mesmo modelo, o mesmo conjunto de
        clientes: só a intervenção muda, então a diferença no resultado é efeito dela.
    Devolve: uma linha por (cenário, dose) com AUC, taxa de default e impacto no negócio.
    """
    rows = []
    for scenario in SCENARIOS:
        for dose in doses:
            batch = _apply(scenario, base, dose)
            scores = predict_proba(model, batch)
            rows.append(
                {
                    "cenario": scenario,
                    "dose": dose,
                    "roc_auc": round(float(roc_auc_score(batch[TARGET], scores)), 4),
                    "taxa_default": round(float(batch[TARGET].mean()), 4),
                    **business_impact(batch, scores),
                }
            )
    return rows
