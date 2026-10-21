# DATA-001 · Download, EDA curta e split Referência / Produção

- Etapa: 1 (base para todas as etapas)
- Status: concluída
- Data: 21/10/2026

## Objetivo
Baixar o dataset UCI Default of Credit Card Clients de forma reprodutível, gerar uma EDA curta
que alimente o contrato de dados (DQ-001) e separar fisicamente **Referência** (treino) e
**Produção** (onde o drift será injetado no DRIFT-001). Atende a boa prática obrigatória
"separação clara Referência vs Produção".

## Conceito por trás (didático)
O modelo só conhece o mundo pela Referência. A Produção é "o futuro": dados que ele nunca viu.
Se treinarmos com qualquer linha da Produção, o futuro vaza para o passado (*data leakage*) e
toda medição de drift fica viciada, como um aluno que viu a prova antes. Por isso o split é feito
**uma vez**, com `seed` fixa, gravado em disco, e os dois conjuntos não compartilham nenhum `ID`.

Como o dataset não tem data, a Produção nasce como uma amostra *sem* drift (mesma distribuição).
Isso é proposital: é o grupo de controle. No DRIFT-001 aplicamos deslocamentos conhecidos a ela;
sabendo a "resposta certa", conferimos se o detector acha.

## Escopo
- Dentro:
  - `data/raw/credit_default.parquet`: dado original com colunas renomeadas (`X1..X23` para
    `LIMIT_BAL..PAY_AMT6`, `Y` para `default`), sem nenhuma limpeza.
  - Split estratificado por `default`, 70% Referência / 30% Produção, `seed=42`.
  - `data/reference/reference.parquet`, `data/production/production_base.parquet`.
  - `data/split_metadata.json`: contagens, taxa de default, seed, hash SHA-256 do raw.
  - `reports/eda/eda_summary.md` (versionado): tamanho, nulos, duplicados, desbalanceamento,
    códigos fora do dicionário em `EDUCATION`, `MARRIAGE`, `PAY_*`.
  - Testes unitários do split (sem rede).
- Fora:
  - Limpeza ou recodificação de categorias: é decisão do contrato (DQ-001) e do pré-processamento (ML-001).
  - Lotes com drift e lote corrompido: DRIFT-001 e DQ-002.

## Decisões
- **70/30:** a Referência (21.000) ainda é dividida em treino/validação no ML-001; a Produção
  (9.000) é grande o bastante para o PSI/KS terem poder estatístico, e permite fatiar em lotes.
- **Estratificado:** garante a mesma taxa de default (~22%) nos dois lados; sem isso, uma
  diferença no alvo poderia ser confundida com concept drift.
- **Parquet:** preserva tipos (int continua int), é compacto e lido rápido. CSV perderia tipos.
- **Raw sem limpeza:** o raw é imutável; transformações acontecem depois e são rastreáveis.

## Passos
1. `config.py` com caminhos e constantes (seed, proporção).
2. `data/download.py`: baixa, renomeia, salva raw.
3. `data/split.py`: split estratificado + metadata.
4. `data/eda.py`: resumo em Markdown.
5. `scripts/prepare_data.py`: ponto de entrada que roda 2, 3 e 4.
6. Testes em `tests/test_split.py`.

## Critérios de aceite (verificáveis)
- [x] Raw com 30.000 linhas e 25 colunas (`ID`, 23 features, `default`)
- [x] Referência 21.000 + Produção 9.000 = 30.000, sem `ID` em comum
- [x] Taxa de default igual nos dois lados (diferença < 0,1 p.p.)
- [x] Rodar duas vezes gera os mesmos `ID` em cada lado (determinismo)
- [x] `reports/eda/eda_summary.md` lista os códigos não documentados
- [x] `uv run pytest -q` passa; ruff limpo

## Como validar de verdade
```
uv run python scripts/prepare_data.py
uv run python -c "import pandas as pd; r=pd.read_parquet('data/reference/reference.parquet'); p=pd.read_parquet('data/production/production_base.parquet'); print(len(r), len(p), len(set(r.ID)&set(p.ID)), r.default.mean(), p.default.mean())"
uv run pytest -q
```

## Riscos e perguntas em aberto
- Se o `ucimlrepo` sair do ar, o pipeline para. Mitigação futura (IMP): cache do raw ou URL direta do UCI.

## Resultado (preencher ao concluir)
Concluído em 21/10/2026.
- Raw: 30.000 x 25, 0 nulos, 0 IDs duplicados, todas as colunas `int64`. SHA-256 `1d3c191c...`.
- Referência 21.000 / Produção 9.000, taxa de default 22,12% nos dois (diferença 0,00 p.p.), 0 IDs em comum.
- Determinismo: segunda execução reaproveitou o raw e gerou `reference.parquet` com o mesmo hash.
- Achados da EDA (detalhe em `reports/eda/eda_summary.md`):
  - `EDUCATION` 0/5/6 (345 clientes) e `MARRIAGE` 0 (54) fora do dicionário.
  - `PAY_*` -2 e 0 muito frequentes (não são ruído, são categorias reais não documentadas).
  - 1.930 clientes com fatura negativa (crédito a favor).
  - **Não previsto:** 35 linhas idênticas ignorando o ID. Pergunta para o DQ-001: duplicata
    ou coincidência de perfil? Não removemos (raw imutável).
- Testes: 6 novos em `tests/test_split.py` (9 no total), sem rede.
