"""OBS-002: réguas de alerta calibradas para o tamanho do lote semanal.

O que faz: (1) calibra os limites de alerta em amostras SEM drift da Produção-base, no mesmo
tamanho do lote semanal; (2) aplica as regras a um lote e diz quais alertas disparam.
Por que existe: as réguas do DRIFT-002 valiam para lotes de 9.000 linhas e davam alarme falso em
lotes menores (comentário do PMF4-20). Um alerta que dispara toda semana deixa de ser lido.
Onde entra no fluxo: scripts/calibrate_alerts.py grava os limites; run_weekly_pipeline.py os usa.

As três correções herdadas:
1. KS: com 20 colunas testadas, p < 0,05 em alguma delas é quase garantido por acaso
   (comparações múltiplas). Agora: Bonferroni (0,05 / 20) E um tamanho de efeito mínimo D.
2. AUC: o piso vem do bootstrap da Produção-base no mesmo n do lote (percentil 2,5%).
3. Taxa de default: o PSI do alvo não vê 22% virar 27%. Agora: alerta quando a taxa sai do
   intervalo de 95% do bootstrap no mesmo n.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from credit_risk_observability.config import CATEGORICAL_COLUMNS, FEATURE_COLUMNS, TARGET
from credit_risk_observability.model.predict import predict_proba

# Limite do card (PMF4-20) e da literatura de crédito: PSI acima de 0,25 é mudança grande.
PSI_LIMIT = 0.25
FAMILY_ALPHA = 0.05  # chance aceita de alarme falso no conjunto das colunas, não em cada uma
TARGET_FALSE_ALARM = 0.05  # meta: no máximo 1 alarme falso a cada 20 semanas sem drift
KS_FEATURES = [column for column in FEATURE_COLUMNS if column not in CATEGORICAL_COLUMNS]
KS_P_VALUE_LIMIT = FAMILY_ALPHA / len(KS_FEATURES)  # Bonferroni: 0,05 / 20 = 0,0025


@dataclass(frozen=True)
class AlertThresholds:
    """Os limites calibrados, prontos para virar JSON versionado."""

    batch_size: int  # tamanho do lote para o qual os limites valem
    calibration_samples: int  # amostras usadas para calibrar
    holdout_samples: int  # amostras separadas, só para medir o alarme falso depois
    psi_limit: float
    ks_p_value_limit: float
    ks_d_min: float  # tamanho de efeito mínimo: diferença máxima entre as duas curvas acumuladas
    auc_floor: float
    default_rate_low: float
    default_rate_high: float
    # Alarme falso medido nas amostras de holdout, por regra. Exemplo: {"ks": 0.03}.
    holdout_false_alarm: dict

    def to_json(self, path: Path) -> None:
        """Grava os limites em JSON, com indentação, para ler e versionar."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "AlertThresholds":
        """Lê os limites gravados por to_json."""
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def ks_by_feature(reference: pd.DataFrame, batch: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Teste KS de duas amostras em cada feature numérica.

    Recebe: a Referência e o lote.
    Faz: compara as distribuições acumuladas de cada coluna. D é a maior distância vertical entre
        as duas curvas (0 = iguais, 1 = nada em comum); o p-valor diz se D poderia ser acaso.
    Devolve: {"LIMIT_BAL": {"d": 0.12, "p_value": 0.0001}, ...}.
    """
    result = {}
    for column in KS_FEATURES:
        test = stats.ks_2samp(reference[column], batch[column])
        result[column] = {"d": float(test.statistic), "p_value": float(test.pvalue)}
    return result


def ks_alert_features(ks: dict[str, dict[str, float]], p_limit: float, d_min: float) -> list[str]:
    """Features que passam nas duas condições: significativa (Bonferroni) e grande (D mínimo).

    Recebe: o resultado de ks_by_feature e os dois limites.
    Faz: exige as duas, porque com milhares de linhas até uma diferença irrelevante fica
        "significativa", e com poucas linhas uma diferença grande pode ser só sorte.
    Devolve: os nomes. Exemplo: p = 0,001 e D = 0,02 com D mínimo 0,05 não entra.
    """
    return [
        column
        for column, values in ks.items()
        if values["p_value"] < p_limit and values["d"] > d_min
    ]


def _max_significant_d(ks: dict[str, dict[str, float]], p_limit: float) -> float:
    """Maior D entre as features significativas pelo Bonferroni; 0 se nenhuma for."""
    return max((v["d"] for v in ks.values() if v["p_value"] < p_limit), default=0.0)


def _sample_stats(
    reference: pd.DataFrame, sample: pd.DataFrame, model: Pipeline
) -> dict[str, float | dict]:
    """AUC, taxa de default e KS de uma amostra: o que a calibração precisa de cada uma."""
    return {
        "auc": float(roc_auc_score(sample[TARGET], predict_proba(model, sample))),
        "default_rate": float(sample[TARGET].mean()),
        "ks": ks_by_feature(reference, sample),
    }


def calibrate(
    reference: pd.DataFrame,
    production_base: pd.DataFrame,
    model: Pipeline,
    batch_size: int,
    calibration_samples: int = 200,
    holdout_samples: int = 200,
    seed: int = 42,
) -> AlertThresholds:
    """Calibra os limites em amostras sem drift e mede o alarme falso em amostras novas.

    Recebe: a Referência, a Produção-base (que não tem drift), o modelo, o tamanho do lote, quantas
        amostras usar em cada parte e a seed.
    Faz: sorteia amostras de batch_size linhas da Produção-base (sem reposição dentro da amostra).
        Nas de calibração, tira o piso da AUC (percentil 2,5), o intervalo da taxa de default
        (percentis 2,5 e 97,5) e o D mínimo do KS (percentil 95 do maior D significativo). Nas de
        holdout, que a calibração não viu, conta quantas vezes cada regra dispararia.
        Nunca usa lotes com drift: calibrar neles seria ajustar a régua à resposta.
    Devolve: os limites. Exemplo: com 2.000 linhas, o piso da AUC fica perto de 0,69.
    """
    rng = np.random.default_rng(seed)
    total = calibration_samples + holdout_samples
    all_stats = [
        _sample_stats(
            reference,
            production_base.sample(n=batch_size, random_state=int(rng.integers(2**31))),
            model,
        )
        for _ in range(total)
    ]
    calibration, holdout = all_stats[:calibration_samples], all_stats[calibration_samples:]

    aucs = np.array([s["auc"] for s in calibration])
    rates = np.array([s["default_rate"] for s in calibration])
    max_d = np.array([_max_significant_d(s["ks"], KS_P_VALUE_LIMIT) for s in calibration])

    auc_floor = float(np.percentile(aucs, 2.5))
    rate_low, rate_high = (float(x) for x in np.percentile(rates, [2.5, 97.5]))
    d_min = float(np.percentile(max_d, 100 * (1 - TARGET_FALSE_ALARM)))

    def rate(rule) -> float:
        return float(np.mean([rule(s) for s in holdout]))

    holdout_false_alarm = {
        "ks": rate(lambda s: bool(ks_alert_features(s["ks"], KS_P_VALUE_LIMIT, d_min))),
        # A régua antiga, só para comparação: p < 0,05 em qualquer feature, sem D mínimo.
        "ks_regua_antiga": rate(lambda s: any(v["p_value"] < 0.05 for v in s["ks"].values())),
        "auc": rate(lambda s: s["auc"] < auc_floor),
        "taxa_default": rate(lambda s: not rate_low <= s["default_rate"] <= rate_high),
    }

    return AlertThresholds(
        batch_size=batch_size,
        calibration_samples=calibration_samples,
        holdout_samples=holdout_samples,
        psi_limit=PSI_LIMIT,
        ks_p_value_limit=KS_P_VALUE_LIMIT,
        ks_d_min=round(d_min, 4),
        auc_floor=round(auc_floor, 4),
        default_rate_low=round(rate_low, 4),
        default_rate_high=round(rate_high, 4),
        holdout_false_alarm=holdout_false_alarm,
    )


def evaluate_alerts(
    thresholds: AlertThresholds,
    psi_by_feature: dict[str, float],
    ks: dict[str, dict[str, float]],
    auc: float,
    default_rate: float,
) -> dict[str, list[str] | bool]:
    """Aplica as quatro regras a um lote.

    Recebe: os limites, o PSI de cada feature (do Evidently), o KS de cada feature (de
        ks_by_feature), a AUC e a taxa de default do lote.
    Faz: decide cada regra separadamente, para o alerta dizer O QUE mudou, e não só "algo mudou".
    Devolve: {"psi": [features], "ks": [features], "auc": bool, "taxa_default": bool,
        "drift_alert": bool, "algum_alerta": bool}. drift_alert é a regra do card (PSI > 0,25).
    """
    psi_features = [f for f, value in psi_by_feature.items() if value > thresholds.psi_limit]
    ks_features = ks_alert_features(ks, thresholds.ks_p_value_limit, thresholds.ks_d_min)
    auc_alert = auc < thresholds.auc_floor
    rate_alert = not thresholds.default_rate_low <= default_rate <= thresholds.default_rate_high
    return {
        "psi": psi_features,
        "ks": ks_features,
        "auc": auc_alert,
        "taxa_default": rate_alert,
        "drift_alert": bool(psi_features),
        "algum_alerta": bool(psi_features or ks_features or auc_alert or rate_alert),
    }
