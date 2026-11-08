"""Testes do OBS-002: réguas de alerta, calibração, registro no MLflow e semanas simuladas.

O que faz: testa as regras com números feitos à mão, a calibração e o pipeline semanal inteiro
em dados sintéticos, com log, banco do MLflow e pastas temporários.
Por que existe: um alerta errado custa caro nos dois sentidos: o falso cansa, o perdido engana.
Onde entra no fluxo: roda no pytest; não toca em data/, reports/, logs/ nem mlflow.db do projeto.
"""

import importlib.util
import json
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import (
    BILL_COLUMNS,
    FEATURE_COLUMNS,
    ID_COLUMN,
    MODEL_FEATURES,
    PAY_AMOUNT_COLUMNS,
    PAY_STATUS_COLUMNS,
    TARGET,
)
from credit_risk_observability.model.train import build_pipeline
from credit_risk_observability.monitoring import events
from credit_risk_observability.monitoring.alerts import (
    KS_P_VALUE_LIMIT,
    AlertThresholds,
    calibrate,
    evaluate_alerts,
    ks_alert_features,
)
from credit_risk_observability.monitoring.tracking import (
    PipelineRun,
    log_pipeline_run,
    setup_tracking,
)

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    """Importa um arquivo de scripts/, que não faz parte do pacote instalado."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_clients(n: int, seed: int) -> pd.DataFrame:
    """Clientes sintéticos válidos no contrato, com default ligado a PAY_0 e taxa perto de 25%."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({ID_COLUMN: np.arange(1, n + 1) + seed * 1_000_000})
    df["LIMIT_BAL"] = rng.integers(1, 50, n) * 10_000
    df["SEX"] = rng.choice([1, 2], n)
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["MARRIAGE"] = rng.choice([1, 2], n)
    df["AGE"] = rng.integers(21, 70, n)
    for col in PAY_STATUS_COLUMNS:
        df[col] = rng.integers(-2, 5, n)
    for col in BILL_COLUMNS:
        df[col] = rng.integers(-5_000, 200_000, n)
    for col in PAY_AMOUNT_COLUMNS:
        df[col] = rng.integers(0, 20_000, n)
    default_chance = 1 / (1 + np.exp(-2 * (df["PAY_0"] - 2)))
    df[TARGET] = (rng.random(n) < default_chance).astype("int64")
    return df[[ID_COLUMN, *FEATURE_COLUMNS, TARGET]]


