"""Simula mudanças econômicas na Produção-base, de forma controlada (DRIFT-001).

O que faz: gera lotes com dois tipos de mudança.
- Data drift: as entradas (X) mudam, e o resultado (y) não. História: inflação sobe as faturas e o
  banco corta os limites; o cliente continua pagando como antes.
- Concept drift: as entradas não mudam, e o resultado muda. História: clientes com fatura alta
  passam a dar default (calote) com mais frequência.

Por que existe: como sabemos exatamente o que foi alterado, temos a "resposta certa" para conferir
se o detector de drift do DRIFT-002 acerta. É como testar um alarme de incêndio com um fósforo.

Onde entra no fluxo: scripts/make_drift_batch.py chama estas funções, valida o lote no contrato e
salva. Estas funções não leem nem gravam arquivo, o que permite testá-las com dados pequenos.

Rótulo é o valor da coluna default de um cliente: 1 se deu calote, 0 se não deu.
Intensidade é um número de 0 a 1: 0 não muda nada e 1 aplica a mudança cheia. O OBS-002 vai usá-la
para gerar várias "semanas" com drift crescente, sem reescrever código.
"""

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from credit_risk_observability.config import BILL_COLUMNS, TARGET

LIMIT_COLUMN = "LIMIT_BAL"
SUBGROUP_COLUMN = "BILL_AMT1"  # fatura mais recente: define quem é o "cliente de fatura alta"


@dataclass(frozen=True)
class DataDriftParams:
    """Fatores do data drift quando a intensidade é 1. Decisão registrada na spec do DRIFT-001."""

    bill_factor: float = 1.25  # faturas 25% mais caras
    limit_factor: float = 0.75  # limites 25% menores


@dataclass(frozen=True)
class ConceptDriftParams:
    """Define o subgrupo do concept drift: 0,75 significa o quartil mais alto de fatura."""

    subgroup_quantile: float = 0.75


@dataclass(frozen=True)
class ConceptDriftPlan:
    """A conta do concept drift, antes de trocar qualquer rótulo. Só traz números agregados."""

    bill_cutoff: float  # fatura mínima para entrar no subgrupo
    subgroup_size: int  # N: clientes no subgrupo
    subgroup_defaults: int  # D: clientes do subgrupo que deram default
    subgroup_default_rate: float  # r = D / N
    fraction_of_non_defaults: float  # f = D / (N - D)
    labels_to_flip_at_full: int  # rótulos a trocar para dobrar a taxa (é igual a D)


# Valores padrão: as decisões do DRIFT-001, usados quando ninguém pede outros fatores.
DEFAULT_DATA_DRIFT = DataDriftParams()
DEFAULT_CONCEPT_DRIFT = ConceptDriftParams()


def validate_intensity(intensity: float) -> None:
    """Recusa intensidades fora da escala.

    Recebe: a intensidade pedida.
    Faz: levanta ValueError se ela não estiver entre 0 e 1 (NaN também é recusado).
    Devolve: nada.
    """
    # Sem o isnan, NaN passaria: qualquer comparação com NaN dá falso, e o lote sairia cheio de NaN.
    if math.isnan(intensity) or not 0 <= intensity <= 1:
        raise ValueError(f"A intensidade precisa estar entre 0 e 1; recebi {intensity}")


def _interpolate_factor(full_factor: float, intensity: float) -> float:
    """Calcula o fator de uma intensidade por interpolação linear.

    Recebe: o fator cheio (intensidade 1) e a intensidade.
    Faz: anda em linha reta de 1 (nada muda) até o fator cheio.
    Devolve: o fator. Exemplo: fator cheio 0,75 com intensidade 0,5 dá 0,875.
    """
    return 1 + intensity * (full_factor - 1)


def _scale_to_int(column: pd.Series, factor: float) -> pd.Series:
    """Multiplica uma coluna inteira e mantém o resultado inteiro.

    Recebe: a coluna e o fator.
    Faz: multiplica e arredonda. O contrato exige int64, então um float aqui reprovaria o lote.
    Devolve: a coluna nova. Exemplo: 15.000 × 0,75 dá 11.250.
    """
    return np.rint(column * factor).astype("int64")


def apply_data_drift(
    base: pd.DataFrame, intensity: float, params: DataDriftParams = DEFAULT_DATA_DRIFT
) -> tuple[pd.DataFrame, dict]:
    """Gera o lote de data drift: faturas sobem, limite cai e o default fica igual.

    Recebe: a Produção-base, a intensidade (0 a 1) e os fatores cheios.
    Faz: aplica o mesmo fator nas seis faturas, para manter a correlação entre elas (se cada uma
        subisse de um jeito, o histórico do cliente deixaria de fazer sentido). Faturas negativas,
        que são crédito a favor do cliente, também são multiplicadas. Não usa sorteio.
    Devolve: o lote e um dicionário com os fatores e os rótulos trocados (sempre 0).
        Exemplo: com intensidade 1, um limite de 100.000 vira 75.000.
    """
    validate_intensity(intensity)
    bill_factor = _interpolate_factor(params.bill_factor, intensity)
    limit_factor = _interpolate_factor(params.limit_factor, intensity)

    # copy(): a Produção-base é o grupo de controle e nunca pode ser alterada.
    batch = base.copy()
    for bill_column in BILL_COLUMNS:
        batch[bill_column] = _scale_to_int(base[bill_column], bill_factor)
    batch[LIMIT_COLUMN] = _scale_to_int(base[LIMIT_COLUMN], limit_factor)

    return batch, {"bill_factor": bill_factor, "limit_factor": limit_factor, "labels_flipped": 0}


