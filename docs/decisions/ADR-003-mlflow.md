# ADR-003 · Observabilidade com MLflow local primeiro

- Status: aceita
- Data: 13/10/2026

## Contexto
A Etapa 3 aceita MLflow ou dashboard (Datadog, nuvem, open source). A Fase 3 já tem Prometheus/Grafana,
mas lá o alvo era uma API viva; aqui o pipeline é **batch** (roda, termina e morre).

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| MLflow local | um `pip install`, guarda métricas, parâmetros e o HTML do Evidently juntos por execução, UI pronta | menos "operacional" que um Grafana |
| Prometheus + Grafana (Fase 3) | dashboard bonito, alertas | job batch exige Pushgateway, mais peças móveis |

## Decisão
MLflow local primeiro. Prometheus/Grafana vira `IMP-002`.

## Consequências
Cada execução do pipeline é um *run* do MLflow, ligado ao `run_id` dos logs estruturados.