def make_thresholds(batch_size: int = 200, **overrides) -> AlertThresholds:
    """Limites feitos à mão, para testar as regras sem depender da calibração."""
    values = {
        "batch_size": batch_size,
        "calibration_samples": 10,
        "holdout_samples": 10,
        "psi_limit": 0.25,
        "ks_p_value_limit": KS_P_VALUE_LIMIT,
        "ks_d_min": 0.05,
        "auc_floor": 0.69,
        "default_rate_low": 0.20,
        "default_rate_high": 0.24,
        "holdout_false_alarm": {},
    }
    return AlertThresholds(**{**values, **overrides})


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Evita que os testes escrevam no log real do pipeline."""
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")


@pytest.fixture(scope="module")
def workspace(tmp_path_factory) -> dict:
    """Referência, Produção-base e modelo sintéticos, criados uma vez: treinar custa tempo."""
    root = tmp_path_factory.mktemp("monitoring")
    reference = make_clients(3_000, seed=1)
    base = make_clients(1_000, seed=2)
    model = build_pipeline().fit(reference[MODEL_FEATURES], reference[TARGET])
    paths = {"root": root}
    for name, df in (("reference", reference), ("base", base)):
        paths[name] = root / f"{name}.parquet"
        df.to_parquet(paths[name], index=False)
    paths["model"] = root / "model.joblib"
    joblib.dump(model, paths["model"])
    return paths


# --- Regras -----------------------------------------------------------------------------------


def test_ks_alert_needs_significance_and_effect_size():
    """Significativa mas pequena não alerta; grande mas não significativa também não."""
    ks = {
        "A": {"p_value": 0.0001, "d": 0.20},  # as duas condições: alerta
        "B": {"p_value": 0.0001, "d": 0.01},  # significativa, efeito irrelevante
        "C": {"p_value": 0.01, "d": 0.20},  # passaria na régua antiga (0,05), não no Bonferroni
    }

    assert ks_alert_features(ks, KS_P_VALUE_LIMIT, d_min=0.05) == ["A"]


def test_bonferroni_limit_is_family_alpha_over_20_features():
    """0,05 dividido pelas 20 features numéricas: a conta que corrige as comparações múltiplas."""
    assert KS_P_VALUE_LIMIT == pytest.approx(0.0025)


@pytest.mark.parametrize(
    ("auc", "rate", "auc_alert", "rate_alert"),
    [
        (0.70, 0.22, False, False),  # dentro de tudo
        (0.68, 0.22, True, False),  # AUC abaixo do piso
        (0.70, 0.27, False, True),  # 27% de default: o caso que o PSI do alvo não via
        (0.70, 0.19, False, True),  # queda também é alerta: default sumir é suspeito
    ],
)
def test_performance_and_default_rate_rules(auc, rate, auc_alert, rate_alert):
    """AUC pelo piso, taxa de default pelo intervalo dos dois lados."""
    alerts = evaluate_alerts(make_thresholds(), {"LIMIT_BAL": 0.01}, {}, auc, rate)

    assert alerts["auc"] is auc_alert
    assert alerts["taxa_default"] is rate_alert
    assert alerts["algum_alerta"] is (auc_alert or rate_alert)
    assert alerts["drift_alert"] is False


def test_drift_alert_is_psi_above_limit():
    """drift_alert, a tag do card, liga só com PSI acima de 0,25; igual a 0,25 não conta."""
    psi = {"LIMIT_BAL": 0.30, "AGE": 0.25, "SEX": 0.01}

    alerts = evaluate_alerts(make_thresholds(), psi, {}, 0.70, 0.22)

    assert alerts["psi"] == ["LIMIT_BAL"]
    assert alerts["drift_alert"] is True


# --- Calibração -------------------------------------------------------------------------------


def test_calibration_uses_only_no_drift_samples_and_round_trips(workspace, tmp_path):
    """Limites coerentes, alarme falso medido no holdout e JSON que volta igual."""
    reference = pd.read_parquet(workspace["reference"])
    base = pd.read_parquet(workspace["base"])
    model = joblib.load(workspace["model"])

    thresholds = calibrate(
        reference, base, model, batch_size=300, calibration_samples=30, holdout_samples=30
    )

    assert thresholds.batch_size == 300
    assert 0.5 < thresholds.auc_floor < 1
    assert thresholds.default_rate_low < base[TARGET].mean() < thresholds.default_rate_high
    assert set(thresholds.holdout_false_alarm) == {"ks", "ks_regua_antiga", "auc", "taxa_default"}
    path = tmp_path / "thresholds.json"
    thresholds.to_json(path)
    assert AlertThresholds.from_json(path) == thresholds


# --- MLflow -----------------------------------------------------------------------------------


def test_log_pipeline_run_writes_params_metrics_tags_and_skips_none(tmp_path):
    """Métrica None é pulada (não vira zero no gráfico); tags booleanas viram texto."""
    setup_tracking(f"sqlite:///{tmp_path / 'mlflow.db'}", "teste", tmp_path / "artifacts")
    artifact = tmp_path / "eventos.jsonl"
    artifact.write_text("{}\n", encoding="utf-8")
    run = PipelineRun(
        name="semana_1",
        run_id="abc123",
        step=1,
        params={"lote": "semana_1", "intensidade_drift": None},
        metrics={"roc_auc": 0.71, "psi_max": None},
        tags={"drift_alert": True},
        artifacts=[artifact],
    )

    mlflow_id = log_pipeline_run(run)

    saved = mlflow.get_run(mlflow_id)
    assert saved.data.params == {"lote": "semana_1"}
    assert saved.data.metrics == {"roc_auc": 0.71}
    assert saved.data.tags["drift_alert"] == "true"
    assert saved.data.tags["pipeline_run_id"] == "abc123"
    artifacts = [a.path for a in mlflow.MlflowClient().list_artifacts(mlflow_id)]
    assert artifacts == ["eventos.jsonl"]


# --- Semanas simuladas ------------------------------------------------------------------------


def test_build_weeks_are_disjoint_with_growing_drift(workspace):
    """Nenhum cliente em duas semanas, drift crescente e a corrompida por último."""
    script = load_script("run_weekly_pipeline")
    base = pd.read_parquet(workspace["base"])

    weeks = script.build_weeks(base, batch_size=200, seed=42)

    drift_weeks = weeks[:-1]
    assert [w.intensity for w in drift_weeks] == list(script.WEEK_INTENSITIES)
    ids = [set(w.batch[ID_COLUMN]) for w in drift_weeks]
    assert all(not (a & b) for i, a in enumerate(ids) for b in ids[i + 1 :])
    flipped = [w.labels_flipped for w in drift_weeks]
    assert flipped == sorted(flipped) and flipped[0] == 0 < flipped[-1]
    assert weeks[-1].intensity is None


def test_weekly_pipeline_end_to_end(workspace, tmp_path):
    """5 semanas: 4 runs com sucesso e relatório, 1 barrada; log e MLflow com o mesmo run_id."""
    thresholds_path = tmp_path / "thresholds.json"
    make_thresholds(batch_size=200).to_json(thresholds_path)
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"

    code = load_script("run_weekly_pipeline").main(
        ["--batch-size", "200"],
        thresholds_path=thresholds_path,
        output_dir=tmp_path / "weekly",
        reference_path=workspace["reference"],
        base_path=workspace["base"],
        model_path=workspace["model"],
        tracking_uri=tracking_uri,
    )

    assert code == 0
    runs = mlflow.search_runs(
        experiment_ids=[mlflow.get_experiment_by_name("credit-risk-monitoramento").experiment_id]
    )
    assert len(runs) == 5
    status = dict(zip(runs["tags.mlflow.runName"], runs["tags.status"], strict=True))
    assert status["semana_5_corrompida"] == "falha"
    assert sum(value == "sucesso" for value in status.values()) == 4

    log = [json.loads(line) for line in events.PIPELINE_LOG_PATH.read_text().splitlines()]
    assert len(log) == 4 * 2 + 1  # 4 semanas com validação e drift, 1 só com validação
    assert set(runs["tags.pipeline_run_id"]) == {event["run_id"] for event in log}
    assert (tmp_path / "weekly" / "semana_4" / "drift_report.html").exists()


def test_weekly_pipeline_refuses_thresholds_for_another_batch_size(workspace, tmp_path):
    """Régua calibrada para um tamanho, aplicada a outro: é o erro que este card corrige."""
    thresholds_path = tmp_path / "thresholds.json"
    make_thresholds(batch_size=2_000).to_json(thresholds_path)

    with pytest.raises(ValueError, match="calibrados para 2000"):
        load_script("run_weekly_pipeline").main(
            ["--batch-size", "200"],
            thresholds_path=thresholds_path,
            reference_path=workspace["reference"],
            base_path=workspace["base"],
            model_path=workspace["model"],
            tracking_uri=f"sqlite:///{tmp_path / 'mlflow.db'}",
        )
