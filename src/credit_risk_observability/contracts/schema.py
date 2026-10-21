"""Contrato de dados da entrada do modelo (DQ-001).

O contrato barra o que é **impossível ou ilegível** para o pipeline: coluna faltando, tipo
errado, nulo, ID repetido, valor fora do domínio. Ele **não** barra mudança de distribuição
(renda média caiu, mais clientes jovens): isso é drift e é papel do Evidently (Etapa 2).

Códigos legados que já existem na Referência (EDUCATION 0/5/6, MARRIAGE 0, PAY_* -2/0) são
aceitos: barrá-los rejeitaria clientes reais que o modelo foi treinado para atender.
"""

import pandera.pandas as pa

from credit_risk_observability.config import (
    BILL_COLUMNS,
    ID_COLUMN,
    PAY_AMOUNT_COLUMNS,
    PAY_STATUS_COLUMNS,
    TARGET,
)

MIN_AGE, MAX_AGE = 18, 100
SEX_CODES = [1, 2]
EDUCATION_CODES = list(range(7))  # 1 a 4 documentados; 0, 5, 6 legados vistos na EDA
MARRIAGE_CODES = list(range(4))  # 1 a 3 documentados; 0 legado
# -2 sem consumo, -1 em dia, 0 pagou o mínimo, 1 a 9 meses de atraso
PAY_STATUS_CODES = list(range(-2, 10))


def build_schema() -> pa.DataFrameSchema:
    columns = {
        # Regra: ID único (um cliente por linha no lote)
        ID_COLUMN: pa.Column(int, pa.Check.gt(0), unique=True),
        # Regra: limite de crédito obrigatório e positivo
        "LIMIT_BAL": pa.Column(int, pa.Check.gt(0)),
        "SEX": pa.Column(int, pa.Check.isin(SEX_CODES)),
        "EDUCATION": pa.Column(int, pa.Check.isin(EDUCATION_CODES)),
        "MARRIAGE": pa.Column(int, pa.Check.isin(MARRIAGE_CODES)),
        # Regra: idade mínima legal para contratar crédito
        "AGE": pa.Column(int, pa.Check.in_range(MIN_AGE, MAX_AGE)),
        **{col: pa.Column(int, pa.Check.isin(PAY_STATUS_CODES)) for col in PAY_STATUS_COLUMNS},
        # Fatura negativa é crédito a favor do cliente: sem regra de faixa, só tipo e não nulo
        **{col: pa.Column(int) for col in BILL_COLUMNS},
        # Valor pago não pode ser negativo
        **{col: pa.Column(int, pa.Check.ge(0)) for col in PAY_AMOUNT_COLUMNS},
        # Alvo é opcional: lotes de escoragem chegam sem ele; se vier, precisa ser binário
        TARGET: pa.Column(int, pa.Check.isin([0, 1]), required=False),
    }
    return pa.DataFrameSchema(
        columns,
        # Lote vazio passaria em todas as regras de coluna: o "sucesso vazio" barrado na porta
        checks=[pa.Check(lambda df: len(df) > 0, element_wise=False, name="lote_nao_vazio")],
        strict=True,  # coluna inesperada é erro, não é ignorada
        coerce=False,  # não "consertar" tipo escondido: float no lugar de int é falha
        name="credit_default_input_v1",
    )


SCHEMA = build_schema()
