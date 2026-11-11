"""Testes do AWS-002 e do AWS-003: a função na nuvem faz o mesmo que o pipeline local.

O que faz: roda o handler do Lambda com um S3 falso e dados sintéticos, e confere as saídas.
Por que existe: depois do deploy, descobrir um erro custa um ciclo inteiro de imagem e nuvem.
Onde entra no fluxo: roda no pytest, sem AWS, sem data/ e sem rede.
"""

import json
from pathlib import Path
import re
import shutil

import joblib
import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.cloud import handler as cloud
from credit_risk_observability.config import ID_COLUMN, MODEL_FEATURES, TARGET
from credit_risk_observability.contracts.corrupt import inject_defects
from credit_risk_observability.model.train import build_pipeline
from credit_risk_observability.monitoring import events
from credit_risk_observability.monitoring.alerts import AlertThresholds
from test_drift_detect import ID_SENTINEL_PATTERN, make_clients

BUCKET = "bucket-de-teste"
BATCH_SIZE = 2_000


class FakeS3:
    """Imita o cliente do S3 com uma pasta local: uma chave é um arquivo dentro dela."""

    def __init__(self, root: Path):
        self.root = root
        self.uploaded: list[str] = []

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        """Copia o arquivo da chave para o destino, como o S3 faria."""
        assert bucket == BUCKET
        shutil.copy(self.root / key, filename)

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        """Guarda o arquivo na chave e anota o que foi enviado."""
        assert bucket == BUCKET
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(filename, target)
        self.uploaded.append(key)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory) -> Path:
    """Um S3 falso com Referência, modelo e limites, criado uma vez: treinar custa tempo."""
    root = tmp_path_factory.mktemp("s3")
    (root / "seed").mkdir()
    reference = make_clients(4_000, seed=1)
    reference.to_parquet(root / cloud.REFERENCE_KEY, index=False)
    model = build_pipeline().fit(reference[MODEL_FEATURES], reference[TARGET])
    joblib.dump(model, root / cloud.MODEL_KEY)
    thresholds = AlertThresholds(
        batch_size=BATCH_SIZE,
        calibration_samples=1,
        holdout_samples=1,
        psi_limit=0.25,
        ks_p_value_limit=0.0025,
        ks_d_min=0.0,
        auc_floor=0.7,
        default_rate_low=0.0,
        default_rate_high=1.0,
        holdout_false_alarm={},
    )
    thresholds.to_json(root / cloud.THRESHOLDS_KEY)
    make_clients(BATCH_SIZE, seed=2).to_parquet(root / cloud.CONTROL_KEY, index=False)
    return root


