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
