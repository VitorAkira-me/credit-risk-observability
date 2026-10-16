---
name: deteccao-de-drift
description: Use na Etapa 2 (DRIFT-001 e DRIFT-002) para simular data drift e concept drift no dataset de produção, gerar predições e produzir o relatório Evidently com PSI e KS.
---

# Simulação e detecção de drift (Etapa 2, 25% da nota)

## Dois tipos de drift, duas simulações
- **Data drift (muda X):** altere a distribuição de **pelo menos 2 features importantes**.
  Exemplos coerentes com "inflação e novos perfis" no dataset UCI Taiwan:
  - `LIMIT_BAL` cai ~20 a 30% (bancos mais conservadores);
  - `BILL_AMT*` sobe (faturas mais caras com inflação);
  - `PAY_0` e `PAY_2` deslocados para mais atraso;
  - `AGE` com mais clientes jovens (novo público digital).
- **Concept drift (muda a relação X para y):** mantenha X parecido, mas mude o rótulo para um
  subgrupo (ex.: clientes com fatura alta passam a dar default com mais frequência que antes).
  Isso mostra que o modelo erra mais **mesmo sem** a entrada parecer diferente.

Regra: toda alteração precisa ser **reprodutível** (`seed` fixa) e **documentada** na spec com o
tamanho do deslocamento. Assim sabemos a "resposta certa" e conferimos se o detector achou.

## Separação obrigatória
- `data/reference/` = o que o modelo viu no treino.
- `data/production/` = lotes "do futuro" com drift. Nunca treinar com eles.

## Relatório com Evidently
- **Fixe a versão** no `pyproject.toml` e confira a doc dessa versão antes de codar: a API mudou
  bastante a partir da 0.7 (nas novas: `from evidently import Report`,
  `from evidently.presets import DataDriftPreset`, `snapshot = report.run(current_data=..., reference_data=...)`,
  `snapshot.save_html(...)`). Não confie em exemplos antigos da internet sem checar.
- Configure o método estatístico explicitamente para atender o requisito: **PSI** e **KS**
  (parâmetros de método numérico do preset/métrica). Rodar duas vezes, uma com cada, é aceitável e didático.
- Salve em `reports/drift/drift_report_<lote>.html` e também um JSON/dict com o resumo por feature
  (será consumido pela Etapa 3).
- Gere predições do modelo na produção e compare métricas (AUC, recall da classe default) entre
  referência e produção. É a prova de que o drift **dói**.

## Validação de verdade
As features que você alterou precisam aparecer como drift; as que não alterou, idealmente não.
Monte uma tabelinha "alterei / detectou" na spec. Falso positivo e falso negativo são achados, não falhas.

## Pergunta para deixar no ar
Com 30 mil linhas o KS acusa drift em diferenças minúsculas. O PSI não depende do tamanho da
amostra do mesmo jeito. Qual dos dois você colocaria para disparar um alerta às 3h da manhã?
