# Machine Learning Canvas · Sustentação do modelo de crédito

Framework de [Louis Dorard](https://www.louisdorard.com/machine-learning-canvas), adaptado para
**entendimento do negócio**. Os blocos de engenharia (features, construção do modelo) já estão nas
[specs](specs/) e no [Model Card](MODEL_CARD.md), então aqui ficam só os blocos que explicam
**por que** este projeto existe e como o score é usado.

Contexto: Tech Challenge Fase 4, Pós Tech em Machine Learning Engineering (FIAP).

---

## Proposta de valor

Uma fintech já tem um modelo de crédito em produção. O risco não é o modelo errar no primeiro dia,
e sim **degradar em silêncio**: a economia muda, a API continua respondendo e ninguém vê erro, mas
as decisões pioram. Este projeto entrega a camada que impede isso: barra dado sujo antes do modelo,
detecta e explica a mudança, avisa quando o modelo deixa de ser confiável e documenta como os dados
pessoais são protegidos.

**Para quem:** o time de risco de crédito, que decide quando confiar no score, quando revisar à mão
e quando retreinar.

## Tarefa de predição

Classificação binária: dado o histórico de um cliente de cartão (limite, idade, escolaridade,
6 meses de atraso, faturas e pagamentos), prever se ele dará **calote no mês seguinte**
(`default = 1`). Uma predição por cliente, sem depender de outros clientes.

## Decisões que o score alimenta

| Score | Decisão sugerida | Quem decide no fim |
|---|---|---|
| abaixo de 0,5 | aprovar | sistema, com auditoria por amostra |
| acima de 0,5 | negar ou rever condições | revisão humana nos casos limítrofes |
| grupo com disparidade (ADR-006) | revisão humana da negativa | analista de crédito |

O score **ordena** os clientes; ele não é uma probabilidade calibrada ([Model Card](MODEL_CARD.md)).
O cliente pode pedir revisão de qualquer decisão automatizada (LGPD, art. 20).

## Fontes de dados

- **[Default of Credit Card Clients](https://archive.ics.uci.edu/dataset/350)** (UCI): 30.000
  clientes de Taiwan, 2005, baixados sem login ([ADR-001](decisions/ADR-001-dataset.md)).
  Foi escolhido por ter mais de 5.000 linhas (o German Credit tem só 1.000) e atributos sensíveis
  reais, que dão substância à discussão de LGPD e viés.
- **Lotes de produção:** a Produção-base (9.000 clientes que o modelo nunca viu) e lotes derivados
  dela com drift simulado, em intensidade controlada ([DRIFT-001](specs/DRIFT-001.md)).

## Coleta do resultado

O resultado real (`default`) só se conhece **um mês depois** da decisão. Isso define o
monitoramento: o drift das entradas (PSI e KS) aparece na hora, mas a queda de performance (AUC e
taxa de default), que é o que denuncia o concept drift, chega com esse atraso.

## Como as predições são feitas

**Em lotes semanais**, não em tempo real: cada semana passa pelo contrato de dados, pela pontuação
e pelo relatório de drift, e vira um run do MLflow ([OBS-002](specs/OBS-002.md)). Um lote reprovado
no contrato não chega ao modelo.

## Avaliação offline

AUC de 0,732 na validação e de **0,715** na Produção-base, com intervalo de confiança de 95% de
0,701 a 0,728. Esse intervalo é a régua para saber se uma queda é real ou é ruído
([ML-001](specs/ML-001.md)).

## Monitoramento em produção

O coração do projeto. Quatro réguas, calibradas em amostras sem drift para dar poucos alarmes
falsos ([OBS-002](specs/OBS-002.md)):

- **PSI e KS:** a distribuição das entradas mudou (data drift);
- **AUC e taxa de default:** o modelo está errando mais (concept drift).

E duas garantias de processo: o contrato de dados barra o lote sujo
([DQ-002](specs/DQ-002.md)), e o CI barra o PR que afrouxa o contrato ([IMP-001](specs/IMP-001.md)).

## Impacto medido

O experimento de dose-resposta ([GOV-004](specs/GOV-004.md)) traduz a queda de AUC para o negócio.
Em 9.000 clientes, com o concept drift cheio:

| Indicador | Sem drift | Concept drift cheio |
|---|---|---|
| Calotes aprovados | 716 | 1.114 (+56%) |
| Exposição em limite de crédito dos calotes aprovados | NT$ 138 milhões | NT$ 228 milhões (+65%) |

Já o data drift sozinho (faturas mais altas, limites menores) **não** move a AUC: mudar a entrada
não é o mesmo que o modelo errar mais.
