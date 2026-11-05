# REPASSE · decisões tomadas em modo prazo

> **Para que serve:** por causa do prazo, as decisões foram tomadas e seguidas sem parar para discutir. Aqui fica o
> que foi decidido, em linguagem simples, para revisarmos tudo juntos antes do vídeo (Jira PMF4-38).
> Aprendizado adiado, não aprendizado pulado. Cada entrada traz: o que, por quê, a alternativa descartada, o que
> esperávamos, o que aconteceu e uma pergunta para o Akira responder.

## DRIFT-001 · Lotes com drift (04/11/2026)

### 1. História do data drift: inflação + aperto de crédito (decisão do Akira)
- **O que:** as faturas (`BILL_AMT1` a `BILL_AMT6`) sobem com o mesmo fator nas seis, e o limite de crédito (`LIMIT_BAL`) cai. O `default` não muda.
- **Por quê:** é uma mudança nominal (preços) e de política do banco (limites), não de comportamento. O cliente continua pagando como antes, então manter o y faz sentido. Usar o mesmo fator nas seis faturas preserva a correlação entre elas.
- **Descartado:** deslocar `PAY_*` (meses de atraso) mantendo o y. Dar atraso a quem pagou em dia e manter `default = 0` muda a relação entre X e y: seria concept drift disfarçado de data drift.
- **Esperávamos:** as entradas mudam, o contrato aprova e o modelo sente pouco, porque a ordem dos clientes, que é o que ele precisa acertar, quase não muda.
- **Aconteceu:** contrato aprovado (exit 0). A AUC (medida de quão bem o modelo ordena os clientes, de 0,5 a 1,0) foi de 0,7149 para 0,7144: nenhuma queda real. A correlação entre as faturas continuou em 0,9491.
- **Pergunta para o Akira:** se o modelo não piorou, esse data drift é um problema? O que você diria a um gestor que pergunta "por que o alarme tocou, se está tudo certo?"

### 2. Tamanho: faturas × 1,25 e limite × 0,75 na intensidade 1 (decisão do Akira)
- **O que:** intensidade é um número de 0 a 1. Em 0, nada muda; em 1, vale o fator cheio; no meio, interpolação linear (em 0,5, o limite é × 0,875). Faturas negativas (crédito a favor do cliente) também são multiplicadas.
- **Por quê:** o spike mostrou que o limite × 0,75 dá PSI (medida de mudança de distribuição) de cerca de 0,27, uma mudança relevante e bem visível. O parâmetro deixa o OBS-002 gerar "semanas" com drift crescente sem reescrever código.
- **Descartado:** um lote só, com fatores fixos no código, que obrigaria a mexer no código a cada "semana".
- **Esperávamos:** `LIMIT_BAL` com PSI de ~0,27 (mudança relevante) e faturas em "estável", entre 0,01 e 0,10.
- **Aconteceu:** `LIMIT_BAL` 0,2715. Faturas entre 0,025 e 0,046, mesmo com 25% de aumento. O teste KS (outra medida de mudança) detectou as seis com folga, com p-valor abaixo de 1e-27. Efeito colateral: clientes com fatura acima do limite foram de 643 (7,1%) para 3.265 (36,3%).
- **Pergunta para o Akira:** por que uma alta de 25% nas faturas passa despercebida pelo PSI e não pelo KS? E 36% dos clientes acima do limite ainda é uma história crível?

