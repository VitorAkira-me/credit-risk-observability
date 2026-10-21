# credit-risk-observability

Camada de sustentação de um modelo de **Credit Scoring** em produção: contratos de qualidade de
dados, simulação e detecção de drift, observabilidade do pipeline e governança (LGPD).
Tech Challenge Fase 4 (Pós-tech ML).

> Status: em construção. Etapas concluídas: preparação de dados e modelo baseline.
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
