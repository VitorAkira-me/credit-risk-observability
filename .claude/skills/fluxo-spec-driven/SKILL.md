---
name: fluxo-spec-driven
description: Use ao iniciar ou continuar qualquer card da Fase 4. Conduz spec, aprovação, implementação, validação real, commit semântico e atualização de STATUS.
---

# Fluxo Spec-Driven (um card por vez)

## Antes de tudo
1. Leia `docs/STATUS.md` e o card no Jira (chave em `docs/KANBAN.md`). Não leia mais nada sem motivo.
2. Confirme com o Akira qual card será feito.

## Ciclo
1. **Spec.** Copie `docs/specs/_TEMPLATE.md` para `docs/specs/<ID>.md` e preencha. Inclua a seção
   "Conceito por trás" em linguagem simples.
2. **PARE e peça aprovação.** Mostre objetivo, passos e critérios de aceite em poucas linhas.
3. **Branch:** `feat/<ID>-<slug>` (ou `docs/`, `fix/`).
4. **Implemente em passos pequenos.** Ao fim de cada passo que muda comportamento, mostre o que
   mudou e espere o ok antes do próximo.
5. **Valide de verdade.** Rode o comando da spec. Mostre números (linhas, contagens, métricas,
   exit codes). Desconfie de "sucesso vazio": confirme que o artefato foi de fato gerado ou reescrito.
6. **Testes:** `uv run pytest -q`.
7. **Commit em português:** `tipo(escopo): descrição curta`. Um commit por passo lógico.
8. **Feche:** preencha "Resultado" na spec, abra o PR e, no mesmo momento, mova o card no Jira para
   In Review com um comentário (resumo, números e link do PR). No merge, mova para Done.
   A coluna Status do `KANBAN.md` acompanha o Jira, e o `STATUS.md` é atualizado em todo passo.
   Ao começar um card, mova-o para In Progress (e o épico, se for o primeiro card dele).
   Sem acesso ao Jira, avise o Akira na hora e registre a pendência no `STATUS.md`.
9. **Rode a skill `resumo-didatico`.**

## Quando surgir decisão com trade-off
Crie `docs/decisions/ADR-<NNN>-<slug>.md` a partir do template, apresente 2 ou 3 opções com
prós e contras e uma recomendação. A decisão é do Akira.

## Quando surgir ideia boa fora do escopo
Não implemente. Registre como `IMP-*` no Jira (sem acesso, peça ao Akira) e siga.
