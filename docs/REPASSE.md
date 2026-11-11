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

## OBS-001 · Log estruturado (08/11/2026)

### 20. Esquema fixo com 9 campos e `pipeline_step` (decisão do Claude)
- **O que:** todo evento tem `timestamp, run_id, etapa, evento, status, duracao_s, linhas_entrada, linhas_rejeitadas, detalhe`. São os 8 campos do card mais `evento`, o nome estável da ocorrência. Um context manager (`with pipeline_step(...)`) mede o tempo e grava ao sair, inclusive quando o script quebra.
- **Por quê:** se cada script inventa seus campos, o OBS-002 vira uma coleção de casos especiais. E o `with` garante que uma falha inesperada também deixa rastro, sem depender de o script lembrar de logar.
- **Descartado:** um `log_event` por script (o formato antigo), em que a duração e o status dependiam de cada autor.
- **Esperávamos e aconteceu:** lote corrompido sintético de 220 linhas deu `falha` com 130 linhas rejeitadas, que é exatamente a soma dos defeitos disjuntos (50 + 30 + 10 + 40).
- **Pergunta para o Akira:** `linhas_rejeitadas` conta linhas com ao menos uma falha. Se o lote é bloqueado inteiro, qual número importa mais para a operação: as 130 linhas ruins ou as 220 que não seguiram?

### 21. Erro inesperado grava só o tipo, nunca a mensagem (decisão do Claude)
- **O que:** uma exceção vira `motivo: "erro inesperado: ValueError"`. A mensagem completa aparece no console, não no arquivo.
- **Por quê:** mensagens de erro do pandas e do Pandera podem trazer valores de linha, e o arquivo de log é guardado. Teste prova que o texto da mensagem não chega ao log.
- **Pergunta para o Akira:** sem a mensagem no arquivo, como você investigaria uma falha de madrugada? O que um log de console com retenção curta resolveria?

### 22. Relatório de drift fora do git por padrão (pendência da decisão 19, resolvida)
- **O que:** `run_drift_report.py` grava em `outputs/drift/` (no `.gitignore`); `--reports-dir` muda o destino.
- **Limitação desta sessão:** o proxy da nuvem bloqueou o download do UCI, então a validação real foi com lotes sintéticos do mesmo `inject_defects`. Rode no seu ambiente o comando da spec com `production_base.parquet` e `batch_corrupted.parquet` para registrar os números reais.

## OBS-002 · Monitoramento semanal no MLflow (08/11/2026)

### 23. Réguas recalibradas para o lote de 2.000, sempre em amostras sem drift (decisão do Claude)
- **O que:** 400 amostras de 2.000 linhas da Produção-base: 200 para calibrar, 200 só para medir o alarme falso. Piso da AUC = percentil 2,5 (0,687); taxa de default entre os percentis 2,5 e 97,5 (20,6% a 23,6%); KS com Bonferroni (p < 0,0025) e D mínimo no percentil 95.
- **Por quê:** são as três direções do comentário do PMF4-20. Os lotes com drift nunca entram na calibração: ajustar a régua neles seria ajustar a régua à resposta.
- **Esperávamos e aconteceu:** a régua antiga do KS (p < 0,05) alarmou em 24,5% das amostras sem drift; a nova, em 1,5%. AUC: 3,5%. Taxa de default: 7,0%, acima dos 5% nominais, mas dentro do ruído de 200 amostras (erro padrão perto de 1,5 ponto).
- **Surpresa:** o D mínimo saiu 0,0. Com 2.000 linhas, em mais de 95% das amostras nenhuma feature passa no Bonferroni, então ele sozinho já basta. O D mínimo fica no código, para lotes maiores.
- **Pergunta para o Akira:** a taxa de default alarmou em 7% das semanas sem drift. Você aceitaria isso, ou alargaria o intervalo para 99%? O que se perde ao alargar?

### 24. Quatro semanas disjuntas com drift crescente, mais uma corrompida (decisão do Claude)
- **O que:** a Produção-base embaralhada vira 4 lotes de 2.000 sem cliente repetido. Intensidades 0; 0,33; 0,67 e 1, aplicando primeiro o concept drift (rótulos) e depois o data drift (entradas). Os 1.000 que sobram viram a semana corrompida, com os defeitos do DQ-002.
- **Por quê:** lotes disjuntos imitam semanas reais (clientes diferentes); juntar os dois drifts mostra qual régua acorda primeiro.
- **Previsão do Claude antes de rodar:** semana 2 com KS em `LIMIT_BAL`, semana 3 talvez com default, semana 4 com tudo. **Aconteceu:** a semana 3 já alarmou AUC (0,685) e default (27%), com PSI em 0,18. O concept drift aparece antes do data drift.
- **Pergunta para o Akira:** se só existisse o `drift_alert` (PSI), quantas semanas o modelo ficaria degradado antes de alguém saber?

