"""EDA curta: só o que alimenta decisões (contrato de dados, modelo, viés)."""

import pandas as pd

from credit_risk_observability.config import (
    BILL_COLUMNS,
    CATEGORICAL_COLUMNS,
    DOCUMENTED_CODES,
    ID_COLUMN,
    TARGET,
)


def undocumented_codes(df: pd.DataFrame) -> dict[str, dict[int, int]]:
    """Para cada coluna codificada, conta os valores que o dicionário do UCI não explica."""
    result = {}
    for col, allowed in DOCUMENTED_CODES.items():
        counts = df.loc[~df[col].isin(allowed), col].value_counts().sort_index()
        if not counts.empty:
            result[col] = {int(k): int(v) for k, v in counts.items()}
    return result


def summarize(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "columns": df.shape[1],
        "nulls": int(df.isna().sum().sum()),
        "duplicated_ids": int(df[ID_COLUMN].duplicated().sum()),
        "duplicated_rows_without_id": int(df.drop(columns=ID_COLUMN).duplicated().sum()),
        "default_rate": float(df[TARGET].mean()),
        "age_range": (int(df["AGE"].min()), int(df["AGE"].max())),
        "limit_bal_range": (int(df["LIMIT_BAL"].min()), int(df["LIMIT_BAL"].max())),
        "negative_bills": int((df[BILL_COLUMNS] < 0).any(axis=1).sum()),
        "undocumented_codes": undocumented_codes(df),
        "default_rate_by_group": {
            col: df.groupby(col)[TARGET].agg(["count", "mean"]).to_dict("index")
            for col in CATEGORICAL_COLUMNS
        },
    }


def render_markdown(s: dict) -> str:
    lines = [
        "# EDA curta · Default of Credit Card Clients (UCI)",
        "",
        "> Gerado por `scripts/prepare_data.py` a partir do raw completo. Não editar à mão.",
        "",
        "## Visão geral",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Linhas | {s['rows']:,} |",
        f"| Colunas | {s['columns']} |",
        f"| Nulos (total) | {s['nulls']} |",
        f"| IDs duplicados | {s['duplicated_ids']} |",
        f"| Linhas idênticas (ignorando ID) | {s['duplicated_rows_without_id']} |",
        f"| Taxa de default | {s['default_rate']:.2%} |",
        f"| AGE (mín, máx) | {s['age_range'][0]} a {s['age_range'][1]} |",
        f"| LIMIT_BAL (mín, máx) | {s['limit_bal_range'][0]:,} a {s['limit_bal_range'][1]:,} |",
        f"| Clientes com alguma fatura negativa | {s['negative_bills']:,} |",
        "",
        "## Códigos fora do dicionário do UCI",
        "",
        "Documentado: `EDUCATION` 1 a 4, `MARRIAGE` 1 a 3, `PAY_*` -1 (pago em dia) e 1 a 9",
        "(meses de atraso). Os valores abaixo existem nos dados, mas não são explicados.",
        "",
        "| Coluna | Código: contagem |",
        "|---|---|",
    ]
    for col, counts in s["undocumented_codes"].items():
        pretty = ", ".join(f"`{k}`: {v:,}" for k, v in counts.items())
        lines.append(f"| {col} | {pretty} |")

    lines += ["", "## Taxa de default por grupo (insumo para a análise de viés)", ""]
    for col, groups in s["default_rate_by_group"].items():
        lines += [f"**{col}**", "", "| Código | Clientes | Taxa de default |", "|---|---|---|"]
        for code, row in groups.items():
            lines.append(f"| {code} | {int(row['count']):,} | {row['mean']:.2%} |")
        lines.append("")

    lines += [
        "## Implicações",
        "",
        "- **Desbalanceamento:** com ~22% de default, acurácia engana (um modelo que sempre diz",
        "  'paga' acerta 78%). Usar AUC e recall da classe default no ML-001.",
        "- **Códigos não documentados:** o contrato (DQ-001) precisa decidir se `EDUCATION` 0/5/6",
        "  e `MARRIAGE` 0 são aceitos (dado legado conhecido) ou bloqueados. Em `PAY_*`, -2 e 0",
        "  são lidos pela literatura como 'sem consumo' e 'pagou o mínimo': aceitar.",
        "- **Faturas negativas** são crédito a favor do cliente, não erro: o contrato não deve",
        "  exigir `BILL_AMT >= 0`.",
        "",
    ]
    return "\n".join(lines)
