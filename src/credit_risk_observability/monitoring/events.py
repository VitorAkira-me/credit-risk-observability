"""OBS-001: log estruturado do pipeline, uma linha JSON por evento, sempre com os mesmos campos.

JSON em vez de texto livre porque máquina lê sem regex: dá para contar `status == "falha"` por dia
ou somar `linhas_entrada` sem adivinhar formato. Campos fixos porque, se cada script inventar os
seus, a agregação do OBS-002 vira uma coleção de exceções.

O que faz: mede cada etapa (pipeline_step) e grava o evento no console e em logs/pipeline.jsonl.
Por que existe: sem registro, não dá para saber depois quantos lotes passaram, falharam ou demoraram.
Onde entra no fluxo: scripts/run_validation.py, make_drift_batch.py e run_drift_report.py.

Privacidade (requisito da Etapa 4): o log guarda só contagens, nomes de regra e nomes de arquivo.
Nunca valores de linha nem IDs. Por isso o erro inesperado grava só o tipo da exceção: a mensagem
pode conter um valor do lote.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import time
import uuid

from credit_risk_observability.config import PROJECT_ROOT

PIPELINE_LOG_PATH = PROJECT_ROOT / "logs" / "pipeline.jsonl"

# O esquema do evento: toda linha do log tem exatamente estas chaves, nesta ordem.
EVENT_FIELDS = (
    "timestamp",  # quando a etapa terminou, em UTC
    "run_id",  # liga todos os eventos de uma mesma execução
    "etapa",  # qual parte do pipeline: validacao, geracao_lote_drift, relatorio_drift
    "evento",  # o que aconteceu, ex.: validation_failed (nome estável, bom para filtrar)
    "status",  # "sucesso" ou "falha"
    "duracao_s",  # latência da etapa, em segundos
    "linhas_entrada",  # volume que entrou (None se a etapa quebrou antes de ler)
    "linhas_rejeitadas",  # linhas com ao menos uma falha no contrato
    "detalhe",  # dicionário com o resto (lote, regras, diagnóstico); nunca valores de linha
)
SUCCESS = "sucesso"
FAILURE = "falha"


def new_run_id() -> str:
    """Cria a identificação de uma execução.

    Recebe: nada.
    Faz: sorteia um identificador único. Todos os eventos de uma mesma execução carregam o mesmo,
        o que permite reconstruir o que aconteceu naquela rodada.
    Devolve: um texto de 32 caracteres, como "3f2a...".
    """
    return uuid.uuid4().hex


@dataclass
class PipelineStep:
    """O evento de uma etapa, preenchido pelo script enquanto ela roda.

    O script chama succeed() ou fail() para dizer como terminou; o pipeline_step mede o tempo e
    grava. Se o script não chamar nenhum dos dois, a etapa é registrada como falha: silêncio não
    pode virar sucesso (lição do "sucesso vazio" da Fase 3).
    """

    run_id: str
    etapa: str
    evento: str | None = None
    status: str | None = None
    linhas_entrada: int | None = None
    linhas_rejeitadas: int = 0
    detalhe: dict = field(default_factory=dict)

    def succeed(self, evento: str, **detalhe) -> None:
        """Marca a etapa como bem-sucedida, com o nome do evento e os detalhes."""
        self.evento, self.status = evento, SUCCESS
        self.detalhe.update(detalhe)

    def fail(self, evento: str, motivo: str, **detalhe) -> None:
        """Marca a etapa como falha. O motivo é obrigatório: falha sem motivo não ajuda ninguém."""
        self.evento, self.status = evento, FAILURE
        self.detalhe.update(motivo=motivo, **detalhe)


def build_record(step: PipelineStep, duracao_s: float) -> dict:
    """Monta o evento final no esquema fixo.

    Recebe: a etapa preenchida e a duração medida.
    Faz: acrescenta o horário em UTC e coloca as chaves na ordem de EVENT_FIELDS.
    Devolve: o evento como dicionário.
    """
    return {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "run_id": step.run_id,
        "etapa": step.etapa,
        "evento": step.evento,
        "status": step.status,
        "duracao_s": round(duracao_s, 3),
        "linhas_entrada": step.linhas_entrada,
        "linhas_rejeitadas": step.linhas_rejeitadas,
        "detalhe": step.detalhe,
    }


def write_record(logger: logging.Logger, record: dict) -> None:
    """Emite o evento no console e acrescenta a mesma linha em logs/pipeline.jsonl.

    Recebe: o logger e o evento.
    Faz: transforma em uma linha JSON. Falha vai com nível ERROR, para aparecer em destaque.
    Devolve: nada.
    """
    # default=str: um valor que o JSON não conhece vira texto, em vez de derrubar o pipeline.
    line = json.dumps(record, ensure_ascii=False, default=str)
    level = logging.ERROR if record["status"] == FAILURE else logging.INFO
    logger.log(level, line)
    _append(PIPELINE_LOG_PATH, line)


@contextmanager
def pipeline_step(
    logger: logging.Logger, etapa: str, run_id: str | None = None
) -> Iterator[PipelineStep]:
    """Mede uma etapa e grava um evento quando ela termina, dê certo ou não.

    Recebe: o logger, o nome da etapa e, opcionalmente, um run_id já existente.
    Faz: cronometra o bloco `with`. Se o bloco levantar exceção, grava status=falha com o tipo do
        erro e deixa a exceção seguir: registrar não é engolir o erro.
    Devolve: o PipelineStep, que o script preenche. Exemplo:
        with pipeline_step(logger, "validacao") as step:
            step.linhas_entrada = 9000
            step.succeed("validation_passed", lote="production_base")
    """
    step = PipelineStep(run_id=run_id or new_run_id(), etapa=etapa)
    start = time.perf_counter()
    try:
        yield step
    except Exception as exc:
        step.fail("unexpected_error", motivo=f"erro inesperado: {type(exc).__name__}")
        raise
    finally:
        if step.status is None:
            step.fail("step_without_result", motivo="a etapa terminou sem registrar o resultado")
        write_record(logger, build_record(step, time.perf_counter() - start))


def _append(path: Path, line: str) -> None:
    """Acrescenta uma linha no fim do arquivo.

    Recebe: o caminho e a linha.
    Faz: cria a pasta, se faltar, e abre em modo "a" (append), que mantém o que já existe.
    Devolve: nada.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