### 25. MLflow com sqlite local, telemetria desligada, 3.18.0 (decisão do Claude)
- **O que:** `mlflow.db` e `mlartifacts/` locais e fora do git; `MLFLOW_DISABLE_TELEMETRY` antes do import, como no Evidently (decisão 16). Versão 3.18.0 porque a 3.17.2 exige `pyarrow<26` e o projeto fixa 26.0.0; só o `certifi` mudou no lock.
- **Descartado:** o armazenamento em pasta `mlruns/`, que o MLflow 3 já trata como legado.
- **Pergunta para o Akira:** se o `mlflow.db` some, o que se perde de fato? O que dá para reconstruir rodando os scripts de novo?

### 26. Métrica ausente não vira zero; a semana barrada não tem AUC (decisão do Claude)
- **O que:** `log_pipeline_run` pula valores None. A semana 5 tem só 3 métricas (latência, linhas de entrada e rejeitadas) e a tag `status=falha`.
- **Por quê:** AUC 0 no gráfico pareceria um modelo péssimo, quando na verdade o modelo nem rodou.

### 27. Privacidade e reprodutibilidade (achados desta sessão)
- **`failure_cases.csv` no MLflow:** o card pede esse artefato, e ele traz valores de linha (idade 15, IDs repetidos). Fica só em `mlartifacts/`, local e fora do git; minimizar o arquivo é o ADR-005, no GOV-001.
- **Reprodutibilidade:** nesta sessão os dados foram baixados de novo do UCI e os lotes saíram com os mesmos hashes da evidência do DRIFT-002. O arquivo do modelo muda nos bytes (Python 3.12.3 aqui, 3.12.10 no seu), mas a AUC repete 0,7149.
- **Armadilha achada:** `run_validation.py` e `make_drift_batch.py` ainda gravam resumo e manifesto em `reports/` e sobrescrevem a evidência quando rodados de novo. Restaurei com `git restore`. O pipeline semanal já grava em `outputs/`; mudar o padrão dos dois fica como candidato a `IMP-*`.

## IMP-001 · CI/CD no GitHub Actions (08/11/2026)

### 28. Dois workflows: CI em todo PR e merge, CD de monitoramento em todo merge (decisão do Claude, pedido do Akira)
- **O que:** `ci.yml` com dois jobs (qualidade: ruff e pytest; contrato: dados reais e `check_evidence.py`). `pipeline.yml` roda o pipeline semanal e publica os resultados como artefatos por 30 dias.
- **Por quê:** o CI protege a `main` antes do merge; o CD prova, a cada merge, que o pipeline inteiro ainda roda do zero com os dados reais, e entrega o painel sem ninguém rodar nada na mão.
- **Descartado:** rodar o pipeline completo em todo PR (lento, e o PR não precisa do MLflow para ser revisado); publicar os artefatos no repositório (incharia o git, decisão 19).
- **Pergunta para o Akira:** o CD hoje "entrega" artefatos. Numa fintech de verdade, o que mais um merge na `main` deveria disparar?

### 29. O portão compara as falhas regra a regra, não só o exit code (achado do Claude)
- **O que:** `check_evidence.py` exige que a Produção-base passe, que o lote corrompido seja barrado com exatamente as falhas esperadas e que os lotes regerados batam com os hashes da evidência.
- **Previsão:** afrouxar a regra de idade (18 para 10) deixaria o portão vermelho. **Aconteceu:** ficou, mas só por causa da comparação regra a regra. O lote corrompido continuou barrado pelas outras 4 regras (exit 1), então um portão que olhasse só o exit code teria aprovado o PR.
- **Pergunta para o Akira:** que outra mudança no contrato passaria despercebida por um teste que só olha "passou ou não passou"?

