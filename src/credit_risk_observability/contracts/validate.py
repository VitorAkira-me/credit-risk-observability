"""Aplica o contrato a um lote e devolve um resultado legível (em vez de uma exceção crua).

O que faz: roda as regras do contrato em um lote e organiza as falhas por regra.
Por que existe: quem chama recebe "passou ou não, e por quê", sem precisar conhecer o Pandera.
Onde entra no fluxo: scripts/run_validation.py e scripts/make_drift_batch.py chamam validate_batch.
"""

from dataclasses import dataclass, field

import pandas as pd
import pandera.pandas as pa

from credit_risk_observability.contracts.schema import SCHEMA


@dataclass
class ValidationResult:
    """Resultado da validação de um lote."""

    passed: bool  # True se o lote passou em todas as regras
    rows: int  # linhas do lote
    # Uma linha por falha. default_factory cria uma tabela vazia nova a cada resultado.
    failure_cases: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def failures_by_rule(self) -> dict[str, int]:
        """Quantas ocorrências cada regra (coluna + checagem) barrou.

        Recebe: nada; usa failure_cases.
        Faz: junta a coluna e a checagem de cada falha e conta as repetições.
        Devolve: um dicionário. Exemplo: {"AGE:in_range(18, 100)": 50}.
        """
        if self.failure_cases.empty:
            return {}
        fc = self.failure_cases
        # Falhas do lote inteiro (coluna faltando, lote vazio) vêm com contexto DataFrameSchema
        column = fc["column"].astype(str).where(fc["schema_context"] == "Column", "<lote>")
        keys = column + ":" + fc["check"].astype(str)
        return {k: int(v) for k, v in keys.value_counts().sort_index().items()}

    @property
    def rejected_rows(self) -> int:
        """Quantas linhas distintas têm ao menos uma falha.

        Recebe: nada; usa failure_cases.
        Faz: conta os índices distintos. Uma falha sem índice (tipo errado, coluna faltando) atinge
            a coluna inteira, então nenhuma linha do lote é confiável e todas contam.
        Devolve: um inteiro. Exemplo: 3 falhas na mesma linha contam 1.
        """
        if self.failure_cases.empty:
            return 0
        index = self.failure_cases["index"]
        if index.isna().any():
            return self.rows
        return int(index.nunique())


def validate_batch(df: pd.DataFrame, schema: pa.DataFrameSchema = SCHEMA) -> ValidationResult:
    """lazy=True coleta todas as violações de uma vez, em vez de parar na primeira.

    Recebe: o lote e o contrato.
    Faz: valida e transforma a exceção do Pandera em um resultado comum.
    Devolve: um ValidationResult. Exemplo: um lote limpo volta com passed=True e sem falhas.
    """
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        return ValidationResult(passed=False, rows=len(df), failure_cases=exc.failure_cases)
    return ValidationResult(passed=True, rows=len(df))
