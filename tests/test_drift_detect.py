"""Testes do DRIFT-002: o relatório aponta o quadrante certo e não vaza o ID do cliente.

O que faz: testa a régua do diagnóstico e roda scripts/run_drift_report.py de verdade.
Por que existe: o diagnóstico é o que uma pessoa lê primeiro; se ele errar, o relatório engana.
Onde entra no fluxo: roda no pytest, com dados sintéticos e pastas temporárias, sem data/ nem rede.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re

import joblib
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
from credit_risk_observability.drift.detect import (
    CONTROL_AUC,
    CONTROL_AUC_CI_HIGH,
    CONTROL_AUC_CI_LOW,
    DIAGNOSIS_CONCEPT_DRIFT,
    DIAGNOSIS_DATA_DRIFT_NO_IMPACT,
    DIAGNOSIS_DATA_DRIFT_WITH_IMPACT,
    DIAGNOSIS_NO_DRIFT,
    KS_P_VALUE_LIMIT,
    PSI_LIMIT,
    SCORE_COLUMN,
    _select_and_score,
    analyze_batch,
    diagnose,
    features_changed_by_ks,
    features_changed_by_psi,
    performance_dropped,
)
from credit_risk_observability.model.predict import load_model, predict_proba
from credit_risk_observability.model.train import build_pipeline, evaluate
from credit_risk_observability.monitoring import events

ROOT = Path(__file__).resolve().parents[1]
ID_SENTINEL_START = 987_654_000  # número improvável: se aparecer numa saída, é o ID que vazou
# Número inteiro, sem dígitos ou ponto colados: 30.51169876513564 é um decimal do gráfico.
ID_SENTINEL_PATTERN = re.compile(r"(?<![\d.])98765\d{4}(?![\d.])")


def load_script(name: str):
    """Importa um arquivo de scripts/, que não faz parte do pacote instalado.

    Recebe: o nome do script, sem a extensão.
    Faz: carrega o arquivo como um módulo Python.
    Devolve: o módulo. Exemplo: load_script("run_drift_report").main.
    """
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_clients(n: int, seed: int) -> pd.DataFrame:
    """Gera clientes sintéticos válidos no contrato, em que PAY_0 alto indica default.

    Recebe: o número de clientes e a seed (número que fixa o sorteio).
    Faz: sorteia as colunas e calcula o default a partir de PAY_0, para o modelo aprender algo.
    Devolve: a tabela. Exemplo: make_clients(1000, 5) devolve 1.000 linhas e 25 colunas.
    """
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({ID_COLUMN: np.arange(ID_SENTINEL_START, ID_SENTINEL_START + n)})
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
    default_chance = 1 / (1 + np.exp(-2 * (df["PAY_0"] - 1)))
    df[TARGET] = (rng.random(n) < default_chance).astype("int64")
    return df[[ID_COLUMN, *FEATURE_COLUMNS, TARGET]]


def run_report(workspace: dict, name: str, batch: pd.DataFrame) -> tuple[int, Path]:
    """Grava um lote e roda o script de relatório nele.

    Recebe: as pastas e arquivos do teste, o nome do lote e o lote.
    Faz: grava o parquet e chama main, apontando para os caminhos temporários.
    Devolve: o exit code e o caminho do parquet gravado.
    """
    batch_path = workspace["root"] / f"{name}.parquet"
    batch.to_parquet(batch_path, index=False)
    code = load_script("run_drift_report").main(
        [str(batch_path)],
        reference_path=workspace["reference"],
        model_path=workspace["model"],
        reports_dir=workspace["reports"],
    )
    return code, batch_path


@pytest.fixture(scope="module")
def workspace(tmp_path_factory) -> dict:
    """Referência, modelo e pastas temporárias, criados uma vez: treinar custa tempo.

    Também aponta o log para a pasta temporária, para os testes não escreverem no log real.
    """
    root = tmp_path_factory.mktemp("drift_report")
    reference = make_clients(4_000, seed=1)
    reference_path = root / "reference.parquet"
    reference.to_parquet(reference_path, index=False)
    model = build_pipeline().fit(reference[MODEL_FEATURES], reference[TARGET])
    model_path = root / "model.joblib"
    joblib.dump(model, model_path)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(events, "PIPELINE_LOG_PATH", root / "pipeline.jsonl")
        yield {
            "root": root,
            "reference": reference_path,
            "model": model_path,
            "reports": root / "reports",
            "log": root / "pipeline.jsonl",
        }


@pytest.fixture
def control() -> pd.DataFrame:
    """Lote do mesmo gerador da Referência: é o controle, em que nada mudou."""
    return make_clients(2_000, seed=2)


@pytest.fixture(scope="module")
def control_run(workspace) -> int:
    """Roda o relatório do controle uma vez, porque cada rodada do Evidently leva segundos."""
    code, _ = run_report(workspace, "control", make_clients(2_000, seed=2))
    return code


def read_summary(workspace: dict, name: str) -> dict:
    """Lê o resumo JSON de um lote.

    Recebe: as pastas do teste e o nome do lote.
    Faz: abre drift_report_<lote>.json.
    Devolve: o resumo como dicionário.
    """
    path = workspace["reports"] / f"drift_report_{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def all_keys(value) -> set[str]:
    """Junta as chaves de um JSON em todos os níveis.

    Recebe: um valor lido de um JSON.
    Faz: percorre dicionários e listas por dentro.
    Devolve: o conjunto de chaves. Exemplo: {"a": [{"b": 1}]} devolve {"a", "b"}.
    """
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in all_keys(item)}
    return set()


# --- A régua do diagnóstico ---


@pytest.mark.parametrize(
    ("features_changed", "dropped", "expected"),
    [
        (False, False, DIAGNOSIS_NO_DRIFT),
        (True, False, DIAGNOSIS_DATA_DRIFT_NO_IMPACT),
        (False, True, DIAGNOSIS_CONCEPT_DRIFT),
        (True, True, DIAGNOSIS_DATA_DRIFT_WITH_IMPACT),
    ],
)
def test_diagnosis_has_one_answer_per_quadrant(features_changed, dropped, expected):
    """Cada uma das 4 combinações tem o seu diagnóstico."""
    assert diagnose(features_changed, dropped) == expected


def test_diagnosis_texts_match_the_spec():
    """Os textos são os da decisão do Akira: uma mudança aqui muda o que o leitor entende."""
    assert DIAGNOSIS_NO_DRIFT == "sem drift relevante"
    assert DIAGNOSIS_DATA_DRIFT_NO_IMPACT == "data drift sem impacto no modelo"
    assert DIAGNOSIS_CONCEPT_DRIFT == "suspeita de concept drift"
    assert DIAGNOSIS_DATA_DRIFT_WITH_IMPACT == "data drift com impacto"


def test_psi_rule_is_strictly_above_the_limit():
    """PSI exatamente em 0,25 não dispara: a regra é "maior que"."""
    psi = {"A": 0.25, "B": 0.2501, "C": 0.01}

    assert features_changed_by_psi(psi) == ["B"]


def test_ks_rule_is_strictly_below_the_limit():
    """p-valor exatamente em 0,05 não dispara: a regra é "menor que"."""
    p_values = {"A": 0.05, "B": 0.0499, "C": 0.9}

    assert features_changed_by_ks(p_values) == ["B"]


@pytest.mark.parametrize(("auc", "expected"), [(0.70099, True), (0.701, False), (0.75, False)])
def test_performance_drop_is_strictly_below_the_limit(auc, expected):
    """AUC exatamente em 0,701 ainda está dentro do intervalo normal da Produção-base."""
    assert performance_dropped(auc) is expected


# --- O script de ponta a ponta ---


def test_control_batch_is_no_relevant_drift(workspace, control_run):
    """Lote igual ao esperado: nada mudou, então o diagnóstico é "sem drift relevante"."""
    summary = read_summary(workspace, "control")
    assert control_run == 0
    assert summary["feature_drift"]["changed_by_psi"] == []
    assert summary["feature_drift"]["changed_by_ks"] == []
    assert summary["diagnosis"]["text"] == DIAGNOSIS_NO_DRIFT


def test_changed_feature_is_pointed_and_model_keeps_working(workspace, control):
    """Só o limite muda, e o sinal do modelo está em PAY_0: é data drift sem impacto."""
    control["LIMIT_BAL"] = (control["LIMIT_BAL"] // 2).astype("int64")

    run_report(workspace, "data_drift", control)

    summary = read_summary(workspace, "data_drift")
    assert summary["feature_drift"]["changed_by_psi"] == ["LIMIT_BAL"]
    assert summary["feature_drift"]["changed_by_ks"] == ["LIMIT_BAL"]
    assert summary["diagnosis"]["text"] == DIAGNOSIS_DATA_DRIFT_NO_IMPACT


def test_same_inputs_with_shuffled_labels_is_concept_drift(workspace, control):
    """Entradas iguais e resultado embaralhado: só a performance pode denunciar."""
    control[TARGET] = np.random.default_rng(3).permutation(control[TARGET].to_numpy())

    run_report(workspace, "concept", control)

    summary = read_summary(workspace, "concept")
    assert summary["feature_drift"]["changed_by_ks"] == []
    assert summary["performance"]["dropped"] is True
    assert summary["diagnosis"]["text"] == DIAGNOSIS_CONCEPT_DRIFT


def test_changed_feature_and_shuffled_labels_is_data_drift_with_impact(workspace, control):
    """Entradas e resultado mudaram: é o quadrante do drift que dói."""
    control["LIMIT_BAL"] = (control["LIMIT_BAL"] // 2).astype("int64")
    control[TARGET] = np.random.default_rng(3).permutation(control[TARGET].to_numpy())

    run_report(workspace, "both", control)

    summary = read_summary(workspace, "both")
    assert summary["diagnosis"]["text"] == DIAGNOSIS_DATA_DRIFT_WITH_IMPACT


def test_change_only_the_ks_sees_still_counts_as_feature_change(workspace, control):
    """Fatura 5% menor: só o KS vê, e a régua aceita qualquer um dos dois métodos."""
    # Reduzir mantém os valores dentro da faixa da Referência. Se saíssem dela, cairiam em faixas
    # vazias, e o preenchimento de zeros do Evidently inflaria o PSI (armadilha 1 do SPIKE-001).
    control["BILL_AMT1"] = np.rint(control["BILL_AMT1"] * 0.95).astype("int64")

    run_report(workspace, "only_ks", control)

    summary = read_summary(workspace, "only_ks")
    assert summary["feature_drift"]["changed_by_psi"] == []
    assert summary["feature_drift"]["changed_by_ks"] == ["BILL_AMT1"]
    assert summary["diagnosis"]["text"] == DIAGNOSIS_DATA_DRIFT_NO_IMPACT


def test_change_only_the_psi_sees_still_counts_as_feature_change(workspace, control):
    """SEX é categórica e não tem KS: só o PSI pode apontar a mudança dela."""
    control["SEX"] = 1

    run_report(workspace, "only_psi", control)

    summary = read_summary(workspace, "only_psi")
    assert summary["feature_drift"]["changed_by_psi"] == ["SEX"]
    assert summary["feature_drift"]["changed_by_ks"] == []
    assert summary["diagnosis"]["text"] == DIAGNOSIS_DATA_DRIFT_NO_IMPACT


def test_evidently_page_agrees_with_the_diagnosis(workspace, control_run, control):
    """O gráfico não pode dizer "sem drift" abaixo de um diagnóstico de data drift."""
    control["LIMIT_BAL"] = (control["LIMIT_BAL"] // 2).astype("int64")
    run_report(workspace, "agrees", control)

    no_drift = (workspace["reports"] / "drift_report_control.html").read_text(encoding="utf-8")
    with_drift = (workspace["reports"] / "drift_report_agrees.html").read_text(encoding="utf-8")

    assert "Dataset Drift is detected" not in no_drift
    assert no_drift.count("Dataset Drift is NOT detected") == 2
    assert with_drift.count("Dataset Drift is detected") == 2
    assert "Dataset Drift is NOT detected" not in with_drift


def test_evidently_uses_the_same_limits_as_the_diagnosis(workspace, control):
    """Limiar padrão do Evidently faria o HTML discordar: PSI dele é 0,1, e o nosso é 0,25."""
    reference = pd.read_parquet(workspace["reference"])

    snapshot, _ = analyze_batch(reference, control, load_model(workspace["model"]))

    limits = {"psi": PSI_LIMIT, "ks": KS_P_VALUE_LIMIT}
    drift_metrics = [
        metric["config"]
        for metric in snapshot.dict()["metrics"]
        if metric["metric_name"].startswith("ValueDrift(")
    ]
    assert len(drift_metrics) >= 23
    assert all(config["threshold"] == limits[config["method"]] for config in drift_metrics)


def test_id_is_removed_before_the_data_reaches_evidently(workspace, control):
    """A primeira barreira do ADR-005: o ID sai antes de o Evidently receber os dados."""
    selected = _select_and_score(control, load_model(workspace["model"]))

    assert ID_COLUMN not in selected.columns
    assert list(selected.columns) == [*FEATURE_COLUMNS, TARGET, SCORE_COLUMN]
    assert ID_COLUMN in control.columns


def test_summary_numbers_come_from_the_batch(workspace, control_run, control):
    """Conferência independente: taxa, score e métricas são do lote, e não da Referência."""
    summary = read_summary(workspace, "control")
    reference = pd.read_parquet(workspace["reference"])
    scores = predict_proba(load_model(workspace["model"]), control)
    metrics = evaluate(control[TARGET], scores, threshold=0.5)

    target = summary["target_and_score"]
    assert target["default_rate_batch"] == pytest.approx(control[TARGET].mean())
    assert target["default_rate_reference"] == pytest.approx(reference[TARGET].mean())
    assert target["score_mean_batch"] == pytest.approx(scores.mean())
    performance = summary["performance"]
    assert performance["roc_auc"] == metrics["roc_auc"]
    assert performance["recall_default"] == metrics["recall_default"]
    assert performance["precision_default"] == metrics["precision_default"]


def test_control_numbers_match_the_trained_baseline():
    """A régua de AUC precisa ser a do modelo versionado, e o controle tem de caber no IC."""
    metrics_path = ROOT / "models" / "baseline_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert metrics["metrics"]["production_base"]["roc_auc"] == CONTROL_AUC
    assert CONTROL_AUC_CI_LOW < CONTROL_AUC < CONTROL_AUC_CI_HIGH


def test_provenance_has_real_hashes_and_no_local_paths(workspace, control_run):
    """Os hashes provam de onde vieram os números, sem publicar caminhos da máquina."""
    provenance = read_summary(workspace, "control")["provenance"]
    batch_path = workspace["root"] / "control.parquet"

    assert provenance["batch_sha256"] == hashlib.sha256(batch_path.read_bytes()).hexdigest()
    reference_bytes = workspace["reference"].read_bytes()
    assert provenance["reference_sha256"] == hashlib.sha256(reference_bytes).hexdigest()
    model_bytes = workspace["model"].read_bytes()
    assert provenance["model_sha256"] == hashlib.sha256(model_bytes).hexdigest()
    assert provenance["batch_file"] == "control.parquet"
    assert provenance["model_file"] == "model.joblib"


def test_summary_json_has_the_three_blocks(workspace, control_run):
    """O OBS-002 vai ler este JSON: os blocos e campos fazem parte do combinado."""
    summary = read_summary(workspace, "control")

    assert list(summary) == [
        "run_id",
        "created_at",
        "batch",
        "rows",
        "provenance",
        "feature_drift",
        "target_and_score",
        "performance",
        "diagnosis",
    ]
    assert set(summary["feature_drift"]) == {
        "psi_limit",
        "ks_p_value_limit",
        "reference",
        "features",
        "changed_by_psi",
        "changed_by_ks",
    }
    assert set(summary["target_and_score"]) == {
        "default_rate_batch",
        "default_rate_reference",
        "default_psi",
        "score_mean_batch",
        "score_mean_reference",
        "score_psi",
        "score_ks_p_value",
    }
    assert set(summary["performance"]) == {
        "roc_auc",
        "recall_default",
        "precision_default",
        "compared_with",
        "control_auc",
        "control_ci_low",
        "control_ci_high",
        "dropped",
    }
    assert set(summary["diagnosis"]) == {"text", "features_changed", "performance_dropped"}
    assert summary["run_id"]
    assert summary["rows"]["batch"] == 2_000


def test_every_feature_has_psi_and_only_numeric_ones_have_ks(workspace, control_run):
    """São 23 colunas no PSI. O KS exige números, então as 3 categóricas vêm sem ele."""
    features = read_summary(workspace, "control")["feature_drift"]["features"]

    assert list(features) == FEATURE_COLUMNS
    assert all(isinstance(item["psi"], float) for item in features.values())
    categorical_without_ks = [
        name for name, item in features.items() if item["ks_p_value"] is None
    ]
    assert categorical_without_ks == ["SEX", "EDUCATION", "MARRIAGE"]


def test_id_does_not_appear_in_any_output(workspace, control_run):
    """ADR-005: nem o nome da coluna nem os valores de ID saem no JSON, no HTML ou no log."""
    summary_text = (workspace["reports"] / "drift_report_control.json").read_text(encoding="utf-8")
    html = (workspace["reports"] / "drift_report_control.html").read_text(encoding="utf-8")
    log = workspace["log"].read_text(encoding="utf-8")

    assert ID_COLUMN not in all_keys(json.loads(summary_text))
    assert '"ID"' not in html
    for text in (summary_text, html, log):
        assert not ID_SENTINEL_PATTERN.search(text)


def test_score_stays_in_memory_and_batch_file_is_untouched(workspace, control):
    """O score não é gravado: o parquet do lote continua igual, byte a byte."""
    batch_path = workspace["root"] / "untouched.parquet"
    control.to_parquet(batch_path, index=False)
    hash_before = hashlib.sha256(batch_path.read_bytes()).hexdigest()
    columns_before = set(pd.read_parquet(batch_path).columns)

    load_script("run_drift_report").main(
        [str(batch_path)],
        reference_path=workspace["reference"],
        model_path=workspace["model"],
        reports_dir=workspace["reports"],
    )

    assert hashlib.sha256(batch_path.read_bytes()).hexdigest() == hash_before
    assert set(pd.read_parquet(batch_path).columns) == columns_before


def test_html_opens_with_the_portuguese_summary(workspace, control_run):
    """A pessoa lê o diagnóstico e a comparação de AUC antes dos gráficos do Evidently."""
    html = (workspace["reports"] / "drift_report_control.html").read_text(encoding="utf-8")

    body = html.split("<body>")[1].lstrip()
    summary_section = body[: body.index("</section>")]
    assert body.startswith("<section")
    assert f"Diagnóstico: {DIAGNOSIS_NO_DRIFT}" in summary_section
    assert "Produção-base" in summary_section


def test_batch_rejected_by_contract_generates_no_report(workspace, control):
    """Dado sujo não é drift: exit 1, nenhum relatório e um evento de rejeição no log."""
    control.loc[0, "AGE"] = 15

    code, _ = run_report(workspace, "dirty", control)

    assert code == 1
    assert not (workspace["reports"] / "drift_report_dirty.html").exists()
    assert not (workspace["reports"] / "drift_report_dirty.json").exists()
    last_event = json.loads(workspace["log"].read_text(encoding="utf-8").splitlines()[-1])
    assert last_event["evento"] == "drift_report_rejected"


def test_batch_without_target_is_refused_with_a_clear_message(workspace, control):
    """Sem o resultado real não dá para medir a performance: precisa dizer isso."""
    with pytest.raises(ValueError, match="sem a coluna"):
        run_report(workspace, "no_target", control.drop(columns=TARGET))


def test_batch_with_one_class_is_refused_instead_of_reading_as_stable(workspace, control):
    """Com uma classe só, a AUC vira NaN e o lote pareceria estável sem ter sido medido."""
    control[TARGET] = 0

    with pytest.raises(ValueError, match="uma classe"):
        run_report(workspace, "one_class", control)

    assert not (workspace["reports"] / "drift_report_one_class.json").exists()


def test_generated_event_goes_to_the_log(workspace, control_run):
    """O OBS-001 vai ler este evento: precisa ter run_id, diagnóstico e AUC."""
    summary = read_summary(workspace, "control")
    log_lines = workspace["log"].read_text(encoding="utf-8").splitlines()
    log_events = [json.loads(line) for line in log_lines]

    event = next(item for item in log_events if item["run_id"] == summary["run_id"])
    assert event["evento"] == "drift_report_generated"
    assert event["detalhe"]["diagnostico"] == DIAGNOSIS_NO_DRIFT
    assert event["detalhe"]["roc_auc"] == summary["performance"]["roc_auc"]


def test_telemetry_is_off():
    """Importar detect.py desliga o envio de dados de uso do Evidently."""
    from evidently.telemetry import event_logger

    assert event_logger.enabled() is False
