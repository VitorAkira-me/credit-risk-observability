"""AWS-003: gera os lotes da prova real na AWS, no tamanho em que as réguas foram calibradas.

O que faz: grava em outputs/aws/ um lote de controle, um de concept drift e um corrompido.
Por que existe: as réguas de alerta valem para lotes de 2.000 linhas, e os lotes do DRIFT-001 têm
9.000. Enviar um lote de outro tamanho à função dá erro de propósito (ADR-007).
Onde entra no fluxo: depois de prepare_data.py; os arquivos são enviados ao S3 à mão, na prova real.

Uso:
    uv run python scripts/make_aws_batches.py

Exit code (o número que o programa devolve ao terminar): 0 = lotes gravados.
"""

from pathlib import Path
import sys

import pandas as pd

from credit_risk_observability.config import (
    OUTPUTS_DIR,
    PRODUCTION_BASE_PATH,
    SEED,
    WEEKLY_BATCH_SIZE,
)
from credit_risk_observability.contracts.corrupt import inject_defects
from credit_risk_observability.drift.scenarios import apply_concept_drift


def build_batches(base: pd.DataFrame, batch_size: int, seed: int) -> dict[str, pd.DataFrame]:
    """Monta os três lotes da prova real.

    Recebe: a Produção-base, o tamanho do lote e a seed (número que fixa o sorteio).
    Faz: embaralha uma vez e fatia em partes disjuntas, para nenhum cliente repetir entre os lotes.
        O de concept drift muda só os rótulos; o corrompido recebe os defeitos do DQ-002.
    Devolve: {"controle": ..., "concept_drift": ..., "corrompido": ...}.
    """
    shuffled = base.sample(frac=1, random_state=seed).reset_index(drop=True)
    control = shuffled.iloc[:batch_size].reset_index(drop=True)
    concept_source = shuffled.iloc[batch_size : 2 * batch_size].reset_index(drop=True)
    concept, _ = apply_concept_drift(concept_source, 1.0, seed)
    corrupted_source = shuffled.iloc[2 * batch_size :].reset_index(drop=True)
    corrupted, _ = inject_defects(corrupted_source, batch_size=1_000, seed=seed)
    return {"controle": control, "concept_drift": concept, "corrompido": corrupted}


def main(base_path: Path = PRODUCTION_BASE_PATH, output_dir: Path = OUTPUTS_DIR / "aws") -> int:
    """Grava os lotes.

    Recebe: o caminho da Produção-base e a pasta de saída (fora do git).
    Faz: monta os lotes e grava um parquet para cada um.
    Devolve: o exit code 0.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    batches = build_batches(pd.read_parquet(base_path), WEEKLY_BATCH_SIZE, SEED)
    for name, batch in batches.items():
        batch.to_parquet(output_dir / f"{name}.parquet", index=False)
        print(f"Lote {name}: {len(batch)} linhas em {output_dir / f'{name}.parquet'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
