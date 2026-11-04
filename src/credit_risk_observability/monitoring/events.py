"""Log estruturado mínimo: um evento por linha, em JSON.

JSON em vez de texto livre porque máquina lê sem regex: dá para contar `validation_failed`
por dia ou somar `rows` sem adivinhar formato. Base para o OBS-001.
"""

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import uuid

from credit_risk_observability.config import PROJECT_ROOT

PIPELINE_LOG_PATH = PROJECT_ROOT / "logs" / "pipeline.jsonl"


def new_run_id() -> str:
    """Cria a identificação de uma execução.

    Recebe: nada.
    Faz: sorteia um identificador único. Todos os eventos de uma mesma execução carregam o mesmo,
        o que permite ao OBS-001 reconstruir o que aconteceu naquela rodada.
    Devolve: um texto de 32 caracteres, como "3f2a...".
    """
    return uuid.uuid4().hex


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> dict:
    """Emite o evento no logger (console) e acrescenta a mesma linha em logs/pipeline.jsonl."""
    record = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "event": event, **fields}
    line = json.dumps(record, ensure_ascii=False, default=str)
    logger.log(level, line)
    _append(PIPELINE_LOG_PATH, line)
    return record


def _append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