### 3. Concept drift: dobrar a taxa de default do quartil alto de fatura (decisão do Akira)
- **O que:** nenhuma entrada muda. Entre os 25% de clientes com maior `BILL_AMT1`, alguns que não deram default passam a ter `default = 1`, até a taxa do grupo dobrar.
- **Por quê:** concept drift é "mesmo cliente, outro resultado". É o caso em que olhar só as entradas não mostra nada, e queremos provar exatamente isso.
- **Descartado:** trocar rótulos ao acaso em toda a base, que não conta uma história econômica e não dá para explicar na análise causal.
- **Esperávamos:** ~450 rótulos trocados, nenhuma entrada diferente e AUC entre 0,66 e 0,69, fora do intervalo normal da Produção-base (0,701 a 0,728).
- **Aconteceu:** 459 rótulos trocados (conta: N = 2.250, D = 459; taxa de 20,4% para 40,8%; fração de 459 / 1.791 = 25,63%). As 23 features ficaram idênticas, e a AUC caiu para 0,6647. Taxa geral de default: 22,12% para 27,22%.
- **Pergunta para o Akira:** o modelo dá peso negativo a `BILL_AMT1` (fatura alta reduz o risco previsto). Isso ajuda a explicar a queda? O que aconteceria com a AUC se o subgrupo fosse o de fatura mais baixa?

### 4. Sorteio feito uma vez só para todas as intensidades (decisão do Claude)
- **O que:** a seed (número que fixa o sorteio) define uma lista embaralhada de candidatos; cada intensidade troca os primeiros da lista.
- **Por quê:** quem muda em 0,3 continua mudando em 0,6, e o número trocado é exato. Assim, no OBS-002, a diferença entre "semanas" é drift, não sorte.
- **Descartado:** sortear linha a linha com uma probabilidade, que só acerta o número em média e não permitiria testar "exatamente N rótulos".
- **Esperávamos:** mesmo hash a cada geração e rótulos acumulando com a intensidade.
- **Aconteceu:** mesmo hash nos 2 lotes; o teste confirma o acúmulo entre 0,3 e 0,6.
- **Pergunta para o Akira:** o data drift não usa sorteio nenhum. Então, o que a seed registrada no manifesto dele garante?

### 5. Quartil de fatura calculado na própria Produção-base (decisão do Claude)
- **O que:** o corte do "quartil mais alto" (67.290,75) vem da Produção-base, não da Referência.
- **Por quê:** o cenário descreve o que acontece naquele lote, e assim o subgrupo tem 25% dele (2.250 de 9.000).
- **Descartado:** corte da Referência, que seria parecido, mas não garantiria esse tamanho de subgrupo.
- **Esperávamos:** cerca de 2.250 clientes.
- **Aconteceu:** 2.250.
- **Pergunta para o Akira:** num monitoramento de verdade, com lotes semanais, de onde você tiraria esse corte, e por quê?

### 6. PSI e AUC medidos com script temporário (decisão do Claude, a partir da sua decisão 5)
- **O que:** `detect.py` ficou para o DRIFT-002, mas medi PSI, KS e AUC com um script fora do repositório, para comparar com as previsões.
- **Por quê:** sem medir, não dava para saber se o lote de concept drift cumpre "PSI baixo e queda de AUC". "Rodou" não é "funcionou".
- **Descartado:** só gerar os lotes e deixar a prova para o DRIFT-002, o que poderia revelar um lote errado só depois.
- **Esperávamos e aconteceu:** ver as entradas 1 a 3.
- **Pergunta para o Akira:** o que o DRIFT-002 precisa acrescentar para esses números virarem evidência para o avaliador?

### 7. Como declarar as colunas no Evidently (proposta para o DRIFT-002)
- **O que:** declarar sempre um `DataDefinition`, a descrição do tipo de cada coluna: `SEX`, `EDUCATION` e `MARRIAGE` categóricas; `PAY_*` e as demais, numéricas.
- **Por quê:** testado em 03/11. Sem a declaração, o Evidently trata `PAY_0` como numérica e `PAY_2` como categórica. `method="ks"` dá erro com colunas categóricas, então a rodada de KS usa `num_method="ks", cat_method="psi"`. A documentação não fala de colunas ordinais (com ordem, como meses de atraso), então esta é uma escolha nossa.
- **Descartado:** `PAY_*` como categóricas, que perderiam o KS e a noção de que mais atraso é pior.
- **Esperávamos e aconteceu:** as 23 colunas rodaram, e essa configuração foi a usada na medição do DRIFT-001.
- **Pergunta para o Akira:** `PAY_*` usa -2 e -1 como rótulos, não como quantidade. O que isso limita na leitura do KS?

