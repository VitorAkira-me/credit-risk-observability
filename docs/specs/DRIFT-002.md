# DRIFT-002 · Relatório de drift com Evidently e diagnóstico por lote

- Etapa: 2
- Jira: [PMF4-18](https://akiravkax.atlassian.net/browse/PMF4-18)
- Status: concluída
- Data: 04/11/2026

## Objetivo
Para cada lote, gerar um relatório HTML e um resumo JSON que digam quais features mudaram, se o
resultado real e o score do modelo mudaram e se a performance caiu. Atende o requisito central da
Etapa 2: relatório com PSI e KS apontando as features alteradas.

## Conceito por trás (didático)
Monitorar só as entradas é como olhar só o termômetro do paciente: mostra febre, mas não mostra uma
doença sem febre. O DRIFT-001 provou isso: no lote de concept drift nenhuma entrada muda, e só a
taxa real de default e a AUC (medida de quão bem o modelo ordena os clientes, de 0,5 a 1,0) mostram
o problema. Por isso o relatório olha três coisas e as cruza em quatro quadrantes.

PSI e KS medem a mudança de uma coluna de jeitos diferentes. O PSI compara faixas de valores (quanto
maior, mais mudou). O KS compara as curvas acumuladas e devolve um p-valor (quanto menor, mais forte
a evidência de mudança). Com amostras grandes, o KS percebe mudanças pequenas que o PSI não vê.

## Decisões
Tomadas pelo Akira, por prazo:

1. Cada lote gera um relatório com três blocos: drift das features (PSI e KS, com método explícito);
   drift do alvo e da predição (taxa real de default e distribuição do score); performance (AUC,
   recall e precisão do lote).
2. As features são comparadas com a Referência (o que o modelo viu no treino). A performance é
   comparada com a Produção-base (AUC 0,715, IC 95% de 0,701 a 0,728), pela regra do ML-001.
3. Diagnóstico em quatro quadrantes:

   | Features | Performance | Diagnóstico |
   |---|---|---|
   | estáveis | estável | sem drift relevante |
   | mudaram | estável | data drift sem impacto no modelo |
   | estáveis | caiu | suspeita de concept drift |
   | mudaram | caiu | data drift com impacto |

   "Performance caiu": AUC do lote abaixo de 0,701. "Features mudaram": alguma feature com PSI > 0,25
   ou com KS de p-valor < 0,05. Qual régua dispara alerta fica para o OBS-002.
4. O ID do cliente fica fora do `DataDefinition` e de qualquer relatório (coerente com o ADR-005).
5. `load_model` e `predict_proba` pontuam os lotes. O score fica só em memória.
6. Telemetria do Evidently desligada (`DO_NOT_TRACK=1`).

Tomadas pelo Claude, com registro no REPASSE:

7. Limiares explícitos no Evidently (PSI 0,25 e KS 0,05). O padrão de PSI dele é 0,1: sem isso, o HTML
   marcaria drift onde o diagnóstico diz que não houve.
8. As 23 features entram na régua, inclusive `SEX` e `MARRIAGE`, que estão fora do modelo. Elas podem
   mudar o público atendido e são a base da análise de viés (GOV-003).
9. Categóricas (`SEX`, `EDUCATION`, `MARRIAGE`) só têm PSI. O KS exige números e o Evidently dá erro
   se for pedido nelas. Logo, são 23 colunas no PSI e 20 no KS.
10. O bloco de performance usa o `evaluate` do projeto e aparece num resumo em português no topo do
    HTML. Se viesse das métricas do Evidently, a tabela o compararia com a Referência, contrariando a
    decisão 2.
11. O script confere o contrato antes de medir: lote reprovado não gera relatório (exit 1). Lote sem o
    alvo, ou com uma classe só, é recusado com erro: a performance não poderia ser medida.
12. `drift_share = 1/23` no Evidently. O padrão dele só declara drift do conjunto com 50% das
    colunas: o HTML diria "Dataset Drift is NOT detected" abaixo do nosso diagnóstico de data drift.

## Escopo
- Dentro: `src/credit_risk_observability/drift/detect.py`, `scripts/run_drift_report.py`,
  `tests/test_drift_detect.py` e os relatórios dos três lotes em `reports/drift/`.
- Fora: decidir qual régua dispara alerta (OBS-002); PSI à mão (DRIFT-003); viés por grupo (GOV-003).

## Critérios de aceite
- [x] Um HTML e um JSON em `reports/drift/` para Produção-base, data drift e concept drift
- [x] As 4 combinações do diagnóstico testadas, inclusive nos limites exatos (0,25; 0,05; 0,701)
- [x] Estrutura do JSON testada
- [x] O ID não aparece no JSON nem no HTML (testado com um valor-sentinela)
- [x] Lote de controle sintético sai como "sem drift relevante"
- [x] Parquet do lote intacto: o score não é gravado
- [x] Previsão x resultado registrados; regra não ajustada para o resultado bater
- [x] Nenhum HTML acima de 10 MB (se passar: parar e levar as opções ao Akira)
- [x] Testes antigos e novos passando; ruff limpo; padrão júnior/pleno

## Como validar de verdade
```
uv run python scripts/run_drift_report.py data/production/production_base.parquet
uv run python scripts/run_drift_report.py data/production/batch_data_drift_i100.parquet
uv run python scripts/run_drift_report.py data/production/batch_concept_drift_i100.parquet
```
Conferir exit code, diagnóstico, tamanho e horário dos arquivos, e comparar o KS com `scipy.stats.ks_2samp`.

## Previsões (escritas em 04/11/2026, antes de rodar nos três lotes)
Previsão do Claude. Ela não é totalmente cega: o DRIFT-001 já tinha medido o PSI da base (todas as
colunas abaixo de 0,1), a AUC dos lotes e o KS de algumas colunas.

| Lote | Features mudaram | AUC | Diagnóstico previsto | Previsão do Akira |
|---|---|---|---|---|
| Produção-base (controle) | PSI: nenhuma. KS: nenhuma, com risco real de alarme falso | ~0,715 | sem drift relevante | a preencher no repasse |
| Data drift | PSI: `LIMIT_BAL` (~0,27). KS: `LIMIT_BAL` e as 6 faturas | ~0,714 | data drift sem impacto no modelo | a preencher no repasse |
| Concept drift | Iguais às do controle, por construção | ~0,665 | suspeita de concept drift | a preencher no repasse |

**Onde a previsão pode errar:** a régua aceita "alguma feature" entre 20 testes de KS. Se fossem
independentes, a chance de ao menos um p-valor abaixo de 0,05 sem drift nenhum seria de 64%
(1 - 0,95^20). Como as colunas são correlacionadas, chuto algo entre 30% e 50%; por isso, minha
confiança no controle é de uns 60%. E os dois diagnósticos estão ligados: o concept drift tem as
mesmas entradas do controle. Um alarme falso ali mudaria o controle para "data drift sem impacto" e
o concept drift para "data drift com impacto". A regra não será ajustada se isso acontecer.

## Riscos e perguntas em aberto
- A spec do ML-001 registra o IC como 0,702 a 0,728, e esta spec usa 0,701, como decidido. São dois
  bootstraps diferentes. A diferença só importaria para um lote com AUC entre 0,701 e 0,702.
- O Jira pede comparar a performance com a Referência. Vale a decisão 2 desta spec.
- Telemetria: desligá-la não muda nenhum número. No Evidently 0.7.23, `send_event` só é chamado pelos
  serviços de UI e coletor, e não pelo fluxo de `Report`. O `DO_NOT_TRACK=1` é uma garantia a mais;
  conferimos que `event_logger.enabled()` dá falso, mas não medimos o tráfego de rede.

## Resultado
Os três lotes saíram no quadrante previsto, sem nenhum ajuste de regra.

| Lote | Mudaram pelo PSI | Mudaram pelo KS | AUC | Previsto | Obtido |
|---|---|---|---|---|---|
| Produção-base (controle) | nenhuma | nenhuma | 0,7149 | sem drift relevante | sem drift relevante |
| Data drift | `LIMIT_BAL` (0,2715) | `LIMIT_BAL` e as 6 faturas | 0,7144 | data drift sem impacto no modelo | data drift sem impacto no modelo |
| Concept drift | nenhuma | nenhuma | 0,6647 | suspeita de concept drift | suspeita de concept drift |

**Alterei x detectei:**

| Lote | Alterei | PSI detectou | KS detectou | Falso positivo |
|---|---|---|---|---|
| Data drift | 7 colunas | 1 de 7 (faltaram as faturas) | 7 de 7 | 0 |
| Concept drift | 0 colunas; 459 rótulos | 0 colunas | 0 colunas | 0 |

**O que mais os números mostraram:**
- Alvo e score: no data drift, o score quase não se move (PSI 0,0053; KS p-valor 0,121), o que explica
  a AUC estável. No concept drift, o score fica igual ao do controle, e a taxa real sobe de 22,12% para
  27,22%. Esse aumento dá PSI de só 0,0141 no alvo: o PSI não enxergaria o problema nem no alvo.
- Performance no concept drift: recall de 0,6404 para 0,5453 e precisão de 0,3683 para 0,3859. A precisão
  sobe porque há mais defaults reais entre os apontados.
- Folga do controle: o menor p-valor do KS é 0,183 (`PAY_AMT3`), e o maior PSI é 0,0152 (`PAY_AMT2`).
- **Fragilidade da régua:** em 200 outras divisões aleatórias dos mesmos dados, o KS deu ao menos um alarme
  falso em 62 (31%), com até 14 colunas de uma vez. A previsão de 30% a 50% estava certa, e a nossa seed
  caiu nos outros 69%. Com outra divisão, o controle e o concept drift mudariam de quadrante. Regra
  mantida; a decisão é do OBS-002.

**Conferências:**
- KS do Evidently igual ao de `scipy.stats.ks_2samp` nas 20 colunas, nos 3 lotes (diferença 0).
- JSON idêntico ao gerar de novo, fora `run_id` e `created_at`. O HTML muda em identificadores internos.
- HTMLs: 6,30 MB cada (19 MB no total, 1,6 MB cada compactado). Só 0,13 MB são dados; o resto é o
  JavaScript do Evidently, repetido em cada arquivo.
- Página aberta no navegador (Edge): resumo no topo e gráficos do Evidently concordando com o diagnóstico.
- Mutação: 20 de 21 erros injetados percebidos. O restante é equivalente, porque o limiar padrão do KS
  já é 0,05.

**Limite da régua de AUC:** o 0,701 vale para lotes de cerca de 9.000 linhas. Amostras sem drift ficaram
abaixo dele em 5 de 40 vezes com 1.000 linhas e em 14 de 40 com 500. Fica para o OBS-002.

**Desvio de processo:** uma regeneração rodou junto com a mutação de código, e um relatório saiu com o
limite errado (0,65). Foi percebido pela saída do script: os relatórios foram apagados e refeitos sozinhos,
e os hashes confirmaram os lotes intactos.
