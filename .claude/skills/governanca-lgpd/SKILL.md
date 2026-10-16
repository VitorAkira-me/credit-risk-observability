---
name: governanca-lgpd
description: Use na Etapa 4 (GOV-001) para escrever no README o plano de proteção de dados (PII, base legal, retenção), a mitigação de vieses e a análise causal da degradação.
---

# Governança, LGPD e causalidade (Etapa 4, 15% da nota)

## Seções obrigatórias no README
1. **Inventário de dados:** tabela coluna, tipo, é PII?, é sensível (art. 5º, II)?, usada no modelo?, tratamento.
   No UCI Taiwan, por exemplo: `ID` (identificador, pseudonimizar ou descartar), `SEX`, `MARRIAGE`,
   `EDUCATION`, `AGE` (dados que podem gerar discriminação).
2. **Privacy by Design e by Default:** minimização (só colunas necessárias), pseudonimização do ID
   (hash com sal), dados brutos fora do git, acesso mínimo, logs sem PII.
3. **Base legal:** art. 7º da LGPD. Discutir proteção do crédito (inc. X) e execução de contrato
   (inc. V) e por que consentimento é frágil aqui. Citar o art. 20 (direito de revisão de decisão
   automatizada) e o que isso exige de explicabilidade.
4. **Retenção e descarte:** prazo por tipo de dado, justificativa, como é apagado.
5. **Vieses:** medir a diferença de taxa de aprovação e de erro entre grupos (ex.: sexo, faixa
   etária) na referência e na produção. Discutir se remover a coluna sensível resolve
   (spoiler: proxies como escolaridade e estado civil podem carregar a mesma informação).
6. **Análise causal:** o PDF pede "Governança e Causalidade". Separar **correlação** de **causa** na
   degradação: o que mudou no mundo (cenário econômico), como isso se propagou para as features
   (data drift), como mudou a relação com o default (concept drift) e qual o impacto no negócio.
   Um diagrama causal simples (causa econômica, features, decisão, resultado) ajuda muito.
7. **Plano de ação:** o que fazer quando o alerta dispara (investigar, retreinar, rollback, revisão humana).

## Cuidados
- Não citar artigos de lei de memória sem conferir o texto oficial (planalto.gov.br, Lei 13.709/2018).
- Não é parecer jurídico: deixe claro que é um plano técnico de conformidade.

## Pergunta para deixar no ar
Se o modelo nunca recebe a coluna `SEX`, ele pode ainda assim discriminar por sexo? Como você provaria?
