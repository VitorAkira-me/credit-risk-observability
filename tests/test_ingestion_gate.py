import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import FEATURE_COLUMNS, ID_COLUMN, TARGET
from credit_risk_observability.contracts.corrupt import DEFECTS, inject_defects
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.monitoring import events

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_population() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    n = 500
    df = pd.DataFrame({ID_COLUMN: np.arange(1, n + 1)})
    for col in FEATURE_COLUMNS:
        df[col] = 0
    df["LIMIT_BAL"] = rng.integers(10, 100, n) * 1_000
    df["SEX"] = rng.choice([1, 2], n)
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["MARRIAGE"] = rng.choice([1, 2], n)
    df["AGE"] = rng.integers(21, 70, n)
    df[TARGET] = rng.choice([0, 1], n)
    return df


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")


def test_validation_finds_exactly_the_injected_defects(clean_population):
    batch, expected = inject_defects(clean_population, batch_size=200, seed=42)

    result = validate_batch(batch)

    assert len(batch) == 200 + DEFECTS["duplicated_rows"]
    assert not result.passed
    assert result.failures_by_rule == expected


def test_gate_returns_0_and_logs_pass(clean_population, tmp_path):
    path = tmp_path / "clean.parquet"
    clean_population.to_parquet(path)

    code = load_script("run_validation").main([str(path)], reports_dir=tmp_path / "reports")

    assert code == 0
    event = json.loads(events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "validation_passed"
    assert event["rows"] == 500
    assert not (tmp_path / "reports").exists()


def test_gate_returns_1_logs_failure_and_saves_cases(clean_population, tmp_path):
    batch, expected = inject_defects(clean_population, batch_size=200, seed=42)
    path = tmp_path / "bad.parquet"
    batch.to_parquet(path)

    code = load_script("run_validation").main([str(path)], reports_dir=tmp_path / "reports")

    assert code == 1
    event = json.loads(events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "validation_failed"
    assert event["failures_by_rule"] == expected
    cases = pd.read_csv(tmp_path / "reports" / "bad_failure_cases.csv")
    assert len(cases) == sum(expected.values())
