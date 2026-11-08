"""Testes do portão de ingestão: o lote corrompido é bloqueado, e o lote limpo passa.

O que faz: roda scripts/run_validation.py de verdade, com arquivos e log temporários.
Por que existe: o orquestrador decide pelo exit code, então é ele que precisa estar certo.
Onde entra no fluxo: roda no pytest; não toca em data/, reports/ nem logs/ do projeto.
"""

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
    """Importa um arquivo de scripts/, que não faz parte do pacote instalado.

    Recebe: o nome do script, sem a extensão.
    Faz: carrega o arquivo como um módulo Python.
    Devolve: o módulo. Exemplo: load_script("run_validation").main.
    """
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_population() -> pd.DataFrame:
    """População sintética de 500 clientes válidos, de onde sai o lote corrompido."""
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
    """Evita que os testes escrevam no log real do pipeline."""
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")


def test_validation_finds_exactly_the_injected_defects(clean_population):
    """O contrato acha exatamente os defeitos injetados: nem mais, nem menos."""
    batch, expected = inject_defects(clean_population, batch_size=200, seed=42)

    result = validate_batch(batch)

    assert len(batch) == 200 + DEFECTS["duplicated_rows"]
    assert not result.passed
    assert result.failures_by_rule == expected


def test_gate_returns_0_and_logs_pass(clean_population, tmp_path):
    """Lote limpo: exit 0, evento de aprovação e nenhum relatório criado."""
    path = tmp_path / "clean.parquet"
    clean_population.to_parquet(path)

    code = load_script("run_validation").main(
        [str(path)], reports_dir=tmp_path / "reports", detail_dir=tmp_path / "detalhe"
    )

    assert code == 0
    event = json.loads(events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1])
    assert event["evento"] == "validation_passed"
    assert event["linhas_entrada"] == 500
    assert event["status"] == "sucesso"
    assert not (tmp_path / "reports").exists()


def test_gate_returns_1_logs_failure_and_saves_cases(clean_population, tmp_path):
    """Lote sujo: exit 1, evento de falha e um CSV com todos os casos."""
    batch, expected = inject_defects(clean_population, batch_size=200, seed=42)
    path = tmp_path / "bad.parquet"
    batch.to_parquet(path)

    code = load_script("run_validation").main(
        [str(path)], reports_dir=tmp_path / "reports", detail_dir=tmp_path / "detalhe"
    )

    assert code == 1
    event = json.loads(events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1])
    assert event["evento"] == "validation_failed"
    assert event["status"] == "falha"
    assert event["detalhe"]["falhas_por_regra"] == expected
    cases = pd.read_csv(tmp_path / "reports" / "bad_failure_cases.csv")
    assert len(cases) == sum(expected.values())


def test_versioned_report_has_no_customer_values(clean_population, tmp_path):
    """ADR-005: o CSV versionado tem só regra e posição; os valores ficam no detalhe local.

    Usa IDs com uma marca fácil de procurar. Se ela aparecer no relatório versionado, um
    identificador de cliente vazou para o git.
    """
    marked = clean_population.copy()
    marked[ID_COLUMN] = marked[ID_COLUMN] + 987_650_000
    batch, expected = inject_defects(marked, batch_size=200, seed=42)
    path = tmp_path / "bad.parquet"
    batch.to_parquet(path)

    load_script("run_validation").main(
        [str(path)], reports_dir=tmp_path / "reports", detail_dir=tmp_path / "detalhe"
    )

    versioned = (tmp_path / "reports" / "bad_failure_cases.csv").read_text(encoding="utf-8")
    cases = pd.read_csv(tmp_path / "reports" / "bad_failure_cases.csv")
    assert list(cases.columns) == ["regra", "posicao_linha"]
    assert "98765" not in versioned  # nenhum ID marcado
    assert ",15\n" not in versioned and ",15," not in versioned  # nenhuma idade barrada
    assert cases["regra"].value_counts().to_dict() == expected
    # O detalhe existe, mas só na pasta local, e é ele que guarda os valores.
    detail = pd.read_csv(tmp_path / "detalhe" / "bad_detalhe.csv")
    assert "failure_case" in detail.columns


def test_versioned_validation_reports_in_git_have_no_customer_values():
    """Varre reports/validation/ do repositório: nenhum CSV versionado traz valor de cliente."""
    for csv in (ROOT / "reports" / "validation").glob("*.csv"):
        cases = pd.read_csv(csv)
        assert "failure_case" not in cases.columns, csv.name
        assert ID_COLUMN not in cases.columns, csv.name