## Mapa do código

### O caminho de um lote, do download até o portão

Hoje os scripts rodam à mão, nesta ordem: nenhum orquestrador os encadeia ainda.

1. `scripts/prepare_data.py` baixa os dados (`data/download.py`), resume (`data/eda.py`) e separa Referência e Produção-base (`data/split.py`).
2. `scripts/train_baseline.py` treina o modelo na Referência (`model/train.py`) e mede o AUC na Produção-base (`model/predict.py`): é a régua para saber depois se o modelo piorou.
3. `scripts/make_corrupted_batch.py` (`contracts/corrupt.py`) ou `scripts/make_drift_batch.py` (`drift/scenarios.py`) criam um lote a partir da Produção-base.
4. `scripts/run_validation.py` aplica o contrato (`contracts/validate.py` e `contracts/schema.py`), registra o resultado (`monitoring/events.py`) e devolve o exit code: 0 deixa o lote seguir, 1 o bloqueia.

O `make_drift_batch.py` também confere o contrato antes de gravar, porque lote reprovado nem chega ao disco. Depois do portão, o caminho ainda termina: pontuar o lote aprovado e medir o drift é o DRIFT-002.

### Cada arquivo em uma frase

**Config**
- `src/credit_risk_observability/__init__.py`: marca a pasta como pacote Python e guarda o `main()` de exemplo, sem papel no pipeline.
- `config.py`: guarda num lugar só os caminhos, a seed e os nomes de colunas que todo o projeto usa.

**Data**
- `data/__init__.py`: marca a pasta de dados como parte do pacote.
- `data/download.py`: baixa os 30.000 clientes do UCI, dá às colunas os nomes oficiais e guarda a cópia local.
- `data/eda.py`: resume os dados no relatório que embasou as regras do contrato e a escolha de métricas.
- `data/split.py`: separa Referência e Produção-base sem cliente em comum e registra como isso foi feito.

**Model**
- `model/__init__.py`: marca a pasta do modelo como parte do pacote.
- `model/train.py`: monta o baseline (o modelo simples que serve de régua) e calcula as métricas de qualidade.
- `model/predict.py`: carrega um modelo salvo e calcula a probabilidade de default de cada cliente.

**Contracts**
- `contracts/__init__.py`: marca a pasta do contrato como parte do pacote.
- `contracts/schema.py`: declara o que é um lote válido: colunas, tipos e valores permitidos.
- `contracts/validate.py`: aplica o contrato a um lote e devolve se passou e quais regras falharam.
- `contracts/corrupt.py`: estraga um lote de propósito, com defeitos contados, para provar que o contrato bloqueia.

**Monitoring**
- `monitoring/__init__.py`: marca a pasta de monitoramento como parte do pacote.
- `monitoring/events.py`: grava cada evento do pipeline como uma linha JSON em `logs/pipeline.jsonl`, com o `run_id` da execução.

**Drift**
- `drift/__init__.py`: marca a pasta de drift como parte do pacote.
- `drift/scenarios.py`: altera a Produção-base de forma controlada, gerando data drift (as entradas mudam) ou concept drift (o resultado muda).

**Scripts** (os pontos de entrada, que você roda no terminal)
- `scripts/prepare_data.py`: passo 1, produz a Referência e a Produção-base a partir do download.
- `scripts/train_baseline.py`: passo 2, treina o modelo e salva modelo e métricas.
- `scripts/make_corrupted_batch.py`: passo 3, gera o lote corrompido e o gabarito de falhas esperadas.
- `scripts/make_drift_batch.py`: passo 3, gera um lote com drift, confere no contrato e grava o manifesto (o registro de como o lote foi gerado).
- `scripts/run_validation.py`: passo 4, o portão: decide pelo exit code se o lote segue ou para.

