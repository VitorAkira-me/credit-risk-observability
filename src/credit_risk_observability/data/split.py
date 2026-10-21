"""Split Referência / Produção e metadados que provam como ele foi feito."""

import hashlib
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from credit_risk_observability.config import ID_COLUMN, TARGET


def split_reference_production(
    df: pd.DataFrame, production_size: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa Referência e Produção estratificando pelo alvo (mesma taxa de default)."""
    if df[ID_COLUMN].duplicated().any():
        raise ValueError("IDs duplicados no raw: o split não garantiria separação por cliente")

    reference, production = train_test_split(
        df, test_size=production_size, stratify=df[TARGET], random_state=seed
    )
    return (
        reference.sort_values(ID_COLUMN).reset_index(drop=True),
        production.sort_values(ID_COLUMN).reset_index(drop=True),
    )


def file_sha256(path: Path) -> str:
    """Hash do arquivo: se o raw mudar, o metadata denuncia."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_metadata(
    raw_path: Path,
    reference: pd.DataFrame,
    production: pd.DataFrame,
    production_size: float,
    seed: int,
) -> dict:
    return {
        "raw_sha256": file_sha256(raw_path),
        "seed": seed,
        "production_size": production_size,
        "rows": {
            "reference": len(reference),
            "production_base": len(production),
            "total": len(reference) + len(production),
        },
        "default_rate": {
            "reference": round(float(reference[TARGET].mean()), 4),
            "production_base": round(float(production[TARGET].mean()), 4),
        },
        "shared_ids": len(set(reference[ID_COLUMN]) & set(production[ID_COLUMN])),
    }