@pytest.fixture
def run(seeded, tmp_path, monkeypatch, capsys):
    """Devolve uma função que envia um lote ao handler e separa o que ele imprimiu."""
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setattr(cloud, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")
    s3 = FakeS3(seeded)

    def invoke(batch: pd.DataFrame | None, key: str = "incoming/lote.parquet", event=None):
        """Grava o lote, chama o handler e devolve (resultado, linhas JSON, cliente)."""
        if batch is not None:
            (seeded / key).parent.mkdir(parents=True, exist_ok=True)
            batch.to_parquet(seeded / key, index=False)
        if event is None:
            event = s3_event(key)
        capsys.readouterr()
        result = cloud.handler(event, None, s3_client=s3)
        lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
        return result, [json.loads(line) for line in lines], s3

    return invoke


def s3_event(key: str) -> dict:
    """Monta o evento que o S3 envia ao Lambda: a chave chega codificada para URL."""
    encoded = key.replace(" ", "+")
    return {"Records": [{"s3": {"bucket": {"name": BUCKET}, "object": {"key": encoded}}}]}


def metrics_of(lines: list[dict]) -> dict:
    """Acha a linha de métricas EMF (Embedded Metric Format) entre as que o handler imprimiu."""
    return next(line for line in lines if "_aws" in line)


def corrupted_batch() -> pd.DataFrame:
    """Lote de defeitos conhecidos: 1.000 linhas e 20 cópias."""
    batch, _ = inject_defects(make_clients(BATCH_SIZE, seed=2), batch_size=1_000, seed=42)
    return batch


def test_clean_batch_generates_reports_and_no_alert(run):
    """Lote limpo: relatórios no S3, sucesso e nenhum alerta."""
    result, lines, s3 = run(make_clients(BATCH_SIZE, seed=2))

    metrics = metrics_of(lines)
    assert result["status"] == "sucesso"
    assert metrics["LotesReprovados"] == 0
    assert metrics["AlertasDrift"] == 0
    assert metrics["LinhasEntrada"] == BATCH_SIZE
    assert any(key.endswith(".html") for key in s3.uploaded)
    assert any(key.endswith(".json") for key in s3.uploaded)
    assert all(key.startswith("reports/") for key in s3.uploaded)


def test_corrupted_batch_is_a_result_and_not_an_error(run):
    """Contrato reprovado não levanta exceção: o Lambda termina bem, e a métrica dispara o alarme."""
    result, lines, s3 = run(corrupted_batch())

    metrics = metrics_of(lines)
    assert result["status"] == "falha"
    assert metrics["LotesReprovados"] == 1
    assert metrics["LinhasRejeitadas"] == 130
    assert metrics["LinhasEntrada"] == 1_020
    assert not any(key.endswith(".html") for key in s3.uploaded)


def test_shuffled_labels_fire_the_drift_alert(run):
    """Entradas iguais e resultado embaralhado: só a AUC denuncia, e o alerta dispara."""
    batch = make_clients(BATCH_SIZE, seed=2)
    batch[TARGET] = np.random.default_rng(3).permutation(batch[TARGET].to_numpy())

    result, lines, _ = run(batch)

    metrics = metrics_of(lines)
    assert result["status"] == "sucesso"
    assert metrics["AlertasDrift"] == 1
    assert metrics["AUC"] < 0.7


def test_batch_with_uncalibrated_size_is_refused(run):
    """Régua calibrada para 2.000 linhas não vale para outro tamanho: precisa dar erro claro."""
    with pytest.raises(ValueError, match="calibrados para 2000"):
        run(make_clients(500, seed=4))


def test_scheduled_event_uses_the_control_batch(run):
    """O agendamento não tem arquivo novo: ele roda o lote de controle."""
    result, lines, _ = run(None, event={"source": "agendamento-semanal"})

    assert result["status"] == "sucesso"
    assert result["lote"] == "controle"
    assert metrics_of(lines)["LotesReprovados"] == 0


def test_key_with_space_is_decoded(run):
    """O S3 envia a chave com "+" no lugar de espaço: sem decodificar, o arquivo não é achado."""
    result, _, _ = run(make_clients(BATCH_SIZE, seed=2), key="incoming/lote com espaco.parquet")

    assert result["lote"] == "lote com espaco"


def test_emf_line_follows_the_specification(run):
    """Fora do formato, o CloudWatch trata a linha como log comum e a métrica não existe."""
    _, lines, _ = run(make_clients(BATCH_SIZE, seed=2))

    metrics = metrics_of(lines)
    directive = metrics["_aws"]["CloudWatchMetrics"][0]
    assert isinstance(metrics["_aws"]["Timestamp"], int)
    assert directive["Namespace"] == cloud.METRICS_NAMESPACE
    assert directive["Dimensions"] == [["Pipeline"]]
    assert metrics["Pipeline"] == cloud.PIPELINE_NAME
    for definition in directive["Metrics"]:
        assert isinstance(metrics[definition["Name"]], int | float)


def test_events_are_raw_json_with_one_run_id(run):
    """Logs Insights lê os campos sozinho se a linha for JSON puro; o run_id liga as etapas."""
    result, lines, _ = run(make_clients(BATCH_SIZE, seed=2))

    pipeline_events = [line for line in lines if "etapa" in line]
    assert [event["etapa"] for event in pipeline_events] == ["validacao", "relatorio_drift"]
    assert {event["run_id"] for event in pipeline_events} == {result["run_id"]}


def test_no_output_has_id_or_row_values(run, seeded):
    """ADR-005: nenhum ID no log, nas métricas, no retorno ou nos arquivos enviados ao S3."""
    batch = corrupted_batch()
    age_position = batch.index[batch["AGE"] == 15][0]
    batch.loc[age_position, "AGE"] = 77_777

    result, lines, s3 = run(batch)

    printed = json.dumps([result, *lines], ensure_ascii=False)
    assert not ID_SENTINEL_PATTERN.search(printed)
    assert "77777" not in printed
    assert f'"{ID_COLUMN}"' not in printed
    for key in s3.uploaded:
        text = (seeded / key).read_text(encoding="utf-8")
        assert not ID_SENTINEL_PATTERN.search(text)
        assert not re.search(r"\b77777\b", text)


def test_only_incoming_keys_are_processed(run):
    """Defesa contra laço: um arquivo fora de incoming/ é ignorado, mesmo que o gatilho erre."""
    result, lines, s3 = run(None, event=s3_event("reports/abc/drift_report.json"))

    assert result["status"] == "ignorado"
    assert lines == []
    assert s3.uploaded == []


def test_infra_points_to_the_metrics_the_handler_publishes():
    """Alarme olhando métrica com nome errado fica parado para sempre, sem dar erro nenhum."""
    stack = (Path(__file__).resolve().parents[1] / "infra" / "stack.py").read_text(
        encoding="utf-8"
    )

    assert f'METRICS_NAMESPACE = "{cloud.METRICS_NAMESPACE}"' in stack
    assert f'PIPELINE_NAME = "{cloud.PIPELINE_NAME}"' in stack
    for metric in re.findall(r'pipeline_metric\("(\w+)"', stack):
        assert metric in cloud._METRIC_UNITS
    assert 'prefix="incoming/"' in stack
    assert cloud.INCOMING_PREFIX == "incoming/"
