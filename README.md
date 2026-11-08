# credit-risk-observability

[![CI](https://github.com/VitorAkira-me/credit-risk-observability/actions/workflows/ci.yml/badge.svg)](https://github.com/VitorAkira-me/credit-risk-observability/actions/workflows/ci.yml)
[![Pipeline de monitoramento](https://github.com/VitorAkira-me/credit-risk-observability/actions/workflows/pipeline.yml/badge.svg)](https://github.com/VitorAkira-me/credit-risk-observability/actions/workflows/pipeline.yml)

Camada de sustentação de um modelo de **Credit Scoring** em produção: contratos de qualidade de
dados, simulação e detecção de drift, observabilidade do pipeline e governança (LGPD).
Tech Challenge Fase 4 (Pós-tech ML).

> Status: em construção. Concluído: dados, baseline, Etapa 1 (contrato), Etapa 2 (drift) e o
> monitoramento da Etapa 3 (log estruturado e MLflow).
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
uv run python scripts/make_drift_batch.py --scenario data_drift --intensity 1      # lote com data drift
uv run python scripts/make_drift_batch.py --scenario concept_drift --intensity 1   # lote com concept drift
uv run python scripts/run_drift_report.py data/production/production_base.parquet          # controle
uv run python scripts/run_drift_report.py data/production/batch_data_drift_i100.parquet    # relatório de data drift
uv run python scripts/run_drift_report.py data/production/batch_concept_drift_i100.parquet # relatório de concept drift
uv run python scripts/calibrate_alerts.py      # réguas de alerta para lotes de 2.000 (Etapa 3)
uv run python scripts/run_weekly_pipeline.py   # 5 semanas simuladas, cada uma vira um run do MLflow
uv run python scripts/plot_weekly_panel.py     # painel estático em reports/figures/
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db   # painel vivo em http://localhost:5000
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

## Relatórios de drift: o que fica no git
Os 3 relatórios de `reports/drift/drift_report_*` são a evidência da Etapa 2: ficam versionados e não
devem ser regerados em PRs futuros, porque cada regeneração soma cerca de 4,7 MB ao histórico.
Desde o OBS-001, `scripts/run_drift_report.py` grava por padrão em `outputs/drift/`, fora do git, e não
toca na evidência. No OBS-002, esses relatórios viram artefatos do MLflow.

## Log estruturado do pipeline (OBS-001)
Cada etapa (`validacao`, `geracao_lote_drift`, `relatorio_drift`) grava uma linha JSON em
`logs/pipeline.jsonl`, sempre com os mesmos campos:

| Campo | O que é |
|---|---|
| `timestamp` | fim da etapa, em UTC |
| `run_id` | identifica a execução e liga o log ao manifesto e ao relatório |
| `etapa` / `evento` | qual parte rodou e o que aconteceu (ex.: `validation_failed`) |
| `status` | `sucesso` ou `falha`; exceção inesperada também vira `falha` |
| `duracao_s` | latência da etapa, em segundos |
| `linhas_entrada` / `linhas_rejeitadas` | volume que entrou e linhas com falha no contrato |
| `detalhe` | lote, motivo, falhas por regra, diagnóstico de drift |

O log guarda só contagens, nomes de regra e nomes de arquivo: nenhum ID nem valor de linha (Etapa 4).

## Etapa 3 · Monitoramento semanal no MLflow (OBS-002)
A Produção-base vira 4 semanas de 2.000 clientes, sem cliente repetido, com drift crescente
(semana 1 sem drift; semana 4 com o data drift e o concept drift cheios do DRIFT-001), mais uma
semana com lote corrompido. Cada semana passa pelo contrato, pelo relatório de drift e pelas réguas
de alerta, e vira um run do MLflow com o mesmo `run_id` do `logs/pipeline.jsonl`.

![Painel das semanas](reports/figures/painel_semanas.png)

| Régua | Dispara quando | Por quê | Alarme falso medido* |
|---|---|---|---|
| `drift_alert` (PSI) | PSI > 0,25 em alguma feature | mudança grande na distribuição (limite usual em crédito) | (não calibrado) |
| `alerta_ks` | p < 0,0025 (0,05 / 20, Bonferroni) e D > D mínimo | 20 testes por lote: com p < 0,05 a régua antiga alarmava em 24,5% das semanas sem drift | 1,5% |
| `alerta_auc` | AUC < 0,687 | piso do bootstrap da Produção-base com n = 2.000 (percentil 2,5) | 3,5% |
| `alerta_taxa_default` | taxa fora de 20,6% a 23,6% | o PSI do alvo não vê 22% virar 27% (concept drift) | 7,0% |

\* Em 200 amostras sem drift que a calibração não viu. Limites em
[`reports/monitoring/alert_thresholds.json`](reports/monitoring/alert_thresholds.json).

| Semana | Drift | AUC | Default | PSI máx | Alertas |
|---|---|---|---|---|---|
| 1 | nenhum | 0,728 | 21,9% | 0,02 | nenhum |
| 2 | 1/3 | 0,701 | 23,4% | 0,05 | KS (`LIMIT_BAL`, `BILL_AMT1`) |
| 3 | 2/3 | 0,685 | 27,0% | 0,18 | KS (limite e 6 faturas), AUC, default |
| 4 | cheio | 0,662 | 27,1% | 0,30 | PSI (`LIMIT_BAL`), KS, AUC, default |
| 5 | lote corrompido | barrada no contrato (130 linhas rejeitadas) | | | `status=falha` |

Leitura: o concept drift aparece antes do data drift. Na semana 3 a AUC e a taxa de default já
alarmam, e o PSI ainda está em 0,18. Um monitoramento só de PSI perderia uma semana.

O que cada run guarda: params (lote, semana, intensidade, versão do modelo, contrato, método de
drift), métricas no eixo "semana" (latência por etapa, linhas de entrada e rejeitadas, AUC, taxa de
default, PSI por feature, nº de features com alerta) e artefatos (HTML do Evidently, eventos do
log e, na semana barrada, as falhas do contrato). `mlflow.db`, `mlartifacts/` e `outputs/` ficam
fora do git; a evidência versionada é o painel e os limites calibrados.

## CI/CD no GitHub Actions (IMP-001)
| Workflow | Quando roda | O que garante |
|---|---|---|
| [`ci.yml`](.github/workflows/ci.yml) | todo PR para a `main` e todo merge | **Qualidade:** `uv sync --locked`, ruff e pytest. **Contrato:** com os dados reais do UCI, a Produção-base passa, o lote corrompido é barrado com as falhas exatas e os lotes regerados batem com os hashes da evidência em `reports/drift/` (`scripts/check_evidence.py`). |
| [`pipeline.yml`](.github/workflows/pipeline.yml) | todo merge na `main` e manual | Roda o pipeline de monitoramento inteiro, confere que os limites calibrados não mudaram sem decisão e publica como artefato da execução: relatórios das semanas, `mlflow.db`, `mlartifacts/`, log e painel (sem o `failure_cases.csv`, que tem valores de linha). |

Um PR que afrouxa o contrato fica vermelho mesmo quando o lote corrompido continua barrado por
outras regras: o portão compara as falhas regra a regra, e não só o exit code.

## Estrutura
```
src/credit_risk_observability/   # pacote: config, data/, model/, contracts/, drift/, monitoring/
scripts/                         # pontos de entrada do pipeline
tests/                           # pytest
reports/                         # evidências versionadas (EDA, relatórios de drift)
models/                          # métricas versionadas; modelo .joblib regerável
docs/                            # STATUS, KANBAN, GLOSSARIO, specs/ e decisions/ (ADRs)
data/                            # fora do git (regerável pelos scripts)
```

## Governança (LGPD, vieses, análise causal)
Será escrita no card GOV-001.
