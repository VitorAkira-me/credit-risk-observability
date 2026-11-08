"""OBS-002: calibra as réguas de alerta para o tamanho do lote semanal.

O que faz: sorteia amostras SEM drift da Produção-base, tira delas os limites de alerta e mede o
alarme falso em amostras novas (holdout). Grava reports/monitoring/alert_thresholds.json.
Por que existe: as réguas do DRIFT-002 valiam para 9.000 linhas; o lote semanal tem 2.000.
Onde entra no fluxo: roda uma vez, depois de train_baseline.py e antes de run_weekly_pipeline.py.

Uso:
    uv run python scripts/calibrate_alerts.py
    uv run python scripts/calibrate_alerts.py --batch-size 1000

Exit code (o número que o programa devolve ao terminar): 0 = limites gravados; 1 = alguma regra
passou da meta de alarme falso no holdout (5%, com folga para o ruído de 200 amostras).
"""

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd

from credit_risk_observability.config import (
    ALERT_THRESHOLDS_PATH,
    MODEL_PATH,
    PRODUCTION_BASE_PATH,
    REFERENCE_PATH,
    WEEKLY_BATCH_SIZE,
)
from credit_risk_observability.model.predict import load_model
from credit_risk_observability.monitoring.alerts import calibrate

logger = logging.getLogger("calibrate_alerts")

# 200 amostras medem um alarme de 5% com erro padrão de cerca de 1,5 ponto: 8% ainda é ruído.
MAX_HOLDOUT_FALSE_ALARM = 0.08
RULES_WITH_TARGET = ("ks", "auc", "taxa_default")


def main(argv: list[str] | None = None, output_path: Path = ALERT_THRESHOLDS_PATH) -> int:
    """Calibra e grava os limites.

    Recebe: os argumentos da linha de comando e o caminho de saída (temporário nos testes).
    Faz: calibra, imprime o alarme falso de cada regra no holdout e grava o JSON.
    Devolve: o exit code.
    """
    parser = argparse.ArgumentParser(description="Calibra as réguas de alerta (OBS-002)")
    parser.add_argument("--batch-size", type=int, default=WEEKLY_BATCH_SIZE)
    parser.add_argument("--samples", type=int, default=200, help="amostras de cada parte")
    args = parser.parse_args(argv)

    thresholds = calibrate(
        pd.read_parquet(REFERENCE_PATH),
        pd.read_parquet(PRODUCTION_BASE_PATH),
        load_model(MODEL_PATH),
        batch_size=args.batch_size,
        calibration_samples=args.samples,
        holdout_samples=args.samples,
    )
    thresholds.to_json(output_path)

    print(
        f"Limites para lotes de {thresholds.batch_size} linhas:\n"
        f"  AUC mínima: {thresholds.auc_floor}\n"
        f"  Taxa de default: de {thresholds.default_rate_low} a {thresholds.default_rate_high}\n"
        f"  KS: p < {thresholds.ks_p_value_limit} e D > {thresholds.ks_d_min}\n"
        f"  PSI: > {thresholds.psi_limit}\n"
        f"Alarme falso no holdout: {thresholds.holdout_false_alarm}\n"
        f"Gravado em {output_path.name}"
    )
    too_noisy = [
        rule
        for rule in RULES_WITH_TARGET
        if thresholds.holdout_false_alarm[rule] > MAX_HOLDOUT_FALSE_ALARM
    ]
    if too_noisy:
        print(f"Regras acima da meta de alarme falso: {too_noisy}")
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    sys.exit(main())
