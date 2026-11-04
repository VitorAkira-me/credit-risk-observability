"""DRIFT-001: gera um lote de Produção com drift, valida no contrato e registra um manifesto.

O que faz: lê a Produção-base, aplica um cenário (data_drift ou concept_drift), confere o lote no
contrato de dados e salva o lote e o manifesto (o registro de como o lote foi gerado).
Por que existe: o detector de drift (DRIFT-002) precisa de lotes com "resposta certa" conhecida.
Onde entra no fluxo: depois de prepare_data.py e antes do relatório de drift.

Uso:
    uv run python scripts/make_drift_batch.py --scenario data_drift --intensity 1
    uv run python scripts/make_drift_batch.py --scenario concept_drift --intensity 0.5

Exit code (o número que o programa devolve ao terminar): 0 = lote salvo; 1 = lote reprovado no
contrato e nada gravado, porque drift deve ser "diferente mas possível", nunca dado sujo.
"""

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from credit_risk_observability.config import (
    DRIFT_REPORTS_DIR,
    PRODUCTION_BASE_PATH,
    PRODUCTION_DIR,
    SEED,
)
from credit_risk_observability.contracts.schema import SCHEMA
from credit_risk_observability.contracts.validate import validate_batch
from credit_risk_observability.data.split import file_sha256
from credit_risk_observability.drift.scenarios import (
    apply_concept_drift,
    apply_data_drift,
    validate_intensity,
)
from credit_risk_observability.monitoring.events import log_event, new_run_id

logger = logging.getLogger("make_drift_batch")

SCENARIOS = ("data_drift", "concept_drift")


def build_batch_name(scenario: str, intensity: float) -> str:
    """Monta o nome do lote a partir do cenário e da intensidade.

    Recebe: o cenário e a intensidade.
    Faz: exige no máximo duas casas decimais, porque 0,333 e 0,33 gerariam o mesmo nome (i033), e
        um lote sobrescreveria o outro em silêncio.
    Devolve: o nome sem extensão. Exemplo: data_drift com 1 vira "batch_data_drift_i100".
    """
    percent = intensity * 100
    if abs(percent - round(percent)) > 1e-9:
        raise ValueError(f"Use intensidade com no máximo duas casas decimais; recebi {intensity}")
    return f"batch_{scenario}_i{round(percent):03d}"


def build_manifest(
    run_id: str,
    args: argparse.Namespace,
    details: dict,
    base_path: Path,
    batch_path: Path,
    rows: int,
) -> dict:
    """Monta o registro de como o lote foi gerado.

    Recebe: a identificação da execução, os argumentos, os detalhes do cenário e os caminhos.
    Faz: junta parâmetros, hashes (impressão digital do arquivo) e versões. Traz só números
        agregados, nunca valores de linhas, porque este arquivo é versionado (ADR-005).
    Devolve: um dicionário pronto para virar JSON.
    """
    return {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "scenario": args.scenario,
        "intensity": args.intensity,
        "seed": args.seed,
        "rows": rows,
        # ** abre o dicionário aqui dentro: cada detalhe do cenário vira um campo do manifesto.
        **details,
        "contract": SCHEMA.name,
        # Só o nome do arquivo: um caminho completo publicaria detalhes da máquina no repositório.
        "base_file": base_path.name,
        "base_sha256": file_sha256(base_path),
        "batch_file": batch_path.name,
        "batch_sha256": file_sha256(batch_path),
        "versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }


def main(
    argv: list[str] | None = None,
    base_path: Path = PRODUCTION_BASE_PATH,
    production_dir: Path = PRODUCTION_DIR,
    reports_dir: Path = DRIFT_REPORTS_DIR,
) -> int:
    """Gera, valida e salva um lote.

    Recebe: os argumentos da linha de comando e os caminhos (os testes passam pastas temporárias).
    Faz: aplica o cenário, confere no contrato e só então grava o lote e o manifesto.
    Devolve: o exit code, 0 se o lote foi salvo e 1 se foi reprovado.
    """
    parser = argparse.ArgumentParser(description="Gera um lote de Produção com drift (DRIFT-001)")
    parser.add_argument("--scenario", choices=SCENARIOS, required=True, help="tipo de drift")
    parser.add_argument("--intensity", type=float, default=1.0, help="de 0 (nada) a 1 (cheio)")
    parser.add_argument("--seed", type=int, default=SEED, help="fixa o sorteio do concept drift")
    args = parser.parse_args(argv)

    validate_intensity(args.intensity)
    batch_name = build_batch_name(args.scenario, args.intensity)
    # run_id: identifica esta execução e liga o log ao manifesto (prepara o OBS-001).
    run_id = new_run_id()

    base = pd.read_parquet(base_path)
    if args.scenario == "data_drift":
        batch, details = apply_data_drift(base, args.intensity)
    else:
        batch, details = apply_concept_drift(base, args.intensity, args.seed)

    # O contrato vem antes de gravar: um lote reprovado nunca chega ao disco.
    result = validate_batch(batch)
    fields = {"run_id": run_id, "batch": batch_name, "rows": result.rows}
    if not result.passed:
        log_event(
            logger,
            "drift_batch_rejected",
            level=logging.ERROR,
            **fields,
            failures_by_rule=result.failures_by_rule,
        )
        print(f"Lote {batch_name} REPROVADO no contrato: {result.failures_by_rule}")
        return 1

    production_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    batch_path = production_dir / f"{batch_name}.parquet"
    batch.to_parquet(batch_path, index=False)

    manifest = build_manifest(run_id, args, details, base_path, batch_path, len(batch))
    manifest_path = reports_dir / f"{batch_name}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    log_event(
        logger,
        "drift_batch_generated",
        **fields,
        scenario=args.scenario,
        intensity=args.intensity,
        labels_flipped=details["labels_flipped"],
    )
    print(
        f"Lote {batch_name}: {len(batch)} linhas, aprovado no contrato. "
        f"Faturas x {details['bill_factor']:.4f}, limite x {details['limit_factor']:.4f}, "
        f"{details['labels_flipped']} rótulos trocados. Manifesto: {manifest_path.name}"
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    sys.exit(main())
