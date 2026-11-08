# ADR-005 · Minimizar dados pessoais nos relatórios de validação

- Status: aceita e implementada no GOV-001 (08/11/2026)
- Data: 03/11/2026

## Contexto
Uma auditoria de 03/11 apontou que `reports/validation/batch_corrupted_failure_cases.csv` está
versionado em repositório público. O arquivo tem 40 linhas com **20 IDs reais do dataset UCI**. As
idades (sempre 15) e os `SEX` (sempre 3) são os valores que nós injetamos, não dados de clientes.

O risco hoje é baixo, porque o dataset já é público. O problema é o comportamento do código:
`scripts/run_validation.py` grava o valor de cada falha em uma pasta versionada. Com dados reais, isso
publicaria dados de clientes, contra o princípio da necessidade da LGPD (art. 6º, III).

## Opções consideradas
| Opção | Prós | Contras |
|---|---|---|
| A. Manter e documentar | nenhum trabalho; evidência do DQ-002 intacta | o código segue expondo valores; a Etapa 4 defenderia minimização com um contraexemplo no repo |
| B. Parar de versionar o CSV, mantendo o `_summary.json` | ~10 min; as contagens continuam como evidência | o script ainda grava os valores localmente, sem retenção; o detalhe só existe regerando |
| C. Minimizar na origem: relatório versionado com regra, contagem e posição da linha, sem o valor; detalhe local, fora do git | vale para dados reais; um teste garante a regra; evidência de Privacy by Design | ~30 a 45 min; mexe no código e nos testes do DQ-002; investigar um cliente depende do detalhe local |

## Decisão
Opção **C**, por corrigir a causa em vez do sintoma. Trocar o ID por um hash não basta: os IDs são
sequenciais, e o hash seria fácil de reverter sem um segredo.

## Por que não reescrever o histórico
O arquivo continua acessível no commit `1471353`, e aceitamos isso:
- os dados vieram de um dataset público, então a reescrita não protege ninguém;
- exigiria desligar a proteção da `main` para um force push;
- mudaria os hashes já referenciados nos PRs, e não alcançaria cópias já feitas do repositório.

Com dados reais a resposta seria outra: reescrever e tratar como incidente.

## Quando será implementada
Dentro do **GOV-001 (PMF4-22)**, não agora: a Etapa 2 está atrasada e é ela que protege a nota.
Critério de pronto: um teste prova que o relatório versionado não contém valores das linhas barradas, e o
CSV atual é regerado no novo formato.

## Consequências
- Até lá, o CSV atual permanece no repositório, e `run_validation.py` **não deve processar dados reais**.
- As contagens por regra do DQ-002 continuam valendo como evidência, no `_summary.json`.
- O GOV-001 precisa definir a retenção do detalhe local.
