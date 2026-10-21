"""Gera um lote corrompido com defeitos conhecidos e contados (DQ-002).

Cada defeito cai em linhas **diferentes** das outras: assim a contagem esperada por regra é
exata e, se a validação reportar outro número, o bug está no contrato ou neste gerador.
"""

import numpy as np
import pandas as pd

from credit_risk_observability.config import ID_COLUMN

DEFECTS = {
    "underage": 50,  # AGE = 15
    "null_limit": 30,  # LIMIT_BAL nulo
    "unknown_sex": 10,  # SEX = 3
    "duplicated_rows": 20,  # linhas copiadas (mesmo ID)
}


def inject_defects(
    df: pd.DataFrame, batch_size: int, seed: int
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Amostra `batch_size` linhas e injeta DEFECTS. Devolve o lote e as contagens esperadas."""
    rng = np.random.default_rng(seed)
    batch = df.sample(n=batch_size, random_state=seed).reset_index(drop=True)

    positions = rng.permutation(batch_size)
    groups, start = {}, 0
    for name, n in DEFECTS.items():
        groups[name] = positions[start : start + n]
        start += n

    batch.loc[groups["underage"], "AGE"] = 15
    batch["LIMIT_BAL"] = batch["LIMIT_BAL"].astype("float64")  # int não guarda NaN
    batch.loc[groups["null_limit"], "LIMIT_BAL"] = np.nan
    batch.loc[groups["unknown_sex"], "SEX"] = 3
    copies = batch.loc[groups["duplicated_rows"]]
    batch = pd.concat([batch, copies], ignore_index=True)

    expected = {
        "AGE:in_range(18, 100)": DEFECTS["underage"],
        "LIMIT_BAL:not_nullable": DEFECTS["null_limit"],
        # Com nulos, o Pandera atribui a falha de tipo a cada linha nula (o NaN é o que impede o
        # int64). Sem nulos, uma coluna float daria 1 falha só, para a coluna inteira.
        "LIMIT_BAL:dtype('int64')": DEFECTS["null_limit"],
        "SEX:isin([1, 2])": DEFECTS["unknown_sex"],
        # report_duplicates="all": original e cópia contam, 2 por par
        f"{ID_COLUMN}:field_uniqueness": 2 * DEFECTS["duplicated_rows"],
    }
    return batch, expected