### 30. Limites calibrados conferidos no CD e artefato sem `failure_cases.csv` (decisão do Claude)
- **O que:** o CD recalibra e roda `git diff --exit-code` no `alert_thresholds.json`; rodando de novo aqui, os limites saíram idênticos. O upload exclui o `failure_cases.csv`.
- **Por quê:** régua que muda sem decisão é régua que ninguém revisou. E artefato do Actions fica acessível a quem lê o repositório: valores de linha não vão para lá (ADR-005).

## OBS-003 · Métricas de saúde no README (08/11/2026)

### 31. Tabela ligada às três perguntas do monitoramento, mais um guia de decisão (rascunho do Claude)
- **O que:** cada métrica do MLflow numa linha com o que mede, por que importa, limiar e onde ver; prints da semana 1 (saudável) e da semana 4 (alerta); guia em 3 casos para "retreinar ou não".
- **Por quê:** a pergunta do card ("se você saísse de férias, alguém decidiria só com a tabela?") pede uma regra de ação, não só definições. O guia separa falha de dado (corrigir a origem), data drift sem impacto (observar) e queda de performance (análise causal e retreino).
- **Descartado:** limiar para a latência. Com 5 semanas não há histórico para calibrar; inventar um número seria uma régua sem base. Fica como referência.
- **Pergunta para o Akira:** no caso 2 (data drift sem impacto), por quanto tempo você esperaria antes de agir? O que mudaria a sua resposta?

## GOV-001 · Inventário de PII e ADR-005 (08/11/2026)

### 32. ADR-005 implementado: relatório versionado só com regra e posição (decisão do Akira, código do Claude)
- **O que:** `ValidationResult.minimized_failures` descarta o valor barrado. O CSV versionado tem `regra` e `posicao_linha`; o detalhe vai para `outputs/validation/`. O pipeline semanal manda ao MLflow só a versão minimizada.
- **Esperávamos e aconteceu:** o teste que varre `reports/validation/` falhou antes da regeneração (achou os IDs do CSV antigo) e passou depois. As contagens do DQ-002 continuam iguais (160 falhas, 130 linhas).
- **Pergunta para o Akira:** a posição da linha ainda deixa reidentificar o cliente por quem tem o arquivo do lote. Isso é problema? Quem tem o lote já tem os dados de qualquer jeito?

### 33. `ID` descartado das saídas, não pseudonimizado (decisão do Claude)
- **Por quê:** IDs sequenciais de 1 a 30.000 tornam um hash sem segredo reversível por tentativa. Nenhuma saída precisa do ID, então não gravá-lo é mais simples e mais seguro que protegê-lo.
- **Descartado:** hash com sal fixo no código (o sal vazaria junto com o repositório).
- **Em produção:** HMAC-SHA256 na ingestão, com a chave fora do código.

### 34. Citações da LGPD não conferidas no texto oficial (limitação desta sessão)
- **O que aconteceu:** liberei `www.planalto.gov.br` na rede do ambiente, mas o servidor encerra a conexão vinda da nuvem. O README parafraseia e cita só número de artigo; a lista de conferência está na spec do GOV-001.
- **Pergunta para o Akira:** por que um plano de conformidade nunca deve citar artigo de memória? O que muda se o artigo tiver sido alterado por lei posterior?

## GOV-003 · Viés por grupo (08/11/2026)

### 35. O viés está na idade, não no sexo (achado da auditoria)
- **Previsão do Claude:** diferença pequena por sexo e viés contra os mais jovens. **Aconteceu:** sexo passa na regra dos 4/5 (0,920), mas idade reprova (0,663), e contra os **mais velhos**: 50 ou mais aprovados em 44,8%, de 30 a 39 em 67,6%.
- **Por que a previsão errou:** a taxa real de default sobe com a idade neste dataset (19,8% de 30 a 39, 26,0% com 50 ou mais), e o modelo amplia essa diferença.
- **Pergunta para o Akira:** se o grupo mais velho de fato atrasa mais, aprovar menos é injusto ou é só preciso? Qual das duas métricas (paridade ou oportunidade) responde melhor a isso?

### 36. Contrafactuais em vez de opinião: "tirar a coluna resolve?" (decisão do Claude)
- **O que:** o mesmo modelo, a mesma Referência, só mudando as colunas. Com `SEX` e `MARRIAGE`, a disparidade por sexo dobra (0,051 para 0,125). Sem `AGE`, a disparidade por idade cai (0,228 para 0,134) e a AUC perde 0,0012.
- **Por quê:** é um experimento de intervenção: muda uma coisa e mede o efeito. É o mesmo raciocínio da análise causal do GOV-004.
- **Pergunta para o Akira:** sem `AGE`, os menores de 29 passam a ser os menos aprovados. Que coluna está "fazendo o papel" da idade? Como você descobriria?

