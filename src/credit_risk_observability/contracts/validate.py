"""Aplica o contrato a um lote e devolve um resultado legível (em vez de uma exceção crua)."""

from dataclasses import dataclass, field

import pandas as pd
import pandera.pandas as pa

from credit_risk_observability.contracts.schema import SCHEMA


@dataclass
class ValidationResult:
    passed: bool
    rows: int
    failure_cases: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def failures_by_rule(self) -> dict[str, int]:
        """Quantas ocorrências cada regra (coluna + checagem) barrou."""
        if self.failure_cases.empty:
            return {}
        fc = self.failure_cases
        # Falhas do lote inteiro (coluna faltando, lote vazio) vêm com contexto DataFrameSchema
        column = fc["column"].astype(str).where(fc["schema_context"] == "Column", "<lote>")
        keys = column + ":" + fc["check"].astype(str)
        return {k: int(v) for k, v in keys.value_counts().sort_index().items()}


def validate_batch(df: pd.DataFrame, schema: pa.DataFrameSchema = SCHEMA) -> ValidationResult:
    """lazy=True coleta todas as violações de uma vez, em vez de parar na primeira."""
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        return ValidationResult(passed=False, rows=len(df), failure_cases=exc.failure_cases)
    return ValidationResult(passed=True, rows=len(df))