**Tests** (rodam com `uv run pytest`, sem depender de `data/` nem de rede)
- `tests/test_smoke.py`: confere se as pastas, o pacote e as dependências estão de pé.
- `tests/test_split.py`: prova que o split separa os clientes sem vazamento e é repetível.
- `tests/test_model.py`: prova que o modelo aprende, é medido certo e não usa `SEX` nem `MARRIAGE`.
- `tests/test_contract.py`: prova que cada regra do contrato bloqueia o defeito que promete bloquear.
- `tests/test_ingestion_gate.py`: prova que o portão devolve o exit code certo e encontra exatamente os defeitos injetados.
- `tests/test_drift.py`: prova que os lotes com drift mudam exatamente o que foi decidido.

## Padrão júnior/pleno no código existente (04/11/2026)

### 8. O que contou como "só comentário" (decisão do Claude)
- **O que:** 28 arquivos receberam docstrings e comentários, e 4 scripts ganharam 5 `print` com um resumo em português: `prepare_data.py`, `train_baseline.py`, `make_corrupted_batch.py` e `run_validation.py` (aprovado e bloqueado). Log JSON, mensagens de erro e textos do `argparse` ficaram iguais.
- **Por quê:** o playbook pede que scripts imprimam um resumo para humano, e você incluiu mensagens impressas no escopo. Os `print` só leem valores que já existiam.
- **Descartado:** reescrever as mensagens de `logger.info`, porque log é registro de máquina e não fazia parte do pedido.
- **Esperávamos:** mesma lógica, mesmos artefatos e os mesmos 59 testes.
- **Aconteceu:** árvore de sintaxe igual nos 28 arquivos, sem contar docstrings e `print`; 16 artefatos e 8 eventos de log iguais aos da main.
- **Pergunta para o Akira:** o `print` vai para o stdout, e o log do `logging` vai para o stderr. Por que isso importa se alguém usar `run_validation.py > saida.txt`?

### 9. Testes com docstring de uma linha (proposta do Claude, aprovada pelo Akira e agora regra do playbook)
- **O que:** funções de teste e fixtures dizem em uma linha o que provam; "Recebe / Faz / Devolve" ficou para o código e para os ajudantes dos testes.
- **Por quê:** em teste, o que interessa é o comportamento provado. As três partes repetiriam `base` e `None` 62 vezes.
- **Descartado:** aplicar as três partes em todas as 101 funções, como o playbook dizia ao pé da letra na época.
- **Esperávamos e aconteceu:** 39 funções com as três partes e 62 com uma linha.
- **Pergunta para o Akira:** se um teste precisa de mais de uma linha para explicar o que prova, o que isso sugere sobre o próprio teste?

### 10. O que apareceu ao ler o código, sem corrigir porque lógica estava fora do escopo (decisão do Claude)
- **O que:** um comentário antigo meu estava errado e foi corrigido: dizia que, sem o `isnan`, NaN passaria em `validate_intensity`. Passaria não: `not 0 <= nan <= 1` já dá `True`, então o `isnan` é redundante. Ficaram sem mexer:
  - `load_model` ainda não tem quem chame (vai ser usado no DRIFT-002);
  - `prepare_data.py` grava os arquivos antes de checar o vazamento, então uma falha deixaria os arquivos no disco (débito no Jira PMF4-39, prioridade baixa);
  - `inject_defects` não confere se os defeitos cabem no lote: com um lote pequeno demais, os grupos ficariam menores que o gabarito (débito no Jira PMF4-39, prioridade baixa).
- **Por quê:** o pedido era não mudar comportamento; misturar correção aqui estragaria a prova.
- **Descartado:** corrigir tudo no mesmo PR.
- **Pergunta para o Akira:** um comentário errado passou pela revisão do DRIFT-001, e os testes não o pegaram. Que tipo de erro nenhum teste automático consegue encontrar?

## DRIFT-002 · Relatório de drift (04/11/2026)

