# STATUS · atualizado em 03/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e status: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Onde estamos
- **Etapa 1 concluída e na `main`** (PRs #1 a #5, `9923dd8`): contrato Pandera com 9 regras e
  portão `run_validation.py`, que bloqueia lote corrompido (exit 1) com contagens exatas.
- Baseline: AUC real ~0,715. Diagnóstico de 03/11: 31 testes passando; ruff check e format limpos.
- SPIKE-001: Evidently 0.7.23 funciona com pandas 3.0.6 em 3 colunas, com PSI e KS.
  Detalhes e armadilhas em `docs/specs/SPIKE-001-evidently.md`.

## Em andamento
Branch `chore/retomada-auditoria`, **sem commit**, aguardando o ok do Akira: spike, `evidently` e
`scipy` fixados no `pyproject.toml`, saneamento de STATUS, README e KANBAN.

## Decisões registradas em 03/11
- ADR-005: relatórios de validação minimizados na origem (opção C), implementação no GOV-001 (PMF4-22).
- KANBAN com coluna Status espelhando o Jira; `fluxo-spec-driven` atualizada para o novo fluxo.

## Pendência (Akira)
- ADR-004: PMF4-35 está To Do no Jira, e o arquivo diz "aguardando revisão".

## Próximo passo
Depois do commit: DRIFT-001 (PMF4-16). Lote com data drift em ≥ 2 features e
concept drift, com deslocamentos documentados. Precisa passar no contrato. Comparar contra a
Produção-base, não contra a validação (ruído de seed, ver ML-001).
Modo: Claude pilota por causa do prazo.

## Prazo
A referência é o Jira. Entrega em 17/11/2026. **~2 dias atrás do plano do Jira:** DRIFT-001 venceu em
02/11 e não começou; DRIFT-002 vence em 06/11. Plano de corte no CLAUDE.md §8.
