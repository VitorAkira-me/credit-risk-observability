# STATUS · atualizado em 21/10/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.

## Onde estamos
- **Etapa 1 concluída** (25% da nota): DQ-001 contrato Pandera com 9 regras rígidas;
  DQ-002 portão `run_validation.py` bloqueia lote corrompido (exit 1) com contagens exatas.
- Antes: SETUP-001, DATA-001, ML-001 (baseline AUC real ~0,715), ADR-004.
- Lote corrompido: 1.020 linhas, AGE 50, ID duplicado 40, LIMIT_BAL nulo 30 (+30 tipo), SEX 10.
- Log estruturado JSON em `logs/pipeline.jsonl` (`monitoring/events.py`): base para o OBS-001.
- 31 testes passando; ruff limpo; exit codes conferidos no Git Bash e no PowerShell.

## PRs abertos (merge pelo Akira, em ordem)
1. #4 DQ-001  2. #5 DQ-002 (parte do #4)

## Próximo passo
DRIFT-001: lote de Produção com data drift em ≥ 2 features (LIMIT_BAL, BILL_AMT, PAY_0, AGE)
e concept drift, deslocamentos documentados com seed. Comparar contra a Produção-base, não a
validação (ruído de seed, ver ML-001). O lote com drift **precisa passar no contrato**.
Modo: Claude pilota por causa do prazo.

## Prazo
Entrega 17/11/2026. Semana 2 de 5; Etapa 1 fechada com ~5 dias de folga. Etapa 2 é da semana 3.
