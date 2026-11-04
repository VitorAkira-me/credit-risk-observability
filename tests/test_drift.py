"""Testes do DRIFT-001: provam que os lotes com drift mudam exatamente o que foi decidido.

Por que existe: a simulação só serve como "resposta certa" para o detector se soubermos, com
certeza, o que foi alterado. Usa dados sintéticos pequenos, então não depende de data/ nem de rede.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import (
    BILL_COLUMNS,
    FEATURE_COLUMNS,
    ID_COLUMN,
    TARGET,
)
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.drift.scenarios import (
    ConceptDriftParams,
    DataDriftParams,
    apply_concept_drift,
    apply_data_drift,
    plan_concept_drift,
)
from credit_risk_observability.monitoring import events

ROOT = Path(__file__).resolve().parents[1]
SEED = 42


def load_script(name: str):
    """Importa um arquivo de scripts/, que não faz parte do pacote instalado."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def base() -> pd.DataFrame:
    """Produção-base sintética, válida no contrato, com faturas negativas e faixas de fatura variadas."""
    rng = np.random.default_rng(1)
    n = 1_000
    df = pd.DataFrame({ID_COLUMN: np.arange(1, n + 1)})
    for col in FEATURE_COLUMNS:
        df[col] = 0
    df["LIMIT_BAL"] = rng.integers(1, 50, n) * 10_000
    df["SEX"] = rng.choice([1, 2], n)
    df["EDUCATION"] = rng.choice([1, 2, 3], n)
    df["MARRIAGE"] = rng.choice([1, 2], n)
    df["AGE"] = rng.integers(21, 70, n)
    for col in BILL_COLUMNS:
        df[col] = rng.integers(-5_000, 200_000, n)
    df[TARGET] = (rng.random(n) < 0.22).astype("int64")
    return df


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Evita que os testes escrevam no log real do pipeline."""
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")


# --- Intensidade 0: nada muda ---


def test_data_drift_intensity_zero_is_identical(base):
    """Intensidade 0 é o grupo de controle: o lote precisa ser igual à base."""
    batch, _ = apply_data_drift(base, intensity=0)

    pd.testing.assert_frame_equal(batch, base)


def test_concept_drift_intensity_zero_is_identical(base):
    """Sem intensidade, nenhum rótulo muda: nada de troca escondida."""
    batch, details = apply_concept_drift(base, intensity=0, seed=SEED)

    pd.testing.assert_frame_equal(batch, base)
    assert details["labels_flipped"] == 0


# --- Intensidade 1: fatores exatos ---


def test_data_drift_intensity_one_applies_exact_factors(base):
    """Com intensidade 1, valem os fatores da spec: faturas × 1,25 e limite × 0,75."""
    batch, details = apply_data_drift(base, intensity=1)

    expected_limit = np.rint(base["LIMIT_BAL"] * 0.75).astype("int64")
    pd.testing.assert_series_equal(batch["LIMIT_BAL"], expected_limit)
    for col in BILL_COLUMNS:
        pd.testing.assert_series_equal(batch[col], np.rint(base[col] * 1.25).astype("int64"))
    assert details["bill_factor"] == 1.25
    assert details["limit_factor"] == 0.75


def test_data_drift_interpolates_linearly(base):
    """No meio da escala, o fator fica no meio do caminho até o fator cheio."""
    _, details = apply_data_drift(base, intensity=0.5)

    assert details["bill_factor"] == pytest.approx(1.125)
    assert details["limit_factor"] == pytest.approx(0.875)


def test_data_drift_multiplies_negative_bills(base):
    """Decisão da spec: crédito a favor do cliente também cresce (-1.000 vira -1.250)."""
    base.loc[0, "BILL_AMT1"] = -1_000

    batch, _ = apply_data_drift(base, intensity=1)

    assert batch.loc[0, "BILL_AMT1"] == -1_250


def test_data_drift_changes_only_bills_and_limit(base):
    """Colunas fora da história, e o default, ficam iguais: é o que torna o lote data drift."""
    batch, _ = apply_data_drift(base, intensity=1)

    untouched = [c for c in base.columns if c not in [*BILL_COLUMNS, "LIMIT_BAL"]]
    pd.testing.assert_frame_equal(batch[untouched], base[untouched])


def test_data_drift_keeps_integer_types(base):
    """Com fator quebrado, o resultado segue inteiro: o contrato reprovaria um float."""
    batch, _ = apply_data_drift(base, intensity=0.33)

    assert batch["LIMIT_BAL"].dtype == "int64"
    assert (batch[BILL_COLUMNS].dtypes == "int64").all()


# --- Contrato: drift é "diferente mas possível" ---


@pytest.mark.parametrize("intensity", [0.25, 0.5, 1])
def test_drifted_batches_pass_the_contract(base, intensity):
    """Drift é diferente mas possível: nenhuma intensidade pode gerar dado sujo."""
    data_batch, _ = apply_data_drift(base, intensity=intensity)
    concept_batch, _ = apply_concept_drift(base, intensity=intensity, seed=SEED)

    assert validate_batch(data_batch).passed
    assert validate_batch(concept_batch).passed


# --- Concept drift: X intacto, número exato de rótulos ---


def test_concept_drift_does_not_change_any_x_column(base):
    """Concept drift muda só o y: um monitor de entradas não pode ver diferença."""
    batch, _ = apply_concept_drift(base, intensity=1, seed=SEED)

    x_columns = [c for c in base.columns if c != TARGET]
    pd.testing.assert_frame_equal(batch[x_columns], base[x_columns])


def test_concept_drift_flips_exactly_the_calculated_labels(base):
    """Troca o número exato do plano, só de 0 para 1 e só no quartil alto de fatura."""
    plan = plan_concept_drift(base)

    batch, details = apply_concept_drift(base, intensity=1, seed=SEED)

    changed = batch[TARGET] != base[TARGET]
    assert changed.sum() == plan.labels_to_flip_at_full == details["labels_flipped"]
    # Só existe uma direção: de "não deu default" para "deu default".
    assert (base.loc[changed, TARGET] == 0).all()
    assert (batch.loc[changed, TARGET] == 1).all()
    # Todo rótulo trocado pertence ao quartil alto de fatura.
    assert (base.loc[changed, "BILL_AMT1"] >= plan.bill_cutoff).all()


def test_concept_drift_doubles_the_subgroup_default_rate(base):
    """Confere o objetivo da conta: a taxa de default do subgrupo dobra."""
    plan = plan_concept_drift(base)

    batch, _ = apply_concept_drift(base, intensity=1, seed=SEED)

    subgroup = base["BILL_AMT1"] >= plan.bill_cutoff
    assert batch.loc[subgroup, TARGET].mean() == pytest.approx(
        2 * base.loc[subgroup, TARGET].mean()
    )


def test_plan_math_matches_the_spec():
    """Exemplo à mão: 4 no subgrupo, 1 com default. r=0,25; f=1/3; trocar 1 rótulo."""
    df = pd.DataFrame(
        {"BILL_AMT1": [0, 0, 0, 0, 10, 20, 30, 40], TARGET: [0, 0, 0, 0, 1, 0, 0, 0]}
    )

    plan = plan_concept_drift(df, ConceptDriftParams(subgroup_quantile=0.5))

    assert plan.subgroup_size == 4
    assert plan.subgroup_defaults == 1
    assert plan.subgroup_default_rate == pytest.approx(0.25)
    assert plan.fraction_of_non_defaults == pytest.approx(1 / 3)
    assert plan.labels_to_flip_at_full == 1


def test_higher_intensity_keeps_previously_flipped_labels(base):
    """Quem mudou em 0,3 segue mudado em 0,6: entre semanas, varia o drift, não o sorteio."""
    weak, _ = apply_concept_drift(base, intensity=0.3, seed=SEED)
    strong, _ = apply_concept_drift(base, intensity=0.6, seed=SEED)

    flipped_weak = weak[TARGET] != base[TARGET]
    flipped_strong = strong[TARGET] != base[TARGET]
    assert flipped_weak.sum() < flipped_strong.sum()
    assert (flipped_strong[flipped_weak]).all()


def test_plan_refuses_subgroup_without_defaults():
    """Trocaria 0 rótulos: seria um lote com "drift" que não mudou nada (sucesso vazio)."""
    df = pd.DataFrame({"BILL_AMT1": [1, 2, 3, 4], TARGET: [0, 0, 0, 0]})

    with pytest.raises(ValueError, match="sem nenhum default"):
        plan_concept_drift(df)


def test_plan_refuses_rate_that_cannot_double():
    """Com 100% de default no subgrupo, não há clientes para trocar: precisa dar erro."""
    df = pd.DataFrame({"BILL_AMT1": [1, 2, 3, 4], TARGET: [0, 0, 1, 1]})

    with pytest.raises(ValueError, match="não dá para dobrar"):
        plan_concept_drift(df, ConceptDriftParams(subgroup_quantile=0.5))


# --- Seed ---


def test_same_seed_generates_the_same_batch(base):
    """Seed fixa (número que controla o sorteio) torna o lote reprodutível."""
    first, _ = apply_concept_drift(base, intensity=1, seed=SEED)
    second, _ = apply_concept_drift(base, intensity=1, seed=SEED)

    pd.testing.assert_frame_equal(first, second)


def test_different_seed_flips_different_rows_with_same_count(base):
    """Outra seed muda quem é sorteado, mas não quantos: prova que a seed é usada."""
    first, first_details = apply_concept_drift(base, intensity=1, seed=1)
    second, second_details = apply_concept_drift(base, intensity=1, seed=2)

    assert first_details["labels_flipped"] == second_details["labels_flipped"]
    assert not first[TARGET].equals(second[TARGET])


# --- Entradas inválidas e imutabilidade ---


@pytest.mark.parametrize("intensity", [-0.1, 1.1, float("nan")])
def test_invalid_intensity_is_refused(base, intensity):
    """Fora de 0 a 1, ou NaN (valor indefinido), falha na hora, sem gerar lote errado."""
    with pytest.raises(ValueError, match="intensidade"):
        apply_data_drift(base, intensity=intensity)
    with pytest.raises(ValueError, match="intensidade"):
        apply_concept_drift(base, intensity=intensity, seed=SEED)


def test_data_drift_custom_params_are_respected(base):
    """Os fatores vêm dos parâmetros, não de um número fixo escondido no código."""
    _, details = apply_data_drift(base, intensity=1, params=DataDriftParams(bill_factor=2.0))

    assert details["bill_factor"] == 2.0


def test_scenarios_do_not_modify_the_base(base):
    """A Produção-base é o controle: as funções trabalham sempre em uma cópia."""
    original = base.copy()

    apply_data_drift(base, intensity=1)
    apply_concept_drift(base, intensity=1, seed=SEED)

    pd.testing.assert_frame_equal(base, original)


# --- Script de entrada ---


def run_script(base_df: pd.DataFrame, tmp_path: Path, *args: str) -> int:
    """Roda o script com caminhos temporários e devolve o exit code."""
    base_path = tmp_path / "base.parquet"
    base_df.to_parquet(base_path, index=False)
    return load_script("make_drift_batch").main(
        list(args),
        base_path=base_path,
        production_dir=tmp_path / "production",
        reports_dir=tmp_path / "reports",
    )


def test_script_writes_batch_and_manifest(base, tmp_path):
    """Caminho feliz: exit 0, lote e manifesto gravados e run_id igual no log e no manifesto."""
    code = run_script(base, tmp_path, "--scenario", "concept_drift", "--intensity", "1")

    assert code == 0
    batch = pd.read_parquet(tmp_path / "production" / "batch_concept_drift_i100.parquet")
    manifest_path = tmp_path / "reports" / "batch_concept_drift_i100_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(batch) == len(base)
    assert manifest["seed"] == 42
    assert manifest["intensity"] == 1
    assert manifest["labels_flipped"] == plan_concept_drift(base).labels_to_flip_at_full
    # O run_id do manifesto é o mesmo do log: é ele que liga os dois.
    log_line = events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1]
    event = json.loads(log_line)
    assert event["event"] == "drift_batch_generated"
    assert event["run_id"] == manifest["run_id"]


def test_script_manifest_has_factors_and_no_row_values(base, tmp_path):
    """O manifesto traz os fatores e os rótulos trocados, e não traz identificadores."""
    run_script(base, tmp_path, "--scenario", "data_drift", "--intensity", "1")

    manifest_path = tmp_path / "reports" / "batch_data_drift_i100_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["bill_factor"] == 1.25
    assert manifest["limit_factor"] == 0.75
    assert manifest["labels_flipped"] == 0
    # ADR-005: nenhum valor de linha nem identificador no relatório versionado.
    assert ID_COLUMN not in manifest
    assert "ids" not in manifest


def test_script_does_not_write_a_batch_that_fails_the_contract(base, tmp_path):
    """Reprovado no contrato: exit 1, nenhum arquivo gravado e evento de rejeição no log."""
    base.loc[0, "AGE"] = 15

    code = run_script(base, tmp_path, "--scenario", "data_drift", "--intensity", "1")

    assert code == 1
    assert not (tmp_path / "production" / "batch_data_drift_i100.parquet").exists()
    assert not (tmp_path / "reports" / "batch_data_drift_i100_manifest.json").exists()
    event = json.loads(events.PIPELINE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "drift_batch_rejected"


def test_script_refuses_intensity_that_would_collide_in_the_file_name(base, tmp_path):
    """0,333 e 0,33 gerariam o mesmo nome, i033: uma sobrescreveria a outra em silêncio."""
    with pytest.raises(ValueError, match="duas casas"):
        run_script(base, tmp_path, "--scenario", "data_drift", "--intensity", "0.333")