### 11. Régua dos quatro quadrantes (decisão do Akira)
- **O que:** cada lote responde a duas perguntas: as features mudaram (PSI acima de 0,25 ou KS, um teste que devolve p-valor, abaixo de 0,05)? A performance caiu (AUC, a medida de ordenação dos clientes, abaixo de 0,701)? O cruzamento dá quatro diagnósticos.
- **Por quê:** o DRIFT-001 mostrou que o concept drift não aparece nas colunas. Um relatório só de features o chamaria de "tudo certo".
- **Descartado:** relatório só de features, ou um veredito de alerta já neste card (fica para o OBS-002).
- **Esperávamos:** controle "sem drift relevante", data drift "sem impacto" e concept drift "suspeita de concept drift", com 60% de confiança no controle.
- **Aconteceu:** os três como previsto. AUC de 0,7149, 0,7144 e 0,6647.
- **Pergunta para o Akira:** o quadrante diz "suspeita", e não "concept drift". O que você precisaria ver, além da queda de AUC, para trocar a suspeita por certeza?

### 12. A régua do KS dá alarme falso em 31% das divisões (achado do Claude, regra mantida)
- **O que:** "alguma feature com p-valor abaixo de 0,05" são 20 testes por lote. Refiz a divisão Referência/Produção 200 vezes, sem nenhum drift: 62 deram ao menos um alarme, com até 14 colunas de uma vez.
- **Por quê importa:** a nossa seed caiu nos outros 69%, com menor p-valor de 0,183. Em outra divisão, o controle sairia "data drift sem impacto", e o concept drift, "data drift com impacto": a história do vídeo mudaria por sorte.
- **Descartado:** ajustar a regra para o resultado ficar seguro. Você pediu para não ajustar, e o veredito é do OBS-002.
- **Esperávamos:** chance de 30% a 50%. **Aconteceu:** 31%.
- **Pergunta para o Akira:** se fossem 20 testes independentes, seriam 64%. Por que deu menos? E o que você mudaria na régua no OBS-002?

### 13. Limiares explícitos no Evidently, até no drift do conjunto (decisão do Claude)
- **O que:** PSI 0,25, KS 0,05 e `drift_share = 1/23` no relatório.
- **Por quê:** os padrões dele são PSI 0,1 e 50% das colunas. O HTML do lote de data drift dizia "Dataset Drift is NOT detected" logo abaixo do nosso "data drift", porque só 1 de 23 colunas (PSI) e 7 de 23 (KS) mudaram.
- **Descartado:** deixar o padrão e explicar a diferença no texto, o que faria o avaliador ler uma contradição.
- **Esperávamos e aconteceu:** "NOT detected" no controle e no concept drift; "detected" no data drift, conferido abrindo a página no navegador.
- **Pergunta para o Akira:** um limite de 50% das colunas faz sentido para quem? Em que tipo de sistema ele seria uma boa régua, e por que não no nosso?

### 14. Performance no resumo, e não nas métricas do Evidently (decisão do Claude)
- **O que:** AUC, recall e precisão vêm do `evaluate` do projeto e aparecem num resumo em português no topo do HTML.
- **Por quê:** na tabela do Evidently, a comparação seria com a Referência; a sua decisão compara com a Produção-base. Usar o `evaluate` também garante o mesmo cálculo do ML-001.
- **Descartado:** `ClassificationPreset` do Evidently. Daria gráficos prontos, mas contra o conjunto errado.
- **Esperávamos e aconteceu:** Produção-base com 0,7149, igual a `baseline_metrics.json`, conferido por teste.
- **Pergunta para o Akira:** o limite de 0,701 veio de um lote de 9.000 linhas. O que acontece com ele num lote semanal de 1.000 linhas, no OBS-002?

### 15. As 23 features entram na régua, e o lote reprovado não gera relatório (decisão do Claude)
- **O que:** `SEX` e `MARRIAGE` são medidas mesmo fora do modelo; categóricas só têm PSI, então são 23 colunas no PSI e 20 no KS. Lote reprovado no contrato dá exit 1 e nenhum relatório.
- **Por quê:** mudança no público atendido importa para o viés (GOV-003), mesmo sem entrar no modelo. E dado sujo não é drift.
- **Descartado:** medir só as 21 features do modelo; o KS com categóricas, que dá erro.
- **Esperávamos e aconteceu:** coberto por testes; os 3 lotes reais passam no contrato.
- **Pergunta para o Akira:** se `SEX` mudar muito e o modelo nem a usa, o diagnóstico "data drift sem impacto no modelo" conta a história inteira?

