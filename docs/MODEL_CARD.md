# Model Card · Baseline de risco de crédito (regressão logística)

Estrutura inspirada em [Mitchell et al., 2019](https://arxiv.org/abs/1810.03993). O foco deste
projeto não é o melhor modelo, e sim **sustentar** um modelo em produção. Por isso, as seções mais
importantes aqui são *Limitações*, *Justiça* e *Monitoramento*: elas dizem quando não confiar
no score e o que fazer quando ele piorar.

Todos os números vêm de arquivos versionados: [`models/baseline_metrics.json`](../models/baseline_metrics.json),
[`reports/fairness/fairness_report.json`](../reports/fairness/fairness_report.json) e
[`reports/monitoring/alert_thresholds.json`](../reports/monitoring/alert_thresholds.json).

---

## Detalhes do modelo

- **Algoritmo:** `LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)`,
  dentro de um `sklearn.Pipeline` com `OneHotEncoder` para `EDUCATION` e `StandardScaler` para as
  colunas numéricas. Treino em [`scripts/train_baseline.py`](../scripts/train_baseline.py)
  ([ML-001](specs/ML-001.md)).
- **Por que um modelo simples:** a regressão logística é explicável peso a peso, o que sustenta o
  direito de revisão da LGPD (art. 20). O objetivo do projeto é observar a degradação, não
  maximizar a AUC.
- **Features (21):** `LIMIT_BAL`, `EDUCATION`, `AGE`, `PAY_0` e `PAY_2` a `PAY_6`, `BILL_AMT1` a
  `BILL_AMT6` e `PAY_AMT1` a `PAY_AMT6`. Fora do modelo: `SEX` e `MARRIAGE`
  ([ADR-004](decisions/ADR-004-features-sensiveis.md)).
- **Saída:** um score entre 0 e 1. Com limiar de 0,5, score abaixo do limiar significa "aprovar".
- **Versões:** Python 3.12, scikit-learn 1.9.1, seed 42. O hash do arquivo do modelo
  (`modelo_sha256`) vai para cada run do MLflow, para saber qual versão tomou cada decisão.

## Uso pretendido

**Para que serve:** ordenar pedidos de cartão de crédito por risco de calote no mês seguinte, como
**apoio** à decisão, com revisão humana nos casos limítrofes e nos grupos com disparidade.

**O que este modelo não é:**
- não é uma decisão final automática: o plano de ação ([GOV-004](specs/GOV-004.md)) prevê
  revisão humana, e o cliente tem direito de pedir revisão (art. 20 da LGPD);
- não é uma probabilidade calibrada: com `class_weight="balanced"`, o modelo prevê default para
  38,5% dos clientes da Produção-base, quando a taxa real é 22,1% (ver *Limitações*);
- não vale fora do contexto de origem: clientes de cartão de crédito de Taiwan, em 2005.

## Dados de treino

- **Fonte:** [Default of Credit Card Clients](https://archive.ics.uci.edu/dataset/350) (UCI),
  30.000 clientes, alvo `default` com 22,12% de inadimplência
  ([ADR-001](decisions/ADR-001-dataset.md)).
- **Separação:** Referência com 21.000 clientes (treino e validação) e Produção com 9.000, que
  nunca entra no treino. Split estratificado, seed 42, 0 clientes em comum ([DATA-001](specs/DATA-001.md)).
- **Treino e validação:** 16.800 e 4.200 clientes, a partir da Referência.
- **Dados pessoais:** todo o dataset é dado pessoal. O inventário completo está no
  [README](../README.md) (GOV-001).

## Avaliação

| Conjunto | Clientes | AUC | KS de crédito | Recall de default | Precisão de default | Brier |
|---|---|---|---|---|---|---|
| Treino | 16.800 | 0,728 | 0,383 | 0,650 | 0,380 | 0,206 |
| Validação | 4.200 | 0,732 | 0,384 | 0,657 | 0,384 | 0,205 |
| Produção-base (controle) | 9.000 | **0,715** | 0,365 | 0,640 | 0,368 | 0,209 |

Como ler: a **AUC** mede o quanto o modelo ordena bem quem paga e quem não paga (0,5 é sorteio e
1,0 é perfeito). O **KS de crédito** mede a separação entre bons e maus pagadores. O **recall** diz
quantos calotes o modelo pega, e a **precisão**, quantos dos apontados de fato deram calote. O
**Brier** é o erro médio das probabilidades (menor é melhor).

**Faixa normal:** trocar só a seed do split leva a AUC de validação de 0,714 a 0,732. Na
Produção-base, o intervalo de confiança de 95% vai de 0,701 a 0,728. Uma variação dentro dessa faixa
não é piora do modelo.

## Justiça (viés por grupo)

A auditoria do [GOV-003](specs/GOV-003.md) mede a taxa de aprovação por grupo. A **regra dos 4/5**
sinaliza impacto desigual quando o grupo menos aprovado tem menos de 80% da aprovação do mais aprovado.

| Recorte (Produção-base) | Diferença de aprovação | Razão da regra dos 4/5 | Resultado |
|---|---|---|---|
| Sexo (fora do modelo) | 0,051 | 0,920 | passa |
| Idade (no modelo) | 0,228 | **0,663** | **reprova** |

Clientes com 50 anos ou mais são aprovados em 44,8% dos casos, contra 67,6% na faixa de 30 a 39.
Parte disso vem da diferença real de default, mas o modelo amplia essa diferença.

**Decisão ([ADR-006](decisions/ADR-006-vies-por-idade.md), 09/11/2026):** tirar `AGE` no próximo
retreino (a razão sobe de 0,663 para 0,7996, ainda logo abaixo do 0,8 da regra, a um custo de 0,0012 de AUC) e encaminhar à revisão humana as negativas
dos grupos com disparidade até lá. Atenção para o efeito colateral medido: sem `AGE`, os menores de
29 anos passam a ser os menos aprovados, porque o limite de crédito funciona como proxy da idade.

## Limitações

- **Score não calibrado.** O peso balanceado faz o modelo prever default demais (38,5% previstos
  contra 22,1% reais). O score serve para **ordenar** clientes, não para estimar a probabilidade
  real de calote. Usá-lo como probabilidade (por exemplo, para provisão) exigiria calibração.
- **Dados antigos e de outro mercado.** Taiwan, 2005, valores em NT$. O comportamento de crédito de
  hoje, e de outro país, pode ser diferente.
- **Códigos sem documentação.** `EDUCATION` tem códigos 0, 5 e 6, e `PAY_*` tem -2 e 0, que o UCI
  não explica. O contrato aceita esses códigos porque eles existem nos dados de treino.
- **Drift simulado.** O data drift e o concept drift da Etapa 2 foram injetados de forma controlada,
  para saber a resposta certa. Em produção, a mudança real é mais lenta e misturada.
- **Proxies.** Tirar uma coluna não tira o viés: as features adivinham o sexo com AUC 0,577, e o
  limite de crédito carrega parte da idade.
- **Rótulo atrasado.** O `default` só se conhece um mês depois. Em produção, a AUC e a taxa de
  default (as réguas que detectam concept drift) chegam com esse atraso.

## Monitoramento

| Régua | Dispara quando | Alarme falso medido |
|---|---|---|
| PSI | PSI acima de 0,25 em alguma feature | não calibrado |
| KS | p-valor abaixo de 0,0025 (0,05 / 20); o efeito mínimo calibrado saiu 0, então vale só o Bonferroni | 1,5% |
| AUC | abaixo de 0,687 (lotes de 2.000 clientes) | 3,5% |
| Taxa de default | fora de 20,6% a 23,6% | 7,0% |

O **PSI** mede quanto a distribuição de uma coluna mudou. O **KS** é um teste estatístico que
compara duas distribuições. Nenhum dos dois vê o concept drift, que só aparece na AUC e na taxa de
default. Nas 5 semanas simuladas, a AUC e a taxa de default alarmaram na semana 3, uma semana antes
do PSI ([OBS-002](specs/OBS-002.md)).

## Manutenção

- **Quando retreinar:** quando a AUC ou a taxa de default saem da faixa e a análise causal confirma
  concept drift. Só PSI ou KS alterados, com AUC normal, não justificam retreino
  ([OBS-003](specs/OBS-003.md)).
- **O que o próximo retreino precisa cumprir:** AUC maior que a do modelo atual na janela recente,
  contrato de dados aprovado, `AGE` fora das features (ADR-006) e a regra dos 4/5 medida de novo. Atenção: só tirar `AGE` leva a razão a 0,7996, ainda logo abaixo de 0,8; a revisão humana continua até a regra passar.
- **Rollback:** se o modelo novo for pior, voltar à versão anterior, identificada pelo
  `modelo_sha256` registrado em cada run do MLflow.
