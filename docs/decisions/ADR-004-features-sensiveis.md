# ADR-004 · Atributos sensíveis fora das features do modelo

- Status: aceita (proposta pelo Claude em 21/10/2026, aguardando revisão do Akira)
- Data: 21/10/2026

## Contexto
O dataset traz `SEX`, `MARRIAGE`, `EDUCATION` e `AGE`. A LGPD (art. 6º, IX) proíbe tratamento
para fins discriminatórios ilícitos, e o art. 20 dá ao titular direito de revisão de decisões
automatizadas. Precisamos decidir quais desses atributos o baseline (ML-001) usa como entrada.

Medição na validação da Referência (LogisticRegression, mesmo pré-processamento, seed 42):

| Features | AUC validação |
|---|---|
| Todas as 23 | 0,7336 |
| Sem `SEX` e `MARRIAGE` | 0,7318 |
| Sem `SEX`, `MARRIAGE` e `AGE` | 0,7301 |

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| A. Usar todas | maior AUC (+0,0018) | decisão de crédito baseada em sexo e estado civil: difícil de justificar em revisão (art. 20) |
| B. Tirar `SEX` e `MARRIAGE` | custo de AUC desprezível; explicável; atributos continuam nos dados para auditar viés | não elimina viés: outras features podem ser *proxy* de sexo |
| C. Tirar também `AGE` | menos atributos pessoais | idade é usada legitimamente em crédito e é feature planejada para o drift de "novo público jovem" |

## Decisão
Opção **B**. O ganho de A (0,0018) é dez vezes menor que a variação da AUC de validação
ao trocar só a seed do split (0,714 a 0,732, ver ML-001), e não compensa o risco
regulatório e reputacional. `AGE` fica (opção C descartada) porque tem uso legítimo e explicável
em risco de crédito e será monitorada na análise de viés.

## Consequências
- `SEX` e `MARRIAGE` **continuam** em Referência e Produção: são necessários para medir viés
  (taxa de aprovação e erro por grupo) na Etapa 4. Retirar a coluna do modelo não é o mesmo que
  apagar o dado.
- "Fairness by unawareness" não basta: o GOV-001 precisa medir disparidade por `SEX` mesmo com o
  modelo sem acesso a ele.
- O contrato de dados (DQ-001) continua validando essas colunas.
