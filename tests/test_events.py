"""Testes do log estruturado (OBS-001): esquema fixo, falha registrada, run_id e ausência de PII.

O que faz: exercita pipeline_step direto e roda scripts/run_validation.py com log temporário.
Por que existe: o OBS-002 vai agregar estas linhas; se o formato variar, a agregação quebra calada.
Onde entra no fluxo: roda no pytest; não toca em data/, reports/ nem logs/ do projeto.
"""

import importlib.util
import inspect
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import (
    DRIFT_REPORTS_DIR,
    DRIFT_RUNS_DIR,
    FEATURE_COLUMNS,
    ID_COLUMN,
    PROJECT_ROOT,
    TARGET,
)
from credit_risk_observability.contracts.corrupt import inject_defects
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.monitoring import events
from credit_risk_observability.monitoring.events import EVENT_FIELDS, pipeline_step

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("test_events")

# IDs com uma marca fácil de procurar no log: se ela aparecer, um identificador vazou.
ID_MARK = 987_650_000


def load_script(name: str):
    """Importa um arquivo de scripts/, que não faz parte do pacote instalado."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_events() -> list[dict]:
    """Lê todas as linhas do log temporário como dicionários."""
    lines = events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Evita que os testes escrevam no log real do pipeline."""
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")


@pytest.fixture
def clean_population() -> pd.DataFrame:
    """500 clientes válidos, com IDs marcados para o teste de PII."""
    rng = np.random.default_rng(7)
    n = 500
    df = pd.DataFrame({ID_COLUMN: np.arange(ID_MARK + 1, ID_MARK + n + 1)})
    for col in FEATURE_COLUMNS:
        df[col] = 0
    df["LIMIT_BAL"] = rng.integers(10, 100, n) * 1_000
    df["SEX"] = rng.choice([1, 2], n)
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["MARRIAGE"] = rng.choice([1, 2], n)
    df["AGE"] = rng.integers(21, 70, n)
    df[TARGET] = rng.choice([0, 1], n)
    return df


def test_successful_step_writes_one_line_with_the_fixed_schema():
    """Uma etapa, uma linha, exatamente as chaves do esquema e na mesma ordem."""
    with pipeline_step(logger, "validacao") as step:
        step.linhas_entrada = 10
        step.succeed("validation_passed", lote="x.parquet")

    [event] = read_events()
    assert tuple(event) == EVENT_FIELDS
    assert event["status"] == "sucesso"
    assert event["linhas_entrada"] == 10
    assert event["linhas_rejeitadas"] == 0
    assert event["duracao_s"] >= 0
    assert event["detalhe"] == {"lote": "x.parquet"}


def test_exception_is_logged_as_failure_and_still_raised():
    """Registrar não é engolir: a exceção sobe, e o log guarda só o tipo, sem a mensagem."""
    with pytest.raises(ValueError), pipeline_step(logger, "relatorio_drift"):
        raise ValueError("valor do cliente 123456")

    [event] = read_events()
    assert event["status"] == "falha"
    assert event["evento"] == "unexpected_error"
    assert event["detalhe"]["motivo"] == "erro inesperado: ValueError"
    assert "123456" not in json.dumps(event)


def test_step_without_result_is_a_failure_not_a_silent_success():
    """Se o script esquecer de dizer como terminou, a etapa não pode virar sucesso."""
    with pipeline_step(logger, "validacao"):
        pass

    [event] = read_events()
    assert event["status"] == "falha"
    assert event["evento"] == "step_without_result"


def test_steps_of_one_run_share_the_run_id():
    """Duas etapas da mesma execução: mesmo run_id, que é o que permite reconstruir a rodada."""
    with pipeline_step(logger, "validacao") as first:
        first.succeed("validation_passed")
    with pipeline_step(logger, "relatorio_drift", run_id=first.run_id) as second:
        second.succeed("drift_report_generated")

    run_ids = {event["run_id"] for event in read_events()}
    assert run_ids == {first.run_id}


def test_corrupted_batch_logs_failure_with_reason_and_no_pii(clean_population, tmp_path):
    """Lote corrompido: falha com motivo, linhas rejeitadas contadas e nenhum ID no log."""
    batch, expected = inject_defects(clean_population, batch_size=200, seed=42)
    path = tmp_path / "bad.parquet"
    batch.to_parquet(path)

    code = load_script("run_validation").main([str(path)], reports_dir=tmp_path / "reports")

    assert code == 1
    [event] = read_events()
    assert event["status"] == "falha"
    assert event["linhas_entrada"] == len(batch)
    assert event["linhas_rejeitadas"] == validate_batch(batch).rejected_rows > 0
    assert "regras do contrato violadas" in event["detalhe"]["motivo"]
    assert event["detalhe"]["falhas_por_regra"] == expected
    # PII: nenhum identificador do lote aparece na linha gravada.
    line = events.PIPELINE_LOG_PATH.read_text(encoding="utf-8")
    assert str(ID_MARK)[:5] not in line


def test_rejected_rows_counts_each_row_once(clean_population):
    """Três falhas na mesma linha contam como uma linha rejeitada."""
    batch = clean_population.copy()
    batch.loc[0, ["AGE", "SEX", "EDUCATION"]] = [15, 9, 9]

    result = validate_batch(batch)

    assert len(result.failures_by_rule) == 3
    assert result.rejected_rows == 1


def test_wrong_dtype_rejects_every_row(clean_population):
    """Tipo errado atinge a coluna inteira: nenhuma linha do lote é confiável."""
    batch = clean_population.astype({"AGE": float})

    result = validate_batch(batch)

    assert not result.passed
    assert result.rejected_rows == len(batch)


def test_drift_report_default_output_is_outside_git():
    """Rodar o relatório sem argumentos não pode sobrescrever a evidência de reports/drift/."""
    default = inspect.signature(load_script("run_drift_report").main).parameters["reports_dir"]

    assert default.default == DRIFT_RUNS_DIR != DRIFT_REPORTS_DIR
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"{DRIFT_RUNS_DIR.parent.name}/" in gitignore
