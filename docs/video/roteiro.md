# Roteiro do vídeo STAR (VID-001)

> **Versão 3 (10/11/2026):** escrita para ser **lida em voz alta** do jeito que está, porque o
> repasse do projeto ficou para depois da entrega. Números por extenso na fala, frases curtas e
> uma ideia por frase. Usa o ML Canvas para abrir (o problema de negócio) e o Model Card para
> fechar a governança (o que o modelo é e quando não confiar nele).
>
> **Tempo:** limite de 5min, meta de 4min40. A fala soma cerca de 580 palavras (uns 4min10 a
> 140 palavras por minuto); o resto é troca de tela. Cronometre lendo em voz alta antes de gravar.
> Todos os números vêm do README, do Model Card e do ML Canvas.

## Mapa do vídeo

| Bloco | Tempo | Tela | Mensagem |
|---|---|---|---|
| Situação | 0:00 a 0:40 | ML Canvas | o modelo degrada em silêncio |
| Tarefa | 0:40 a 1:00 | README, diagrama | quatro frentes de sustentação |
| Ação 1: dado sujo | 1:00 a 1:25 | terminal | o portão barra o lote corrompido |
| Ação 2: drift | 1:25 a 2:05 | relatório do Evidently | uma régua só não basta |
| Ação 3: monitoramento | 2:05 a 2:40 | painel das semanas | o alerta chega uma semana antes |
| Ação 4: governança | 2:40 a 3:25 | Model Card e dose-resposta | tirar a coluna não tira o viés |
| Como trabalhei | 3:25 a 3:50 | specs, ADRs, aba Actions | cada decisão é rastreável |
| AWS (opcional) | 3:50 a 4:10 | CloudWatch e e-mail do alarme | roda em produção, em São Paulo |
| Resultado | 4:10 a 4:40 | ML Canvas, "Impacto medido" | o que ficou e o que eu levo |

Se o épico da AWS (PMF4-41) não ficar pronto até 13/11, pule o bloco AWS: o vídeo fecha em 4min20.

---

## Situação (0:00 a 0:40)
**Tela:** `docs/ML_CANVAS.md`, seção "Proposta de valor". Desça até "Coleta do resultado" na última frase.

> Olá, eu sou o Akira, e este é o meu Tech Challenge da Fase 4.
> Imagine uma fintech com um modelo de crédito em produção. Ele foi treinado num cenário
> econômico, mas a economia muda: as faturas sobem, os bancos cortam limites e alguns clientes
> passam a atrasar mais. O modelo não quebra. Ele continua respondendo, só que decide pior, e
> ninguém percebe.
> Este é o ML Canvas do projeto. Quem usa o score é o time de risco, que precisa saber quando
> confiar nele. E tem um detalhe importante: a gente só descobre se o cliente pagou um mês depois.

## Tarefa (0:40 a 1:00)
**Tela:** README, seção 1, diagrama da arquitetura.

> A minha tarefa foi construir a camada que sustenta esse modelo, em quatro frentes: barrar dado
> sujo antes do modelo, detectar a mudança nos dados, deixar a saúde do pipeline visível e
> documentar privacidade, viés e causa. Usei trinta mil clientes reais de cartão de crédito, do UCI.

## Ação 1: dado sujo (1:00 a 1:25)
**Tela:** terminal com `make contract` (ou, no PowerShell,
`uv run python scripts/run_validation.py data/production/batch_corrupted.parquet`).
Destaque o resumo "bloqueado" e o exit 1.

> Primeiro, um contrato de dados com nove regras. Montei um lote de mil e vinte linhas com defeitos
> que eu conhecia: idade quinze, limite vazio, IDs repetidos. O portão barra o lote, sai com erro
> e conta exatamente os defeitos que eu coloquei. Nem mais, nem menos.

## Ação 2: drift (1:25 a 2:05)
**Tela:** `reports/drift/drift_report_batch_data_drift_i100.html` no navegador: o resumo em
português no topo e a linha do `LIMIT_BAL`. Se der tempo, abra o de concept drift e mostre o
diagnóstico "suspeita de concept drift".

> Depois, simulei dois tipos de mudança. No data drift, as faturas sobem vinte e cinco por cento e
> o limite cai vinte e cinco. O Evidently pegou o limite pelos dois testes, o PSI e o KS. As
> faturas, só o KS viu.
> No concept drift é o contrário: nenhuma coluna muda, mas os clientes de fatura alta passam a dar
> mais calote. Nenhum teste de distribuição percebe. Só a queda da AUC, de zero vírgula setenta e
> um para zero vírgula sessenta e seis, denuncia.

## Ação 3: monitoramento (2:05 a 2:40)
**Tela:** `reports/figures/painel_semanas.png`. Se der tempo, o MLflow (`make mlflow`), run da
semana 4 (o print está em `reports/figures/mlflow_run_alerta.png`).

> Para monitorar, rodei cinco semanas no MLflow, com drift crescente. Antes, calibrei as réguas em
> amostras sem drift, porque testar vinte colunas ao mesmo tempo gera alarme falso. O alarme falso
> do KS caiu de vinte e quatro e meio para um e meio por cento. Resultado: na semana três, a AUC e a taxa
> de calote já disparam o alerta, uma semana antes do PSI.

