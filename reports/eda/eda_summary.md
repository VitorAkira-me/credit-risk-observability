# EDA curta · Default of Credit Card Clients (UCI)

> Gerado por `scripts/prepare_data.py` a partir do raw completo. Não editar à mão.

## Visão geral

| Métrica | Valor |
|---|---|
| Linhas | 30,000 |
| Colunas | 25 |
| Nulos (total) | 0 |
| IDs duplicados | 0 |
| Linhas idênticas (ignorando ID) | 35 |
| Taxa de default | 22.12% |
| AGE (mín, máx) | 21 a 79 |
| LIMIT_BAL (mín, máx) | 10,000 a 1,000,000 |
| Clientes com alguma fatura negativa | 1,930 |

## Códigos fora do dicionário do UCI

Documentado: `EDUCATION` 1 a 4, `MARRIAGE` 1 a 3, `PAY_*` -1 (pago em dia) e 1 a 9
(meses de atraso). Os valores abaixo existem nos dados, mas não são explicados.

| Coluna | Código: contagem |
|---|---|
| EDUCATION | `0`: 14, `5`: 280, `6`: 51 |
| MARRIAGE | `0`: 54 |
| PAY_0 | `-2`: 2,759, `0`: 14,737 |
| PAY_2 | `-2`: 3,782, `0`: 15,730 |
| PAY_3 | `-2`: 4,085, `0`: 15,764 |
| PAY_4 | `-2`: 4,348, `0`: 16,455 |
| PAY_5 | `-2`: 4,546, `0`: 16,947 |
| PAY_6 | `-2`: 4,895, `0`: 16,286 |

## Taxa de default por grupo (insumo para a análise de viés)

**SEX**

| Código | Clientes | Taxa de default |
|---|---|---|
| 1 | 11,888 | 24.17% |
| 2 | 18,112 | 20.78% |

**EDUCATION**

| Código | Clientes | Taxa de default |
|---|---|---|
| 0 | 14 | 0.00% |
| 1 | 10,585 | 19.23% |
| 2 | 14,030 | 23.73% |
| 3 | 4,917 | 25.16% |
| 4 | 123 | 5.69% |
| 5 | 280 | 6.43% |
| 6 | 51 | 15.69% |

**MARRIAGE**

| Código | Clientes | Taxa de default |
|---|---|---|
| 0 | 54 | 9.26% |
| 1 | 13,659 | 23.47% |
| 2 | 15,964 | 20.93% |
| 3 | 323 | 26.01% |

## Implicações

- **Desbalanceamento:** com ~22% de default, acurácia engana (um modelo que sempre diz
  'paga' acerta 78%). Usar AUC e recall da classe default no ML-001.
- **Códigos não documentados:** o contrato (DQ-001) precisa decidir se `EDUCATION` 0/5/6
  e `MARRIAGE` 0 são aceitos (dado legado conhecido) ou bloqueados. Em `PAY_*`, -2 e 0
  são lidos pela literatura como 'sem consumo' e 'pagou o mínimo': aceitar.
- **Faturas negativas** são crédito a favor do cliente, não erro: o contrato não deve
  exigir `BILL_AMT >= 0`.
