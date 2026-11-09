# ROADMAP · credit-risk-observability (Fase 4)

A ordem em que o projeto foi construído. Cada camada só começou quando a anterior funcionava, e não
na ordem em que os requisitos aparecem no enunciado. As datas são as dos merges na `main`; cards e
prazos ficam no [Jira PMF4](https://akiravkax.atlassian.net/issues?jql=project%20%3D%20PMF4%20ORDER%20BY%20key%20ASC).

## Fundação

- **STEP 0 · Ambiente e dataset** ✅ 21/10 ([SETUP-001](specs/SETUP-001.md), [ADR-001](decisions/ADR-001-dataset.md))
  Antes de qualquer código, escolher um dataset com mais de 5.000 linhas e atributos sensíveis reais.
- **STEP 1 · Referência e Produção separadas** ✅ 21/10 ([DATA-001](specs/DATA-001.md))
  O drift só se mede contra algo que o modelo viu: a separação precisa existir antes do modelo.
- **STEP 2 · Modelo baseline** ✅ 21/10 ([ML-001](specs/ML-001.md), [ADR-004](decisions/ADR-004-features-sensiveis.md))
  Um modelo simples e explicável é a régua: sem a AUC de controle, nenhuma queda tem significado.

## Etapa 1 · Contrato de dados

- **STEP 3 · Contrato em Pandera** ✅ 21/10 ([DQ-001](specs/DQ-001.md), [ADR-002](decisions/ADR-002-pandera.md))
  Primeiro definir o que é um lote válido; só depois faz sentido falar em lote com drift.
- **STEP 4 · Lote corrompido barrado** ✅ 21/10 ([DQ-002](specs/DQ-002.md))
  Defeitos injetados e contados: o contrato precisa achar exatamente eles.

## Etapa 2 · Drift

- **STEP 5 · Compatibilidade do Evidently** ✅ 03/11 ([SPIKE-001](specs/SPIKE-001-evidently.md))
  Testar a biblioteca antes de depender dela: o padrão sem método explícito não usava nem PSI nem KS.
- **STEP 6 · Lotes com drift conhecido** ✅ 04/11 ([DRIFT-001](specs/DRIFT-001.md))
  Simular a "resposta certa" antes de construir o detector, para poder conferi-lo.
- **STEP 7 · Relatório de drift** ✅ 04/11 ([DRIFT-002](specs/DRIFT-002.md))
  PSI e KS nas features, mais alvo, score e performance: só a performance vê o concept drift.
- **STEP 8 · PSI à mão** 🔄 em andamento ([DRIFT-003](specs/DRIFT-003.md))
  Calcular o PSI sem biblioteca para entender o que o Evidently faz por baixo. Card de aprendizado,
  fica para depois da entrega.

## Etapa 3 · Observabilidade

- **STEP 9 · Log estruturado** ✅ 08/11 ([OBS-001](specs/OBS-001.md))
  O rastro de cada execução vem antes do painel: o painel só mostra o que o log registrou.
- **STEP 10 · Semanas no MLflow e réguas calibradas** ✅ 08/11 ([OBS-002](specs/OBS-002.md), [ADR-003](decisions/ADR-003-mlflow.md))
  Calibrar as réguas em amostras sem drift antes de confiar nos alarmes.
- **STEP 11 · CI/CD** ✅ 08/11 ([IMP-001](specs/IMP-001.md))
  Automatizar o que já funcionava à mão: o CI barra o PR que afrouxa o contrato.
- **STEP 12 · Métricas de saúde documentadas** ✅ 08/11 ([OBS-003](specs/OBS-003.md))
  Cada número do painel com o que mede, por que importa e o limiar de alerta.

## Etapa 4 · Governança

- **STEP 13 · Inventário de dados pessoais** ✅ 08/11 ([GOV-001](specs/GOV-001.md), [ADR-005](decisions/ADR-005-minimizacao-failure-cases.md))
  Saber o que é dado pessoal antes de decidir onde ele pode aparecer.
- **STEP 14 · Viés por grupo** ✅ 08/11 ([GOV-003](specs/GOV-003.md), [ADR-006](decisions/ADR-006-vies-por-idade.md))
  Medir mesmo sem os atributos no modelo: tirar a coluna não tira o viés.
- **STEP 15 · Análise causal** ✅ 08/11 ([GOV-004](specs/GOV-004.md))
  Separar causa de correlação com um experimento de dose-resposta, antes de propor ação.
- **STEP 16 · Base legal e retenção** ✅ 08/11 ([GOV-002](specs/GOV-002.md))
  A retenção aplicada por código, e não só escrita.

## Entrega

- **STEP 17 · README final** ✅ 08/11 ([DOC-001](specs/DOC-001.md))
- **STEP 18 · Documentação no padrão da Fase 3** 🔄 09/11 (DOC-002)
  Model Card, ML Canvas, este roadmap, README reestruturado, Makefile, pre-commit e cobertura.
- **STEP 19 · Roteiro do vídeo STAR** 🔄 ([`docs/video/roteiro.md`](video/roteiro.md))
- **STEP 20 · Gravação e submissão** ⏳ até 16/11, com 17/11 de folga

## Depois da entrega

- Sessão de repasse das decisões do [`REPASSE.md`](REPASSE.md) (REPASSE-001).
- PSI à mão (DRIFT-003) e revisão do ADR-004.
- Retreino com `AGE` fora das features (ADR-006).
