"""Testes do GOV-002: a política de retenção apaga só o vencido, e só quando mandada.

O que faz: cria arquivos e linhas de log com datas controladas numa pasta temporária.
Por que existe: apagar é irreversível; o código que apaga precisa ser o mais testado.
Onde entra no fluxo: roda no pytest; não toca em outputs/ nem em logs/ do projeto.
"""

from datetime import UTC, datetime, timedelta
import json
import os

from credit_risk_observability.governance import retention
from credit_risk_observability.monitoring import events

NOW = datetime(2026, 11, 8, tzinfo=UTC)


def _file(path, age_days):
    """Cria um arquivo com data de modificação de `age_days` dias atrás."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    stamp = (NOW - timedelta(days=age_days)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def _setup(tmp_path, monkeypatch):
    """Aponta a política para pastas e log temporários."""
    detail, weekly = tmp_path / "validation", tmp_path / "weekly"
    monkeypatch.setattr(retention, "FILE_RETENTION_DAYS", {detail: 30, weekly: 90})
    monkeypatch.setattr(events, "PIPELINE_LOG_PATH", tmp_path / "pipeline.jsonl")
    lines = [
        json.dumps({"timestamp": (NOW - timedelta(days=200)).isoformat(), "run_id": "velho"}),
        json.dumps({"timestamp": (NOW - timedelta(days=10)).isoformat(), "run_id": "novo"}),
        "linha sem json",
    ]
    events.PIPELINE_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "old_detail": _file(detail / "lote_detalhe.csv", 31),
        "new_detail": _file(detail / "outro_detalhe.csv", 29),
        "weekly_60": _file(weekly / "semana_1" / "drift_report.html", 60),
        "weekly_91": _file(weekly / "semana_0" / "drift_report.html", 91),
    }


def test_simulation_lists_but_does_not_delete(tmp_path, monkeypatch):
    """Sem --aplicar, nada some: só a lista do que venceu."""
    files = _setup(tmp_path, monkeypatch)

    result = retention.apply_retention(now=NOW, apply=False)

    assert result.files == sorted([files["old_detail"], files["weekly_91"]])
    assert result.log_lines_removed == 1
    assert all(p.exists() for p in files.values())
    assert len(events.PIPELINE_LOG_PATH.read_text().splitlines()) == 3


def test_apply_deletes_only_what_expired(tmp_path, monkeypatch):
    """Com --aplicar: some o vencido; o dentro do prazo e a linha ilegível ficam."""
    files = _setup(tmp_path, monkeypatch)

    retention.apply_retention(now=NOW, apply=True)

    assert not files["old_detail"].exists() and not files["weekly_91"].exists()
    assert files["new_detail"].exists() and files["weekly_60"].exists()
    log = events.PIPELINE_LOG_PATH.read_text().splitlines()
    assert [line for line in log if "velho" in line] == []
    assert len(log) == 2  # a linha nova e a ilegível (na dúvida, não se apaga auditoria)
