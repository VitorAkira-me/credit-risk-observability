# credit-risk-observability

Camada de sustentação de um modelo de **Credit Scoring** em produção: contratos de qualidade de
dados, simulação e detecção de drift, observabilidade do pipeline e governança (LGPD).
Tech Challenge Fase 4 (Pós-tech ML).

> Status: em construção. Concluído: dados, baseline e Etapa 1 (contrato de dados).
> Andamento em [`docs/STATUS.md`](docs/STATUS.md) e [`docs/KANBAN.md`](docs/KANBAN.md).

## Dataset
[Default of Credit Card Clients (UCI, Taiwan)](https://archive.ics.uci.edu/dataset/350):
30.000 clientes, alvo binário `default` (22,12% de inadimplência). Baixado sem login via
`ucimlrepo`. Escolha justificada em [ADR-001](docs/decisions/ADR-001-dataset.md).

## Como rodar
Pré-requisito: [uv](https://docs.astral.sh/uv/). O uv instala o Python 3.12 se precisar.
Os comandos funcionam iguais no PowerShell e no Git Bash.

```
uv sync                                   # ambiente com versões fixadas pelo uv.lock
uv run python scripts/prepare_data.py     # download, EDA e split Referência / Produção
uv run python scripts/train_baseline.py   # treina o baseline e salva métricas
uv run python scripts/make_corrupted_batch.py                            # lote com defeitos conhecidos
uv run python scripts/run_validation.py data/production/batch_corrupted.parquet   # exit 1: bloqueado
uv run pytest -q                          # testes
uv run ruff check . ; uv run ruff format --check .
```

## Referência vs Produção
| Conjunto | Arquivo | Linhas | Uso |
|---|---|---|---|
| Referência | `data/reference/reference.parquet` | 21.000 | treino e validação do modelo |
| Produção | `data/production/production_base.parquet` | 9.000 | nunca entra no treino; base para os lotes com drift |

Split estratificado (seed 42), 0 clientes em comum. Detalhes em [DATA-001](docs/specs/DATA-001.md);
EDA em [`reports/eda/eda_summary.md`](reports/eda/eda_summary.md).

## Modelo baseline
LogisticRegression balanceada. `SEX` e `MARRIAGE` ficam fora das features
([ADR-004](docs/decisions/ADR-004-features-sensiveis.md)).

| Conjunto | AUC | KS | Recall default |
|---|---|---|---|
| Validação | 0,732 | 0,384 | 0,657 |
| Produção sem drift | 0,715 | 0,365 | 0,640 |

Métricas completas em [`models/baseline_metrics.json`](models/baseline_metrics.json) e [ML-001](docs/specs/ML-001.md).

## Etapa 1 · Contrato de dados
Schema Pandera `credit_default_input_v1` com 9 regras rígidas (colunas exatas, `int64` sem
nulos, `ID` único, `AGE` 18 a 100, `LIMIT_BAL` > 0, domínio dos códigos, `PAY_AMT` ≥ 0, alvo
binário, lote não vazio). Regras e decisões em [DQ-001](docs/specs/DQ-001.md).

`scripts/run_validation.py` é o portão de ingestão: lote limpo sai com exit 0; lote inválido sai
com **exit 1**, log `validation_failed` e falhas em `reports/validation/`.

| Lote | Linhas | Resultado | Falhas por regra |
|---|---|---|---|
| Produção-base | 9.000 | aprovado (exit 0) | nenhuma |
| Corrompido | 1.020 | **bloqueado (exit 1)** | AGE 50, ID duplicado 40, LIMIT_BAL nulo 30 (+30 de tipo), SEX 10 |

As contagens batem exatamente com os defeitos injetados ([DQ-002](docs/specs/DQ-002.md)).

## Estrutura
```
src/credit_risk_observability/   # pacote: config, data/, model/ (contracts/, drift/, monitoring/ a seguir)
scripts/                         # pontos de entrada do pipeline
tests/                           # pytest
reports/                         # evidências versionadas (EDA, relatórios de drift)
models/                          # métricas versionadas; modelo .joblib regerável
docs/                            # STATUS, KANBAN, GLOSSARIO, specs/ e decisions/ (ADRs)
data/                            # fora do git (regerável pelos scripts)
```

## Governança (LGPD, vieses, análise causal)
Será escrita no card GOV-001.
