# STATUS · atualizado em 04/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md`, revisadas com o Akira antes do vídeo (PMF4-38).

## Onde estamos
- Etapa 1 concluída. ADR-005 será implementado no GOV-001 (PMF4-22).
- DRIFT-001 concluído, com 2 lotes aprovados no contrato e manifesto em `reports/drift/`.
- DRIFT-002 concluído: um HTML e um JSON por lote em `reports/drift/`, versionados como evidência e não regerados.
  - Produção-base: sem drift relevante (AUC 0,7149).
  - Data drift: `LIMIT_BAL` pelo PSI, `LIMIT_BAL` e as 6 faturas pelo KS; sem impacto no modelo (AUC 0,7144).
  - Concept drift: nenhuma feature mudou; suspeita de concept drift (AUC 0,6647).
- 90 testes passando; ruff limpo.

## Pendências (Akira)
- ADR-004: PMF4-35 está To Do no Jira, e o arquivo diz "aguardando revisão".
- Citar o ADR-005 no card PMF4-22, para a decisão não se perder.
- Débitos de `prepare_data.py` e `inject_defects`: PMF4-39, prioridade baixa.

## Próximo passo
DRIFT-003 (PSI à mão): a referência é a regra de bins do SPIKE-001 e o preenchimento de zeros de `get_binned_data`.
OBS-002 (PMF4-20): corrigir as réguas herdadas (comentário no Jira) e levar os relatórios para fora do git.

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
