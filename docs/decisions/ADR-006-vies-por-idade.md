# ADR-006 · Mitigar o viés por idade

- Status: **aceita** (proposta pelo Claude em 08/11/2026; decidida pelo Akira em 09/11/2026)
- Data: 09/11/2026

## Contexto
A auditoria do GOV-003 (`reports/fairness/fairness_report.json`) mediu, na Produção-base:

| Recorte | Paridade demográfica | Razão (regra dos 4/5) | Igualdade de oportunidade |
|---|---|---|---|
| Sexo (modelo atual, sem `SEX`) | 0,051 | 0,920 (passa) | 0,048 |
| Idade (modelo atual, com `AGE`) | 0,228 | **0,663 (reprova)** | 0,237 |

Clientes com 50 anos ou mais são aprovados em 44,8% dos casos; de 30 a 39, em 67,6%. Entre os bons
pagadores, 50,6% contra 74,3%. Parte disso vem da diferença real de default (26,0% contra 19,8%),
mas o modelo amplia a diferença.

Contrafactuais (mesmo modelo, mesma Referência, medidos na Produção-base):

| Modelo | AUC | Paridade por idade | Razão por idade | Paridade por sexo |
|---|---|---|---|---|
| Atual (ADR-004, opção B) | 0,7149 | 0,228 | 0,663 | 0,051 |
| Sem `AGE` (opção C do ADR-004) | 0,7137 | 0,134 | 0,800 | 0,047 |
| Com `SEX` e `MARRIAGE` (opção A) | 0,7173 | 0,169 | 0,745 | 0,125 |

## Opções
| Opção | Prós | Contras |
|---|---|---|
| A. Manter o modelo e documentar | nenhuma mudança; a evidência de drift continua valendo | reprova a regra dos 4/5 por idade; difícil de defender numa revisão (art. 20) |
| B. Tirar `AGE` do modelo | custo de AUC de 0,0012 (menor que o ruído entre seeds); razão sobe para 0,800 | fica no limite da regra; o viés muda de lado (menores de 29 passam a ser os menos aprovados, via proxies como o limite) |
| C. Manter `AGE` e ajustar o limiar por grupo | controla a paridade diretamente | decisão diferente por idade é tratamento explícito pelo atributo: pior juridicamente |
| D. Revisão humana para os grupos com disparidade | não mexe no modelo; atende ao direito de revisão | custo operacional; não corrige a causa |

## Recomendação do Claude
**B, com D como rede de segurança**, a partir da próxima versão do modelo (retreino). Não aplicar
agora: mudar o modelo invalidaria a evidência versionada das Etapas 2 e 3. A troca entra junto
com o primeiro retreino previsto no plano de ação (GOV-004).

## Decisão
Opção **B com D como rede de segurança**, aplicada no **próximo retreino**, e não agora.

- **B:** `AGE` sai das features do modelo. A razão da regra dos 4/5 por idade sobe de 0,663 para
  0,800, a um custo de 0,0012 de AUC, menor que o ruído entre seeds (0,714 a 0,732 na validação).
- **D:** até o retreino, e depois dele, as negativas dos grupos com disparidade vão para revisão
  humana. É o caminho humano do direito de revisão (LGPD, art. 20).
- **Por que não agora:** retreinar mudaria todos os números das Etapas 2 e 3, e a evidência
  versionada em `reports/` deixaria de valer a 8 dias da entrega. O modelo atual fica documentado
  como está, com o viés medido e explicado.

## Consequências
- `SENSITIVE_EXCLUDED` passa a incluir `AGE`; o ADR-004 fica revisado (opção C).
- A auditoria do GOV-003 roda a cada retreino, com a regra dos 4/5 como critério de aprovação.
- Acompanhar a nova disparidade contra os mais jovens, que a mudança cria.