### 37. ADR-006 proposto, modelo não alterado (decisão do Claude, a confirmar)
- **O que:** recomendação de tirar `AGE` no próximo retreino, com revisão humana das negativas nos grupos com disparidade.
- **Por que não agora:** mudar o modelo invalidaria a evidência versionada de drift e de monitoramento, que é a nota das Etapas 2 e 3.

## GOV-004 · Análise causal (08/11/2026)

### 38. Dose-resposta em vez de correlação na série semanal (decisão do Claude)
- **O que:** cada drift aplicado sozinho, em 5 doses, no mesmo modelo e nos mesmos 9.000 clientes. Mede AUC, calote aprovado, bom cliente negado e exposição.
- **Por quê:** a pergunta do card ("PSI de `LIMIT_BAL` subiu e a AUC caiu na mesma semana: uma causou a outra?") só se responde com intervenção. Nas semanas os dois drifts vinham juntos, então a série sozinha confunde.
- **Previsão do Claude:** AUC parada com data drift e caindo com concept drift. **Aconteceu:** data drift de 0,7149 para 0,7144; concept drift em linha reta até 0,6647. Calotes aprovados +56%, exposição +65%.
- **Pergunta para o Akira:** em produção não dá para "aplicar drift" no mundo. Que experimento você faria com os dados que um banco de verdade tem?

### 39. Plano de ação com critério para encerrar (decisão do Claude)
- **O que:** cada gatilho do OBS-002 ligado a um diagnóstico, uma ação e um critério de saída. Rollback usa o `modelo_sha256` que cada run do MLflow já registra.
- **Por quê:** um plano sem critério de saída deixa o alerta aberto para sempre (fadiga de alerta).
- **Pergunta para o Akira:** quem decide o rollback numa fintech: o time de dados, o de risco ou os dois? O que o art. 20 da LGPD tem a ver com isso?

## GOV-002 · Base legal e retenção (08/11/2026)

### 40. Proteção do crédito e execução de contrato, não consentimento (decisão do Claude, a revisar)
- **Por quê:** consentimento na concessão de crédito não é livre (sem ele não há crédito) e a revogação deixaria o inadimplente apagar o próprio histórico.
- **Pergunta para o Akira (a do card):** se o cliente revoga o consentimento, a empresa precisa apagar o histórico de inadimplência? Como a resposta muda com a base legal?

### 41. Retenção aplicada por código, com simulação por padrão (decisão do Claude)
- **O que:** `scripts/apply_retention.py` lista o vencido; `--aplicar` apaga. Detalhe das falhas: 30 dias; saídas: 90; log: 180.
- **Por quê:** prazo só escrito não protege ninguém; e apagar é irreversível, então o padrão é olhar antes.

### 42. Explicabilidade conferida no modelo, não de memória (achado do Claude)
- **O que aconteceu:** o rascunho do art. 20 dizia que "uso do limite" pesava; não é nem feature. Os coeficientes reais mostram `PAY_0` e a escolaridade no topo.
- **Pergunta para o Akira:** se a escolaridade é um dos maiores pesos e tem risco discriminatório, o ADR-006 deveria tratar dela também?

## DOC-001 · README final (08/11/2026)

### 43. A Etapa 2 não tinha seção de resultados (achado do Claude)
- **O que:** o README tinha a nota "o que fica no git" sobre os relatórios de drift, mas nenhuma tabela dizendo o que foi alterado e o que o PSI e o KS acusaram, que é o centro da Etapa 2 (25% da nota).
- **Como foi pego:** reorganizando o README pela ordem das etapas do PDF, a Etapa 2 ficou sem corpo.
- **Pergunta para o Akira:** o PSI das faturas ficou entre 0,03 e 0,05 com uma alta de 25%. Por que o KS pegou e o PSI não? (Pista: o que o PSI faz com o valor dentro de cada faixa?)

### 44. Reprodutibilidade provada numa pasta limpa (validação do Claude)
- **O que:** clone limpo, sequência inteira do README: 2min46, todos os passos com o exit esperado. Painel, limites, viés e dose-resposta saíram idênticos; só `run_id`, datas e versão do Python mudaram.
- **Pendente:** o mesmo teste no PowerShell (lição da Fase 3), que este ambiente não tem.

