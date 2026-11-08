# STATUS · atualizado em 08/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md`, revisadas com o Akira antes do vídeo (PMF4-38).

## Onde estamos
- Etapas 1 e 2 (parte obrigatória) concluídas. Evidência de drift versionada em `reports/drift/`.
- OBS-001 concluído e validado com os dados reais (9.000 aprovadas; corrompido com 130 linhas rejeitadas).
- OBS-002 concluído (PR #12 mergeado): réguas recalibradas para lotes de 2.000 (`reports/monitoring/alert_thresholds.json`),
  5 semanas no MLflow e painel em `reports/figures/painel_semanas.png`. O concept drift alarma na
  semana 3, antes do PSI (semana 4).
- IMP-001 concluído (PR #14): CI (ruff, pytest e portão de contrato com dados reais) em todo PR e merge; CD que roda
  o pipeline de monitoramento a cada merge e publica os artefatos.
- OBS-003 em revisão: tabela de métricas de saúde, prints do MLflow e guia "retreinar ou não" no README.
- 111 testes passando; ruff limpo.

## Pendências (Akira)
- Revisar o texto do OBS-003 no README (card "Akira pilota", rascunho do Claude).
- Exigir os checks do CI na regra de proteção da `main` (Settings > Branches), senão o CI só avisa.
- Apagar a branch remota `claude/project-continuity-jira-51vtlk` (a sessão não tem permissão).
- ADR-004: PMF4-35 está To Do, e o arquivo diz "aguardando revisão".
- Citar o ADR-005 no card PMF4-22.
- Débitos: PMF4-39; e `run_validation.py`/`make_drift_batch.py` ainda gravam em `reports/` (REPASSE 27).

## Próximo passo
GOV-001 a GOV-004 (PMF4-22 a 25, prazos de 11 a 13/11): inventário de PII com o ADR-005, base legal e
retenção, viés por grupo e análise causal. DRIFT-003 (PSI à mão) segue em paralelo, prazo 13/11. Depois GOV-001 a GOV-004 (11 a 13/11) e DRIFT-003 (13/11).

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
