# KANBAN · Fase 4

> Fonte de verdade das tarefas. Status: BACKLOG, TO-DO, DOING, REVIEW, DONE.
> Cada card vira uma spec em `docs/specs/<ID>.md` antes de começar.

| ID | Card | Etapa | Depende de | Status |
|---|---|---|---|---|
| SETUP-001 | Repo, `uv`, estrutura de pastas, `.gitignore`, pytest rodando | 0 | | DONE |
| ADR-001 | Escolha do dataset | 0 | | DONE |
| DATA-001 | Download + EDA curta + split Referência / Produção (salvos em parquet) | 1 | SETUP-001, ADR-001 | DONE |
| ML-001 | Modelo baseline treinado na Referência, métricas salvas em JSON | 1 | DATA-001 | DONE |
| ADR-002 | Pandera vs Great Expectations | 1 | | DONE |
| DQ-001 | Contrato de dados com ≥3 regras rígidas + testes | 1 | DATA-001, ADR-002 | DONE |
| DQ-002 | Lote corrompido injetado e ingestão bloqueada (prova com log e exit code) | 1 | DQ-001 | DONE |
| DRIFT-001 | Gerar Dataset de Produção com data drift (≥2 features) e concept drift | 2 | ML-001 | TO-DO |
| DRIFT-002 | Relatório Evidently (PSI/KS) em `reports/` + predições na produção | 2 | DRIFT-001 | BACKLOG |
| ADR-003 | MLflow vs Prometheus/Grafana | 3 | | DONE |
| ADR-004 | Atributos sensíveis fora das features do modelo | 1 | | DONE |
| OBS-001 | Logging estruturado do pipeline (sucesso, falha, volume, latência) | 3 | DQ-002 | BACKLOG |
| OBS-002 | Rastreamento (MLflow) de métricas de saúde e alertas de drift | 3 | OBS-001, DRIFT-002, ADR-003 | BACKLOG |
| GOV-001 | README: LGPD, base legal, retenção, vieses, análise causal | 4 | DRIFT-002 | BACKLOG |
| VID-001 | Roteiro STAR e gravação (≤5 min) | 4 | tudo | BACKLOG |

## Melhorias (só depois do essencial)
| ID | Ideia |
|---|---|
| IMP-001 | GitHub Actions rodando contratos e testes em todo PR |
| IMP-002 | Exportar métricas de drift para Prometheus e painel no Grafana da Fase 3 |
| IMP-003 | DAG no Airflow rodando validação + drift em lotes semanais simulados |
| IMP-004 | Gatilho de retreino quando o drift passar de um limiar |
| IMP-QUARENTENA | Quarentena: linhas ruins separadas, resto do lote segue | melhoria | DQ-002 | BACKLOG |
