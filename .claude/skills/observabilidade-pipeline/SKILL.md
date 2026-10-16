---
name: observabilidade-pipeline
description: Use na Etapa 3 (OBS-001 e OBS-002) para centralizar logs e métricas do pipeline e dos testes de drift, com MLflow ou Prometheus/Grafana, e documentar as métricas de saúde.
---

# Observabilidade de pipelines e modelos (Etapa 3, 20% da nota)

## Três perguntas que o painel precisa responder
1. **O pipeline rodou?** status por etapa (ingestão, validação, predição, drift), sucesso ou falha.
2. **Rodou bem?** duração por etapa (latência), volume de linhas recebidas, aprovadas e rejeitadas.
3. **O modelo ainda é confiável?** nº de features com drift, PSI máximo, alertas disparados,
   métricas de performance quando houver rótulo.

## Passo 1: logs estruturados (OBS-001)
- Logging em JSON (uma linha por evento) em `logs/pipeline.jsonl`, com campos fixos:
  `timestamp, run_id, etapa, status, duracao_s, linhas_entrada, linhas_rejeitadas, detalhe`.
- Um `run_id` por execução liga todos os eventos daquela rodada.
- Por que JSON e não texto? Porque log estruturado é consultável (filtrar, agregar, contar).

## Passo 2: rastreamento (OBS-002), opção recomendada MLflow
- `mlflow.start_run()` por execução do pipeline; `log_param` (lote, versão do modelo, método de drift),
  `log_metric` (latência, volumes, nº features com drift, PSI por feature, AUC), `log_artifact`
  (HTML do Evidently, failure_cases do contrato).
- Tag de alerta: `drift_alert=true` quando PSI > 0,25 em alguma feature (limiar documentado).
- Simular várias "semanas" (lotes com drift crescente) gera uma série temporal bonita na UI do MLflow,
  ótima para o vídeo.
- Backend local (`mlruns/` ou sqlite) basta. Nada de nuvem.

## Alternativa: Prometheus/Grafana da Fase 3 (IMP-002)
Pushgateway para jobs batch (Prometheus faz pull e o job morre antes do scrape: por isso o push).
Só depois do MLflow funcionando.

## Documentar no README
Tabela "métrica, o que mede, por que importa, limiar de alerta".

## Pergunta para deixar no ar
Qual a diferença entre um **log**, uma **métrica** e um **trace**? Qual deles você usaria para
descobrir *por que* a validação de terça falhou, e qual para saber *quantas vezes* falhou no mês?
