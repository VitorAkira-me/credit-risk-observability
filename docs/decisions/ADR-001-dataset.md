# ADR-001 · Dataset: Default of Credit Card Clients (UCI)

- Status: aceita
- Data: 13/10/2026

## Contexto
O desafio pede um dataset binário financeiro com pelo menos 5.000 amostras. O German Credit,
citado no PDF, tem só 1.000 e não atende. Queremos algo que baixe sem login, para o pipeline ser
reprodutível por qualquer avaliador.

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| UCI Default of Credit Card Clients | 30k linhas, baixa sem login (`ucimlrepo`), atributos sensíveis reais para LGPD | não tem renda nem desemprego explícitos |
| Give Me Some Credit (Kaggle) | 150k linhas, renda com nulos reais | exige login no Kaggle, reprodutibilidade pior |
| Home Credit Default Risk | muito rico | várias tabelas, grande demais para 5 semanas |

## Decisão
UCI Default of Credit Card Clients, pela reprodutibilidade sem login e pela riqueza para a discussão de governança.

## Consequências
- "Renda" do enunciado vira `LIMIT_BAL` (limite de crédito) e `BILL_AMT*` (faturas) como proxies econômicos.
- Os atributos `SEX`, `MARRIAGE`, `EDUCATION` e `AGE` alimentam a análise de viés da Etapa 4.
- A EDA precisa investigar códigos não documentados em `EDUCATION` e `MARRIAGE` (bom insumo para o contrato).
