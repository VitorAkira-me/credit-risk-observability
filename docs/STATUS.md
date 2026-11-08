# STATUS · atualizado em 08/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md`, revisadas com o Akira antes do vídeo (PMF4-38).

## Onde estamos
- Etapas 1 e 2 (parte obrigatória) concluídas. Evidência de drift versionada em `reports/drift/`.
- OBS-001 concluído e validado com os dados reais (9.000 aprovadas; corrompido com 130 linhas rejeitadas).
- OBS-002 concluído: réguas recalibradas para lotes de 2.000 (`reports/monitoring/alert_thresholds.json`),
  5 semanas no MLflow e painel em `reports/figures/painel_semanas.png`. O concept drift alarma na
  semana 3, antes do PSI (semana 4).
- 111 testes passando; ruff limpo.

## Pendências (Akira)
- Mover PMF4-19 e PMF4-20 para Done no Jira (a escrita no Jira foi bloqueada nesta sessão).
- Apagar a branch remota `claude/project-continuity-jira-51vtlk` (a sessão não tem permissão).
- ADR-004: PMF4-35 está To Do, e o arquivo diz "aguardando revisão".
- Citar o ADR-005 no card PMF4-22.
- Débitos: PMF4-39; e `run_validation.py`/`make_drift_batch.py` ainda gravam em `reports/` (REPASSE 27).

## Próximo passo
OBS-003 (PMF4-21, prazo 10/11): boa parte já está no README (tabela das réguas); falta a tabela de
métricas de saúde do pipeline. Depois GOV-001 a GOV-004 (11 a 13/11) e DRIFT-003 (13/11).

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
