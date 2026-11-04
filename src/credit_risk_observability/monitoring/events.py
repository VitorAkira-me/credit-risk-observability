"""Log estruturado mínimo: um evento por linha, em JSON.

JSON em vez de texto livre porque máquina lê sem regex: dá para contar `validation_failed`
por dia ou somar `rows` sem adivinhar formato. Base para o OBS-001.

O que faz: grava cada evento do pipeline no console e em logs/pipeline.jsonl.
Por que existe: sem registro, não dá para saber depois quantos lotes passaram ou falharam.
Onde entra no fluxo: scripts/run_validation.py e scripts/make_drift_batch.py chamam log_event.
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
    """Emite o evento no logger (console) e acrescenta a mesma linha em logs/pipeline.jsonl.

    Recebe: o logger, o nome do evento, a gravidade e os campos do evento.
    Faz: acrescenta o horário em UTC, transforma tudo em uma linha JSON e grava nos dois lugares.
    Devolve: o evento como dicionário. Exemplo: {"ts": "...", "event": "validation_passed"}.
    """
    record = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "event": event, **fields}
    # default=str: um valor que o JSON não conhece vira texto, em vez de derrubar o pipeline.
    line = json.dumps(record, ensure_ascii=False, default=str)
    logger.log(level, line)
    _append(PIPELINE_LOG_PATH, line)
    return record


def _append(path: Path, line: str) -> None:
    """Acrescenta uma linha no fim do arquivo.

    Recebe: o caminho e a linha.
    Faz: cria a pasta, se faltar, e abre em modo "a" (append), que mantém o que já existe.
    Devolve: nada.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