def plan_concept_drift(
    base: pd.DataFrame, params: ConceptDriftParams = DEFAULT_CONCEPT_DRIFT
) -> ConceptDriftPlan:
    """Calcula quantos rótulos trocar para dobrar a taxa de default do subgrupo.

    Recebe: a Produção-base e o quantil que define o subgrupo.
    Faz: com N clientes no subgrupo e D com default, a taxa é D / N. Para chegar a 2D / N, é preciso
        trocar exatamente D rótulos, entre os N - D clientes sem default.
    Devolve: o plano. Exemplo: N = 4 e D = 1 dão taxa de 25%, fração de 1/3 e 1 rótulo a trocar,
        e a taxa sobe para 2/4 = 50%.
    """
    bill_cutoff = float(base[SUBGROUP_COLUMN].quantile(params.subgroup_quantile))
    in_subgroup = base[SUBGROUP_COLUMN] >= bill_cutoff
    subgroup_size = int(in_subgroup.sum())
    subgroup_defaults = int(base.loc[in_subgroup, TARGET].sum())
    subgroup_non_defaults = subgroup_size - subgroup_defaults

    # Trocaria 0 rótulos: o lote pareceria ter drift sem ter mudado nada (sucesso vazio).
    if subgroup_defaults == 0:
        raise ValueError("Subgrupo sem nenhum default: não há taxa para dobrar")
    # Acima de 50%, faltam clientes sem default para chegar ao dobro.
    if subgroup_defaults > subgroup_non_defaults:
        raise ValueError(
            f"Taxa do subgrupo acima de 50% ({subgroup_defaults}/{subgroup_size}): "
            "não dá para dobrar"
        )

    return ConceptDriftPlan(
        bill_cutoff=bill_cutoff,
        subgroup_size=subgroup_size,
        subgroup_defaults=subgroup_defaults,
        subgroup_default_rate=subgroup_defaults / subgroup_size,
        fraction_of_non_defaults=subgroup_defaults / subgroup_non_defaults,
        labels_to_flip_at_full=subgroup_defaults,
    )


def apply_concept_drift(
    base: pd.DataFrame,
    intensity: float,
    seed: int,
    params: ConceptDriftParams = DEFAULT_CONCEPT_DRIFT,
) -> tuple[pd.DataFrame, dict]:
    """Gera o lote de concept drift: as entradas ficam iguais, e alguns rótulos passam a default.

    Recebe: a Produção-base, a intensidade (0 a 1), a seed (número que fixa o sorteio) e o subgrupo.
    Faz: embaralha uma única vez os clientes do subgrupo sem default e troca os primeiros da lista.
        Como a ordem depende só da seed, quem muda em 0,3 continua mudando em 0,6, e a evolução
        entre "semanas" mostra o drift, não a sorte do sorteio.
    Devolve: o lote e um dicionário com o plano e os rótulos trocados.
        Exemplo: com D = 450, intensidade 1 troca 450 rótulos, e intensidade 0,5 troca 225.
    """
    validate_intensity(intensity)
    plan = plan_concept_drift(base, params)
    labels_to_flip = round(intensity * plan.labels_to_flip_at_full)

    in_subgroup = base[SUBGROUP_COLUMN] >= plan.bill_cutoff
    # Posições, e não rótulos do índice: funciona mesmo se o índice do DataFrame tiver repetição.
    candidate_positions = np.flatnonzero(in_subgroup & (base[TARGET] == 0))
    shuffled_positions = np.random.default_rng(seed).permutation(candidate_positions)
    chosen_positions = shuffled_positions[:labels_to_flip]

    batch = base.copy()
    batch.iloc[chosen_positions, batch.columns.get_loc(TARGET)] = 1

    details = {
        # Fator 1 deixa explícito no manifesto que nenhuma entrada mudou neste cenário.
        "bill_factor": 1.0,
        "limit_factor": 1.0,
        "labels_flipped": labels_to_flip,
        "bill_cutoff": plan.bill_cutoff,
        "subgroup_size": plan.subgroup_size,
        "subgroup_defaults_before": plan.subgroup_defaults,
        "subgroup_default_rate_before": plan.subgroup_default_rate,
        "subgroup_default_rate_after": (plan.subgroup_defaults + labels_to_flip)
        / plan.subgroup_size,
        "fraction_of_non_defaults_at_full": plan.fraction_of_non_defaults,
        "overall_default_rate_before": float(base[TARGET].mean()),
        "overall_default_rate_after": float(batch[TARGET].mean()),
    }
    return batch, details
