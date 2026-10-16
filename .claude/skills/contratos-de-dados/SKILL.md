---
name: contratos-de-dados
description: Use na Etapa 1 (cards DQ-001 e DQ-002) para criar o contrato de dados com Pandera, injetar um lote corrompido e provar que a ingestão é bloqueada.
---

# Contratos de dados (Etapa 1, 25% da nota)

## Ideia central
O contrato é a porta de entrada do pipeline. Ele roda **antes** do modelo. Se o lote falha,
o pipeline para com erro explícito e nada chega ao modelo. "Lixo entra, lixo sai" vira
"lixo não entra".

## Requisitos do desafio
- Pelo menos **3 regras rígidas** (ex.: idade ≥ 18, renda/limite não nulo e positivo, sem duplicatas).
- Demonstrar um lote com erros **falhando e sendo bloqueado**.

## Receita (Pandera)
- Schema em `src/credit_obs/contracts/schema.py` usando `pandera.pandas.DataFrameSchema`
  (ou `DataFrameModel` se preferir estilo classe). Confira a versão instalada antes: a API
  de import mudou entre versões (`import pandera.pandas as pa` nas mais novas).
- Use `strict=True` para rejeitar colunas inesperadas e `coerce=False` para não "consertar" tipos escondido.
- Valide com `schema.validate(df, lazy=True)`: `lazy=True` coleta **todos** os erros de uma vez
  (`SchemaErrors.failure_cases`) em vez de parar no primeiro. Isso vira um relatório útil.
- Duplicatas: `unique=[...]` no schema ou checagem de `df.duplicated()` no nível do DataFrame.
- Regras de domínio sugeridas para o dataset UCI Taiwan: `AGE` entre 18 e 100, `LIMIT_BAL > 0`
  e não nulo, `SEX` em {1, 2}, `EDUCATION` e `MARRIAGE` em conjuntos permitidos (o dataset
  original tem códigos não documentados, ótimo achado para a EDA), alvo binário em {0, 1}, `ID` único.

## Lote corrompido
Script `scripts/make_corrupted_batch.py` gera um parquet em `data/production/` a partir da
Referência com defeitos **conhecidos e contados** (ex.: 50 idades = 15, 30 limites nulos, 20 linhas duplicadas).
A validação precisa reportar exatamente esses números. Se não bater, há bug no contrato ou no gerador.

## Bloqueio de ingestão
`scripts/run_validation.py <arquivo>`:
- passa: grava log `validation_passed`, exit code 0, segue o fluxo;
- falha: grava log `validation_failed` com contagem por regra, salva `failure_cases` em
  `reports/validation/`, **exit code 1** (é isso que um orquestrador ou CI usa para parar).

## Testes mínimos
- lote limpo passa;
- cada regra tem um teste que a viola isoladamente e falha;
- lote corrompido falha com as contagens esperadas.

## Pergunta para deixar no ar
Bloquear o lote inteiro por 1 linha ruim é sempre certo? Quando faria sentido colocar as linhas
ruins em "quarentena" e deixar o resto passar?
