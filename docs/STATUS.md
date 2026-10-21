# STATUS · atualizado em 21/10/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.

## Onde estamos
- SETUP-001, DATA-001 e ML-001 concluídos (cronograma da semana 1 em dia).
- Dados: Referência 21.000 / Produção-base 9.000, default 22,12% nos dois, 0 IDs em comum.
- Baseline LogisticRegression: AUC ~0,715 real (validação 0,732 com seed favorável,
  Produção-base 0,715, IC 95% 0,702 a 0,728). Métricas em `models/baseline_metrics.json`.
- ADR-004: `SEX` e `MARRIAGE` fora das features (custo 0,0018 de AUC), mantidos para auditar viés.
- Achados para o DQ-001: `EDUCATION` 0/5/6, `MARRIAGE` 0, `PAY_*` -2/0 fora do dicionário,
  1.930 faturas negativas (legítimas), 35 linhas idênticas ignorando ID.
- 14 testes passando; ruff limpo. README real com "como rodar".

## PRs abertos (merge pelo Akira, em ordem)
1. #1 SETUP-001  2. #2 DATA-001  3. #3 ML-001 (cada um parte do anterior)

## Pendências manuais (Akira)
- Merge dos PRs acima (o modo automático bloqueia merge sem revisão humana).
- Proteger a `main` (comando no chat de 21/10 ou Settings > Branches).

## Próximo passo
DQ-001: contrato Pandera com ≥3 regras rígidas, usando os achados da EDA.
Modo: Claude pilota por causa do prazo; manter explicações curtas.

## Prazo
Entrega 17/11/2026. Semana 2 de 5 (20 a 26/10: DQ-001 e DQ-002). Em dia.
