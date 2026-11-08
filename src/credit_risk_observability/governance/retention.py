"""GOV-002: política de retenção das saídas locais, aplicada por código.

O que faz: apaga os arquivos locais que passaram do prazo e as linhas antigas do log do pipeline.
Por que existe: o princípio da necessidade da LGPD vale também no tempo. Guardar "para o caso de
precisar" é guardar sem finalidade. Um prazo escrito no README e nunca aplicado não protege ninguém.
Onde entra no fluxo: scripts/apply_retention.py, rodado à mão ou por um agendador.

Prazos (dias) e por quê:
- Detalhe das falhas do contrato (outputs/validation/): 30. Tem valores de cliente; serve só para
  investigar um lote barrado, o que acontece na mesma semana.
- Saídas das semanas e relatórios de drift regerados (outputs/): 90. Um trimestre de histórico
  para comparar semanas; a evidência versionada fica em reports/.
- Linhas do log do pipeline (logs/pipeline.jsonl): 180. Sem PII; serve para auditoria operacional.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from credit_risk_observability.config import (
    DRIFT_RUNS_DIR,
    VALIDATION_DETAIL_DIR,
    WEEKLY_RUNS_DIR,
)
from credit_risk_observability.monitoring import events

FILE_RETENTION_DAYS = {VALIDATION_DETAIL_DIR: 30, WEEKLY_RUNS_DIR: 90, DRIFT_RUNS_DIR: 90}
LOG_RETENTION_DAYS = 180


@dataclass
class RetentionResult:
    """O que a política apagou (ou apagaria, na simulação)."""

    files: list[Path]
    log_lines_removed: int


def expired_files(folder: Path, days: int, now: datetime) -> list[Path]:
    """Arquivos da pasta (e subpastas) modificados há mais de `days` dias.

    Recebe: a pasta, o prazo em dias e o "agora" (passado de fora para o teste controlar o tempo).
    Faz: compara a data de modificação de cada arquivo com o limite.
    Devolve: a lista, em ordem. Pasta que não existe devolve lista vazia.
    """
    if not folder.exists():
        return []
    limit = (now - timedelta(days=days)).timestamp()
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.stat().st_mtime < limit)


def expired_log_lines(path: Path, days: int, now: datetime) -> tuple[list[str], int]:
    """Separa as linhas do log que ainda valem das que passaram do prazo.

    Recebe: o arquivo de log, o prazo e o "agora".
    Faz: lê o timestamp de cada linha JSON. Linha sem timestamp legível é mantida: na dúvida, não
        se apaga registro de auditoria.
    Devolve: (linhas mantidas, quantas seriam removidas).
    """
    if not path.exists():
        return [], 0
    limit = now - timedelta(days=days)
    kept, removed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            stamp = datetime.fromisoformat(json.loads(line)["timestamp"])
        except (ValueError, KeyError, TypeError):
            kept.append(line)
            continue
        if stamp < limit:
            removed += 1
        else:
            kept.append(line)
    return kept, removed


def apply_retention(now: datetime | None = None, apply: bool = False) -> RetentionResult:
    """Aplica a política a todas as saídas locais.

    Recebe: o "agora" (padrão: o relógio em UTC) e se é para apagar de fato.
    Faz: lista os vencidos; com apply=True, apaga os arquivos e reescreve o log sem as linhas velhas.
        Sem apply, só simula: apagar é irreversível, então o padrão é olhar antes.
    Devolve: o que foi (ou seria) apagado.
    """
    now = now or datetime.now(UTC)
    files = [
        f for folder, days in FILE_RETENTION_DAYS.items() for f in expired_files(folder, days, now)
    ]
    kept, removed = expired_log_lines(events.PIPELINE_LOG_PATH, LOG_RETENTION_DAYS, now)
    if apply:
        for path in files:
            path.unlink()
        if removed:
            text = "\n".join(kept) + ("\n" if kept else "")
            events.PIPELINE_LOG_PATH.write_text(text, encoding="utf-8")
    return RetentionResult(files=files, log_lines_removed=removed)