### 16. Telemetria e o que ela realmente garante (decisão do Akira, com ressalva do Claude)
- **O que:** `DO_NOT_TRACK=1` no `detect.py`, antes do import do Evidently.
- **Ressalva:** a sua decisão citava reprodutibilidade, mas telemetria não muda nenhum número. Na versão 0.7.23, o envio só é chamado pelos serviços de UI e coletor, não pelo `Report`. Vale como garantia de privacidade; não medi o tráfego de rede.
- **Esperávamos e aconteceu:** `event_logger.enabled()` dá falso, conferido por teste. Reproduzir o JSON dá números idênticos; o HTML muda em identificadores internos.
- **Pergunta para o Akira:** para a banca, como você provaria que nenhum dado saiu da máquina?

### 17. Erro de processo: relatórios contaminados por mutação (erro do Claude)
- **O que:** rodei a regeneração dos relatórios ao mesmo tempo que a mutação, que altera o código de propósito. Um relatório saiu com limite 0,65, em vez de 0,701.
- **Como foi pego:** a saída impressa do script mostrou o limite. Apaguei os relatórios, conferi o código e os hashes dos lotes (intactos), e gerei de novo sozinho.
- **Lição:** nada que grava evidência roda em paralelo com algo que altera o código.
- **Pergunta para o Akira:** esse erro seria pego se o script não imprimisse o limite usado? O que no JSON ajudaria a detectá-lo depois?

### 18. Lote com uma classe só e lotes pequenos (achados da revisão do Claude)
- **O que:** um lote só com `default = 0` dava AUC `nan` e diagnóstico "sem drift relevante", porque NaN nunca é "abaixo de 0,701". Agora ele é recusado com erro claro. Além disso, o limite de 0,701 vale para lotes de cerca de 9.000 linhas: amostras sem drift nenhum ficaram abaixo dele em 5 de 40 vezes com 1.000 linhas, e em 14 de 40 com 500.
- **Por quê:** a primeira é sucesso vazio, e foi corrigida. A segunda afeta o OBS-002, que vai gerar "semanas", e fica registrada, porque a regra é sua.
- **Descartado:** tratar NaN como "caiu", que chamaria de concept drift um lote que nem pôde ser medido.
- **Esperávamos:** lote recusado. **Aconteceu:** o teste falhou antes da correção (`AUC: nan`) e passou depois; os três relatórios reais não mudaram.
- **Pergunta para o Akira:** como o limite de queda deveria mudar conforme o tamanho do lote?

### 19. Política de HTML e destino dos achados (decisão do Akira)
- **O que:** os 3 relatórios do DRIFT-002 ficam versionados como evidência da Etapa 2 e não devem ser regerados em PRs futuros. Daqui em diante, relatórios de execuções do pipeline vão para uma pasta fora do git e, no OBS-002, para os artefatos do MLflow.
- **Por quê:** cada HTML tem 6,3 MB, quase todo de JavaScript repetido, e muda a cada geração mesmo com os mesmos números. Regerar os três soma cerca de 4,7 MB ao histórico do git.
- **Descartado:** regerar a cada execução, o que incharia o histórico sem acrescentar informação.
- **Pendente:** `scripts/run_drift_report.py` ainda grava em `reports/drift/` por padrão, então rodá-lo sobrescreve a evidência. O README avisa; a mudança de destino é do OBS-002.
- **Destino dos achados médios:** KS, limite de AUC por tamanho de lote e PSI do alvo estão no comentário do PMF4-20. O PSI fora da faixa fica para o repasse do PMF4-17: com fatura × 1,1 em dados sintéticos, os valores saem da faixa da Referência, caem em faixas vazias e o preenchimento de zeros do Evidently leva o PSI acima de 0,25.
- **Pergunta para o Akira:** se o PSI explode quando um valor sai da faixa da Referência, o que seu cálculo à mão no DRIFT-003 deveria fazer com esses valores?
