# ADR-002 · Contratos de dados com Pandera

- Status: aceita
- Data: 13/10/2026

## Contexto
O desafio aceita Great Expectations ou Pandera. Diretriz do projeto: começar simples e melhorar depois.

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| Pandera | schema em Python puro, curva curta, `lazy=True` coleta todos os erros, fácil de testar com pytest | relatórios visuais mais simples |
| Great Expectations | Data Docs em HTML, muito usado em empresas | configuração (contexto, suites, checkpoints) pesada para o prazo |

## Decisão
Pandera.

## Consequências
Os erros de validação viram um DataFrame (`failure_cases`) que salvamos em `reports/validation/`.
Se sobrar tempo, um relatório HTML simples desses erros pode ser uma melhoria (`IMP-*`).
