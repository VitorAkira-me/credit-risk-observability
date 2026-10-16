# GLOSSÁRIO · conceitos da Fase 4

> Caderno de fixação. Cada conceito novo entra aqui em linguagem simples, com uma analogia
> e uma pergunta para pensar. Preencha conforme os cards forem sendo feitos.

## Data Contract (contrato de dados)
**O que é:** um acordo escrito em código sobre o formato que os dados *precisam* ter para entrar no
sistema (tipos, faixas, nulos, unicidade). Se o lote quebra o contrato, ele é barrado na porta.
**Analogia:** o segurança da balada com a lista. Não importa se você é legal, sem nome na lista não entra.
**Pergunta para pensar:** um cliente com idade 17 é "dado sujo" ou "dado válido de um caso proibido"?
A resposta muda onde a regra deve morar (contrato de dados ou regra de negócio).

## Data Drift (desvio de dados)
**O que é:** a distribuição das *entradas* X muda ao longo do tempo. Ex.: a renda média dos novos
clientes cai por causa da inflação.
**Pergunta para pensar:** se a renda de todo mundo sobe 10% por causa da inflação, o cliente ficou
mais rico? O modelo acha que sim.

## Concept Drift (desvio de conceito)
**O que é:** a *relação* entre X e o alvo y muda. O mesmo perfil que antes pagava em dia agora atrasa.
**Pergunta para pensar:** dá para detectar concept drift sem ter o rótulo verdadeiro (pagou ou não)?
Quanto tempo leva para esse rótulo chegar numa operação de crédito real?

## PSI (Population Stability Index)
**O que é:** mede o quanto uma distribuição mudou comparando a fatia de dados em cada faixa (bin).
Fórmula: soma de `(atual% - referência%) * ln(atual% / referência%)`.
**Régua de mercado:** < 0,1 estável; 0,1 a 0,25 atenção; > 0,25 mudança relevante.
**Curiosidade:** nasceu no setor de crédito, décadas antes de existir "MLOps".

## Teste KS (Kolmogorov-Smirnov)
**O que é:** compara duas distribuições numéricas pela **maior distância** entre suas curvas
acumuladas. Gera um p-valor: se for pequeno (ex.: < 0,05), as amostras provavelmente vêm de distribuições diferentes.
**Pergunta para pensar:** com 30 mil linhas, quase qualquer diferença minúscula vira "significativa".
Isso é um bug ou uma característica do teste?

## Degradação silenciosa
**O que é:** o modelo continua respondendo rápido e sem erro (a API está "verde"), mas as decisões
pioram. Monitorar infraestrutura não basta, é preciso monitorar dados e predições.

## LGPD: base legal
**O que é:** todo tratamento de dado pessoal precisa de uma justificativa prevista no art. 7º.
Em crédito, as candidatas típicas são execução de contrato e **proteção do crédito** (inciso X).
**Pergunta para pensar:** por que "consentimento" costuma ser uma base fraca para concessão de crédito?