## DOC-002 · Documentação no padrão da Fase 3 (09/11/2026)

### 45. ADR-006 decidido: `AGE` sai no próximo retreino (decisão do Akira)
- **O que:** opção B (tirar `AGE` das features) com D (revisão humana das negativas dos grupos com disparidade), aplicada no próximo retreino.
- **Por quê:** a razão da regra dos 4/5 por idade sobe de 0,663 para 0,800, a um custo de 0,0012 de AUC, menor que o ruído entre seeds.
- **Descartado:** tirar agora, que mudaria todos os números das Etapas 2 e 3 a 8 dias da entrega; e só documentar, difícil de defender pelo art. 20.
- **Esperávamos e aconteceu:** decisão registrada no ADR, no Model Card, no README e na fala final do roteiro.
- **Pergunta para o Akira:** sem `AGE`, os menores de 29 anos passam a ser os menos aprovados. Que métrica você acompanharia no primeiro mês depois do retreino para saber se trocou um viés por outro?

### 46. O que veio do projeto anterior, e o que não veio (decisão do Claude)
- **O que entrou:** Model Card, ML Canvas, Roadmap, README com badges, autor, requisitos, seções numeradas e índice de ADRs; Makefile, pre-commit e cobertura de testes.
- **O que ficou de fora:** Docker, API e notebooks. Este projeto é de sustentação em lote, sem API servindo predições, e a EDA já está em `reports/eda/`.
- **Por quê:** trazer só o que responde a uma pergunta deste projeto. Um Dockerfile sem serviço para empacotar seria peça de vitrine.
- **Pergunta para o Akira:** se a banca perguntar "como isso iria para produção?", qual peça da Fase 3 você citaria, e o que mudaria nela?

### 47. Ferramentas com as bordas medidas (decisão do Claude)
- **Makefile:** só chama comandos `uv run`, iguais aos do README. O `make` não existe no Windows desta máquina, então foi testado no WSL (Ubuntu 24.04), num clone separado. O teste real achou uma ordem implícita: `make evidence` precisa de `make drift` antes. A ajuda agora avisa, e `make pipeline` já roda na ordem certa.
- **pre-commit:** `reports/` e `models/` ficam de fora. O hook de fim de arquivo tentou mudar `models/baseline_metrics.json`, que o `train_baseline.py` regrava sem quebra de linha: hook e script brigariam a cada treino.
- **Cobertura:** 93% do pacote `src/`. Os scripts de `scripts/` são testados de ponta a ponta, mas ficam fora da conta; os mais baixos são o download e a EDA (46% a 50%), que dependem de rede. O CI mostra o número, sem limite mínimo.
- **Pergunta para o Akira:** um limite mínimo de cobertura no CI (por exemplo, 90%) protegeria o quê, e que tipo de teste ruim ele incentivaria?

## Finalização delegada (10/11/2026)

> Por decisão do Akira em 10/11, o Claude finaliza o que falta até a entrega, e o repasse fica para depois (PMF4-38, 21/11). As entradas abaixo estão marcadas: **feito pelo Claude por decisão do Akira; revisar no repasse.**

### 48. Roteiro v3 conferido número a número (feito pelo Claude por decisão do Akira; revisar no repasse)
- **O que:** cada número e referência do roteiro foi conferido contra README, Model Card, ML Canvas e os dados.
- **Corrigido:** alarme falso do KS era "vinte e quatro" e passou a "vinte e quatro e meio" (24,5%); o print `mlflow_run_alerta.png` é da semana 4, e não da 3; a resposta sobre o PSI culpava as faturas zeradas, mas elas são só 6,7%: a causa medida são as faixas largas (cerca de NT$ 70 mil), em que 83% a 89% dos clientes continuam na mesma faixa.
- **Ajuste preventivo:** "cento e vinte e cinco testes" virou "mais de cento e vinte", porque o número sobe com o DRIFT-003.
- **Descartado:** deixar 0,71 como 0,715 na fala: o arredondamento de 0,7149 para 0,71 está correto e é mais fácil de falar.
- **Pergunta para o Akira:** se as faixas do PSI fossem por quantis, e não de largura fixa, o que aconteceria com o PSI das faturas?
