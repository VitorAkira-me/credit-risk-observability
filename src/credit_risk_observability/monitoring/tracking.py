"""OBS-002: registra cada execução do pipeline como um run do MLflow.

O que faz: abre o banco local do MLflow (sqlite) e grava, por execução, os parâmetros, as
métricas de saúde, as tags de alerta e os artefatos (relatório de drift, falhas do contrato).
Por que existe: o log (OBS-001) conta o que aconteceu em cada execução; o MLflow junta as
execuções numa série no tempo, que é o painel da Etapa 3.
Onde entra no fluxo: scripts/run_weekly_pipeline.py chama log_pipeline_run ao fim de cada semana.

Privacidade: só números agregados, nomes de feature e nomes de arquivo. O lote nunca vai para o
MLflow. A telemetria do MLflow é desligada antes do import, como a do Evidently (REPASSE, 16).
"""

import os

# Precisa vir antes do import: o MLflow lê estas variáveis ao carregar.
os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from dataclasses import dataclass, field
from pathlib import Path

import mlflow

from credit_risk_observability.config import (
    MLFLOW_ARTIFACTS_DIR,
    MLFLOW_EXPERIMENT,
    MLFLOW_TRACKING_URI,
)


@dataclass
class PipelineRun:
    """Tudo o que uma execução manda para o MLflow, montado pelo script antes de gravar.

    params: o que define a execução (lote, versão do modelo, método de drift). Não muda no run.
    metrics: números que formam a série no tempo (latência, volume, PSI, AUC).
    tags: rótulos para filtrar na UI, como drift_alert=true.
    artifacts: arquivos anexados ao run (HTML do Evidently, falhas do contrato).
    """

    name: str
    run_id: str  # o mesmo run_id do logs/pipeline.jsonl: é ele que liga o log ao MLflow
    step: int  # a "semana": o eixo x dos gráficos na UI
    params: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
    artifacts: list[Path] = field(default_factory=list)


def setup_tracking(
    tracking_uri: str = MLFLOW_TRACKING_URI,
    experiment: str = MLFLOW_EXPERIMENT,
    artifacts_dir: Path = MLFLOW_ARTIFACTS_DIR,
) -> str:
    """Aponta o MLflow para o banco local e garante que o experimento existe.

    Recebe: o endereço do banco, o nome do experimento e a pasta dos artefatos.
    Faz: cria o experimento na primeira vez, com os artefatos numa pasta local conhecida.
    Devolve: o id do experimento.
    """
    mlflow.set_tracking_uri(tracking_uri)
    found = mlflow.get_experiment_by_name(experiment)
    if found is not None:
        experiment_id = found.experiment_id
    else:
        experiment_id = mlflow.create_experiment(
            experiment, artifact_location=artifacts_dir.resolve().as_uri()
        )
    mlflow.set_experiment(experiment_id=experiment_id)
    return experiment_id


def log_pipeline_run(run: PipelineRun) -> str:
    """Grava uma execução como um run do MLflow.

    Recebe: a execução montada pelo script. setup_tracking precisa ter sido chamado antes.
    Faz: abre o run, grava params, métricas (no step da semana), tags e artefatos, e fecha.
        Valores None são pulados: uma métrica que não existe (AUC de um lote barrado) não pode
        virar zero no gráfico, porque zero pareceria um modelo péssimo.
    Devolve: o id do run no MLflow.
    """
    tags = {"pipeline_run_id": run.run_id, **{k: str(v).lower() for k, v in run.tags.items()}}
    with mlflow.start_run(run_name=run.name, tags=tags) as active:
        mlflow.log_params({k: v for k, v in run.params.items() if v is not None})
        metrics = {k: float(v) for k, v in run.metrics.items() if v is not None}
        mlflow.log_metrics(metrics, step=run.step)
        for path in run.artifacts:
            mlflow.log_artifact(str(path))
        return active.info.run_id