## Ação 4: governança (2:40 a 3:25)
**Tela:** `docs/MODEL_CARD.md`: role por "Uso pretendido" e pare em "Justiça". Depois
`reports/figures/dose_resposta.png`.

> Na governança, este é o Model Card: o que o modelo é, o que ele não é e quando não confiar nele.
> Tirei sexo e estado civil do modelo, mas medi o viés mesmo assim. Sexo passa na regra dos quatro
> quintos. Idade não: quem tem cinquenta anos ou mais é aprovado bem menos. Decidi tirar a idade no
> próximo retreino, com revisão humana até lá.
> E para separar causa de correlação, apliquei cada drift sozinho, em doses. Só o concept drift
> derruba o modelo, e os calotes aprovados sobem cinquenta e seis por cento.

## Como trabalhei (3:25 a 3:50)
**Tela:** em sequência rápida, uns 6 segundos cada: uma spec aberta em `docs/specs/` (a tabela
de previsão), o índice de ADRs (README, seção 8) e a aba Actions do GitHub com CI e Pipeline verdes.

> Cada tarefa nasceu como uma especificação, com uma previsão escrita antes de rodar, e cada
> escolha difícil virou um registro de decisão. O CI roda mais de cento e vinte testes e barra
> qualquer mudança que afrouxe o contrato. E tudo roda do zero com um comando.

## AWS, opcional (3:50 a 4:10)
**Tela:** dashboard do CloudWatch e o e-mail do alarme aberto ao lado. Só grave se o épico
PMF4-41 estiver pronto.

> E o pipeline também roda na AWS, na região de São Paulo. Quando um lote novo chega, ele é
> validado e analisado sozinho, e se algo der errado, o alerta chega no meu e-mail.

## Resultado (4:10 a 4:40)
**Tela:** `docs/ML_CANVAS.md`, seção "Impacto medido" (a tabela dos calotes aprovados).

> O resultado: dado sujo não passa, o drift é detectado e explicado, e o alerta chega uma semana
> antes. O que eu levo daqui: uma régua só não basta, correlação engana, e tirar a coluna sensível
> não tira o viés. O que eu faria diferente: decidir sobre a idade antes de treinar, e não depois de
> auditar. Obrigado.

---

## Lista de telas, na ordem de gravação
1. `docs/ML_CANVAS.md` (Proposta de valor e Coleta do resultado).
2. README, seção 1 (diagrama).
3. Terminal com o lote corrompido barrado.
4. `reports/drift/drift_report_batch_data_drift_i100.html` (e o de concept drift, se der tempo).
5. `reports/figures/painel_semanas.png` (e o MLflow, se der tempo).
6. `docs/MODEL_CARD.md` (Uso pretendido e Justiça) e `reports/figures/dose_resposta.png`.
7. Uma spec, o índice de ADRs e a aba Actions.
8. AWS: dashboard do CloudWatch e e-mail do alarme (opcional).
9. `docs/ML_CANVAS.md` (Impacto medido).

## Cortes, se passar de 5 minutos
1. Pular o bloco AWS (20 s).
2. Mostrar só o painel estático na Ação 3, sem abrir o MLflow (10 s).
3. Tirar a frase "E tudo roda do zero com um comando" (4 s).

## Dicas para ler em voz alta
- Fale "AUC" como "a-u-cê" e explique uma vez, se quiser: "a nota de quanto o modelo ordena bem
  quem paga e quem não paga".
- PSI e KS: diga as letras. Se sentir que precisa explicar: "dois testes que medem se os dados
  mudaram".
- Pause dois segundos em cada troca de tela; isso conta no tempo e ajuda quem assiste.

## Se perguntarem (respostas curtas para ter na ponta da língua)
- **Por que regressão logística e não um modelo mais forte?** O objetivo era sustentar um modelo,
  não maximizar a AUC. A logística é explicável peso a peso, o que ajuda no direito de revisão da LGPD.
- **Por que o PSI não viu as faturas?** O PSI compara fatias de largura fixa. Como existem faturas
  enormes, cada fatia fica larga, de uns setenta mil, e mais de oitenta por cento dos clientes
  continuam na mesma fatia mesmo com a alta de vinte e cinco por cento. O KS mede a maior distância
  entre as curvas e pega deslocamentos consistentes.
- **Por que calibrar as réguas?** Com vinte colunas testadas ao mesmo tempo, alguma acusa por puro
  acaso. Calibrar em amostras sem drift garante poucos alarmes falsos.
- **Como você sabe que é causa e não correlação?** Apliquei cada drift sozinho, em doses
  crescentes. Só o concept drift move a AUC, e de forma proporcional à dose.
- **O score é uma probabilidade?** Não. Ele ordena bem, mas está descalibrado: prevê calote para
  trinta e oito por cento dos clientes quando a taxa real é vinte e dois. Está nas limitações do
  Model Card.

## Checklist antes de gravar
- [ ] Ler em voz alta com cronômetro e anotar o tempo real de cada bloco.
- [ ] Rodar `make pipeline` antes, para o MLflow ter as 5 semanas (depois, `make restore-evidence`).
- [ ] Deixar todas as telas abertas antes de começar (o MLflow sobe em cerca de 10 s).
- [ ] Fechar notificações e abas com dados pessoais.
- [ ] Depois de publicar, pôr o link do vídeo no topo do README (seção Autor).
