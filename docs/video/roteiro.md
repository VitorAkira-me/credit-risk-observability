# Roteiro do vídeo STAR (VID-001)

> **Rascunho do Claude, para o Akira reescrever com a própria voz** depois do REPASSE-001.
> Todos os números vêm do repositório (README e `reports/`). Ritmo de referência: cerca de
> 140 palavras por minuto falando com calma. Meta: 4min30, com folga para o limite de 5min.
> Contagem do rascunho: cerca de 460 palavras, 3min16 de fala; o resto é tempo de tela
> (terminal rodando, MLflow abrindo, transições). Cronometrar lendo em voz alta é obrigatório.

## Situação (0:00 a 0:40)
**Tela 1:** README aberto no topo (tabela "Resultados em um minuto").

> Uma fintech tem um modelo de crédito em produção. Ele foi treinado num cenário econômico, mas a
> economia muda: a inflação sobe as faturas, os bancos cortam limites e um grupo de clientes passa a
> atrasar mais. O perigo é que o modelo degrada em silêncio. A API continua respondendo, ninguém vê
> erro, mas as decisões pioram. Usei 30 mil clientes reais de cartão de crédito de Taiwan, do UCI.

## Tarefa (0:40 a 1:10)
**Tela 2:** diagrama da arquitetura no README.

> A minha tarefa foi construir a camada de sustentação desse modelo, em quatro frentes: barrar dado
> sujo antes que ele chegue ao modelo; detectar e explicar a mudança nos dados; tornar a saúde do
> pipeline visível; e documentar como os dados pessoais são protegidos e por que o modelo piorou.

## Ação (1:10 a 3:40)
**Tela 3 (0:25):** terminal rodando `run_validation.py` no lote corrompido; destacar o exit 1.

> Primeiro, o contrato de dados, em Pandera, com nove regras. Injetei mil e vinte linhas com
> defeitos conhecidos: idade 15, limite nulo, sexo inválido e IDs duplicados. O portão barra o
> lote, com exit 1, e conta exatamente os defeitos que eu coloquei.

**Tela 4 (0:35):** relatório HTML do data drift (`LIMIT_BAL` em destaque) e a tabela da Etapa 2.

> Depois, simulei dois tipos de drift. No data drift, as faturas subiram 25% e o limite caiu 25%. O
> Evidently acusou o limite pelo PSI e pelo KS. Mas as faturas o PSI deixou passar: só o KS pegou.
> Por isso uso os dois. No concept drift, as entradas não mudam, mas os clientes de fatura alta
> passam a dar mais calote. Nenhum teste de distribuição vê isso; só a queda da AUC, de 0,715 para 0,665.

**Tela 5 (0:40):** painel das semanas (`reports/figures/painel_semanas.png`) e a UI do MLflow (semana 4).

> Para monitorar, simulei cinco semanas no MLflow, com drift crescente. Antes, recalibrei as réguas:
> a régua antiga do KS dava alarme falso em 24,5% das semanas sem drift, uma em cada quatro; agora,
> em 1,5%. O resultado: na semana três, a AUC e a taxa de calote já alarmam, e o PSI ainda não.
> Quem olhasse só o PSI perderia uma semana. A quinta semana, com dado sujo, aparece como falha.

**Tela 6 (0:30):** tabela de viés e gráfico de dose-resposta no README.

> Por fim, governança. Tirei sexo e estado civil do modelo, mas medi o viés mesmo assim. Sexo passa
> na regra dos quatro quintos. Idade não: clientes com 50 anos ou mais são aprovados bem menos.
> E para separar causa de correlação, apliquei cada drift sozinho, em doses: só o concept drift
> derruba o modelo, e com ele os calotes aprovados sobem 56%.

## Resultado (3:40 a 4:30)
**Tela 7:** aba Actions do GitHub com o CI e o CD verdes.

> O resultado: dado sujo não passa, o drift é detectado e explicado, e o alerta chega uma semana
> antes do que chegaria só com PSI. Tudo roda do zero em menos de três minutos, e o CI barra
> o PR que afrouxa o contrato, conferindo as falhas regra a regra. Aprendi que uma régua só não basta, que correlação engana,
> e que tirar a coluna sensível não tira o viés. O que eu faria diferente: decidir o tratamento da
> idade antes de treinar, e não depois de auditar.

## Lista de telas, na ordem de gravação
1. README, topo (tabela de resultados).
2. README, diagrama da arquitetura.
3. Terminal: `uv run python scripts/run_validation.py data/production/batch_corrupted.parquet`.
4. `reports/drift/drift_report_batch_data_drift_i100.html` no navegador; depois a tabela da Etapa 2.
5. `reports/figures/painel_semanas.png`; depois `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db`, run da semana 4.
6. README: tabela de viés e `reports/figures/dose_resposta.png`.
7. GitHub, aba Actions (CI e Pipeline de monitoramento verdes).

## Checklist antes de gravar
- [ ] Reescrever com as suas palavras (depois do REPASSE-001).
- [ ] Ler em voz alta com cronômetro; anotar o tempo real de cada bloco.
- [ ] Deixar todas as telas abertas antes de começar (MLflow sobe em cerca de 10 s).
- [ ] Decidir o ADR-006 antes: a fala do "faria diferente" depende dele.
