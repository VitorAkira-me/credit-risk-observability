"""Split Referência / Produção e metadados que provam como ele foi feito.

O que faz: separa os clientes em dois grupos sem nenhum cliente em comum.
Por que existe: o modelo treina na Referência, e o drift acontece na Produção. Se um cliente
    estivesse nos dois, haveria vazamento: o modelo pareceria melhor do que é.
Onde entra no fluxo: scripts/prepare_data.py chama estas funções depois da EDA.
"""

import hashlib
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from credit_risk_observability.config import ID_COLUMN, TARGET


def split_reference_production(
    df: pd.DataFrame, production_size: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa Referência e Produção estratificando pelo alvo (mesma taxa de default).

    Recebe: a tabela completa, a fração da Produção e a seed (número que fixa o sorteio).
    Faz: sorteia os clientes mantendo a mesma taxa de default nos dois grupos e ordena por ID.
    Devolve: (Referência, Produção). Exemplo: 30.000 clientes e 0,30 dão 21.000 e 9.000.
    """
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
    """Hash do arquivo: se o raw mudar, o metadata denuncia.

    Recebe: o caminho de um arquivo.
    Faz: calcula o SHA-256, a "impressão digital" do arquivo: mudou um byte, mudou o hash.
    Devolve: o hash como texto de 64 caracteres.
    """
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        # Lê de 1 MB em 1 MB (1 << 20 bytes), até a leitura voltar vazia, sem encher a memória.
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
    """Monta o registro de como o split foi feito.

    Recebe: o caminho do raw, os dois grupos, a fração da Produção e a seed.
    Faz: junta o hash do raw, os tamanhos, as taxas de default e os IDs em comum.
    Devolve: um dicionário pronto para virar JSON. Em shared_ids, o certo é 0.
    """
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
