# Roteiro do vídeo STAR (VID-001)

> **Versão 2 (09/11/2026):** além dos resultados, mostra **como** o projeto foi feito, no padrão do
> projeto anterior (clinical-triage-mlops): specs, ADRs, Model Card, CI e qualidade do código.
> Rascunho do Claude para o Akira montar e falar com a própria voz. Todos os números vêm do
> repositório (README, `reports/` e `docs/`).
>
> **Tempo:** limite de 5min; meta de 4min40. Ritmo de referência: cerca de 140 palavras por minuto.
> A fala soma cerca de 520 palavras (3min44); o resto é tempo de tela. Cronometrar lendo em voz alta.

## Mapa do vídeo

| Bloco | Tempo | Tela | Mensagem |
|---|---|---|---|
| Situação | 0:00 a 0:35 | README, topo | o modelo degrada em silêncio |
| Tarefa | 0:35 a 1:00 | README, diagrama | quatro frentes de sustentação |
| Ação 1: dado sujo | 1:00 a 1:30 | terminal | o portão barra o lote corrompido |
| Ação 2: drift | 1:30 a 2:10 | relatório do Evidently | uma régua só não basta |
| Ação 3: monitoramento | 2:10 a 2:45 | painel e MLflow | o alerta chega uma semana antes |
| Ação 4: governança | 2:45 a 3:25 | viés, dose-resposta, Model Card | tirar a coluna não tira o viés |
| Como trabalhei | 3:25 a 4:05 | specs, ADRs, CI, Makefile | cada decisão é rastreável |
| Resultado | 4:05 a 4:40 | aba Actions | o que ficou e o que aprendi |

## Situação (0:00 a 0:35)
**Tela 1:** README aberto no topo: badges, autor e a tabela "Resultados em um minuto".

> Uma fintech tem um modelo de crédito em produção. Ele foi treinado num cenário econômico, mas a
> economia muda: a inflação sobe as faturas, os bancos cortam limites e um grupo de clientes passa a
> atrasar mais. O perigo é que o modelo degrada em silêncio: a API continua respondendo, ninguém vê
> erro, mas as decisões pioram. Usei trinta mil clientes reais de cartão de crédito de Taiwan, do UCI.

## Tarefa (0:35 a 1:00)
**Tela 2:** README, diagrama da arquitetura (seção 1).

> A minha tarefa foi construir a camada de sustentação desse modelo, em quatro frentes: barrar dado
> sujo antes do modelo; detectar e explicar a mudança nos dados; tornar a saúde do pipeline visível;
> e mostrar como os dados pessoais são protegidos e por que o modelo piorou.

## Ação 1: dado sujo (1:00 a 1:30)
**Tela 3:** terminal com `make contract` (ou `uv run python scripts/run_validation.py data/production/batch_corrupted.parquet`). Destacar "BLOQUEADO" e o exit 1.

> Primeiro, um contrato de dados em Pandera, com nove regras. Injetei um lote de mil e vinte linhas
> com defeitos que eu conhecia: idade 15, limite nulo, sexo inválido e IDs duplicados. O portão
> barra o lote com exit 1 e conta exatamente os defeitos que eu coloquei: nem mais, nem menos.

## Ação 2: drift (1:30 a 2:10)
**Tela 4:** `reports/drift/drift_report_batch_data_drift_i100.html` no navegador: o resumo em português no topo e a linha do `LIMIT_BAL`.

> Depois, simulei dois tipos de drift. No data drift, as faturas subiram 25% e o limite caiu 25%. O
> Evidently acusou o limite pelo PSI e pelo KS, mas as faturas o PSI deixou passar: só o KS pegou.
> No concept drift, as entradas não mudam; os clientes de fatura alta é que passam a dar mais calote.
> Nenhum teste de distribuição vê isso. Só a queda da AUC, de 0,715 para 0,665.

## Ação 3: monitoramento (2:10 a 2:45)
**Tela 5:** `reports/figures/painel_semanas.png`; depois `make mlflow`, run da semana 4.

