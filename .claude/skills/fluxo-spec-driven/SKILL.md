---
name: fluxo-spec-driven
description: Use ao iniciar ou continuar qualquer card do Kanban da Fase 4. Conduz spec, aprovação, implementação, validação real, commit semântico e atualização de STATUS.
---

# Fluxo Spec-Driven (um card por vez)

## Antes de tudo
1. Leia `docs/STATUS.md` e a linha do card em `docs/KANBAN.md`. Não leia mais nada sem motivo.
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
8. **Feche:** preencha "Resultado" na spec, mova o card no `KANBAN.md`, atualize `STATUS.md`.
9. **Rode a skill `resumo-didatico`.**

## Quando surgir decisão com trade-off
Crie `docs/decisions/ADR-<NNN>-<slug>.md` a partir do template, apresente 2 ou 3 opções com
prós e contras e uma recomendação. A decisão é do Akira.

## Quando surgir ideia boa fora do escopo
Não implemente. Registre como `IMP-*` no Kanban e siga.