> Para monitorar, simulei cinco semanas no MLflow, com drift crescente. Antes, calibrei as réguas
> em amostras sem drift: a régua ingênua do KS dava alarme falso em uma de cada quatro semanas;
> a calibrada, em 1,5%. Resultado: na semana três, a AUC e a taxa de calote já alarmam, e o PSI
> ainda não. Quem olhasse só o PSI perderia uma semana.

## Ação 4: governança (2:45 a 3:25)
**Tela 6:** README seção 7, tabela de viés e gráfico de dose-resposta; depois `docs/MODEL_CARD.md`, seção "Justiça".

> Na governança, tirei sexo e estado civil do modelo, mas medi o viés mesmo assim. Sexo passa na
> regra dos quatro quintos. Idade não: clientes com 50 anos ou mais são aprovados bem menos. Decidi
> tirar a idade no próximo retreino, com revisão humana até lá. E para separar causa de correlação,
> apliquei cada drift sozinho, em doses: só o concept drift derruba o modelo, e os calotes aprovados
> sobem 56%.

## Como trabalhei (3:25 a 4:05)
**Tela 7:** em sequência rápida, uns 8 segundos cada: `docs/specs/` (uma spec aberta, com a tabela de previsão), `docs/decisions/` (o índice de ADRs do README), `docs/MODEL_CARD.md`, `make help` no terminal e o Jira ou o `docs/KANBAN.md`.

> Cada card nasceu como uma spec, com critério de aceite e uma previsão escrita antes de rodar.
> Quando a previsão errava, o erro virava aprendizado registrado. Cada escolha com trade-off virou
> um ADR, como o do viés por idade. O modelo tem Model Card, com uso pretendido e limitações, e o
> negócio tem um ML Canvas. Tudo roda do zero com um comando: make pipeline.

## Resultado (4:05 a 4:40)
**Tela 8:** GitHub, aba Actions, com o CI e o pipeline de monitoramento verdes.

> O resultado: dado sujo não passa, o drift é detectado e explicado, e o alerta chega uma semana
> antes do que chegaria só com PSI. O CI roda 125 testes, mede a cobertura e barra o PR que afrouxa
> o contrato. Aprendi que uma régua só não basta, que correlação engana e que tirar a coluna sensível
> não tira o viés. O que eu faria diferente: decidir o tratamento da idade antes de treinar, e não
> depois de auditar.

## Lista de telas, na ordem de gravação
1. README, topo: badges, autor e "Resultados em um minuto".
2. README, seção 1: diagrama da arquitetura.
3. Terminal: `make contract` (Linux ou WSL) ou o comando `uv run` do lote corrompido (PowerShell).
4. `reports/drift/drift_report_batch_data_drift_i100.html` no navegador.
5. `reports/figures/painel_semanas.png`; depois o MLflow (`make mlflow`), run da semana 4.
6. README seção 7 (viés e `reports/figures/dose_resposta.png`); depois `docs/MODEL_CARD.md`.
7. `docs/specs/DRIFT-002.md` (tabela de previsões), índice de ADRs (README seção 8), `make help`, Jira.
8. GitHub, aba Actions (CI e Pipeline de monitoramento verdes).

## Cortes, se passar de 5 minutos
1. Tirar a frase do ML Canvas no bloco "Como trabalhei" (economiza uns 5 s).
2. Mostrar só o painel estático na Ação 3, sem abrir o MLflow (uns 10 s).
3. Juntar Situação e Tarefa numa tela só (uns 10 s).

## Checklist antes de gravar
- [x] ADR-006 decidido (09/11/2026): a fala do "faria diferente" usa essa decisão.
- [ ] Reescrever as falas com as suas palavras.
- [ ] Ler em voz alta com cronômetro e anotar o tempo real de cada bloco.
- [ ] Rodar `make pipeline` antes, para o MLflow ter as 5 semanas (e depois `make restore-evidence`).
- [ ] Deixar todas as telas abertas antes de começar (o MLflow sobe em cerca de 10 s).
- [ ] Depois de publicar, pôr o link do vídeo no topo do README (seção Autor).
