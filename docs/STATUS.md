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
- OBS-003 concluído (PR #15): métricas de saúde, prints do MLflow e guia de retreino no README.
- IMP-001 concluído (PR #14): CI (ruff, pytest e portão de contrato com dados reais) em todo PR e merge. O CD rodou verde na `main` duas vezes, com os limites
  calibrados idênticos na máquina do GitHub, e publicou o artefato `monitoramento-<sha>` (12,7 MB, 30 dias).
- GOV-001 concluído (PR #16): inventário de PII, Privacy by Design e ADR-005 implementado.
- GOV-003 concluído (PR #17): viés por grupo. Sexo passa na regra dos 4/5 (0,920); idade reprova (0,663),
  contra os mais velhos. Mitigação proposta no ADR-006 (tirar `AGE` no retreino), aguardando decisão.
- GOV-004 concluído (PR #18): dose-resposta prova que o concept drift causa a queda (AUC 0,715 a 0,665) e o
  data drift não (0,7149 a 0,7144); calotes aprovados +56%. Diagrama causal e plano de ação no README.
- GOV-002 concluído (PR #19): base legal, art. 20 e retenção por código. **Etapa 4 fechada.**
- DRIFT-003 em andamento (Akira pilota): esqueleto, 5 testes e script de comparação prontos; falta `psi()`.
- 113 testes passando; ruff limpo.

## Pendências (Akira)
- Revisar os textos do OBS-003 e do GOV-001 no README (cards "Akira pilota", rascunhos do Claude).
- Conferir as citações da LGPD no Planalto (listas nas specs do GOV-001 e do GOV-002): o site recusa a nuvem.
- Exigir os checks do CI na regra de proteção da `main` (Settings > Branches), senão o CI só avisa.
- Apagar a branch remota `claude/project-continuity-jira-51vtlk` (a sessão não tem permissão).
- Decidir o ADR-006 (viés por idade) e revisar o ADR-004 (PMF4-35, "aguardando revisão").
- Débitos: PMF4-39; e `run_validation.py`/`make_drift_batch.py` ainda gravam em `reports/` (REPASSE 27).

## Próximo passo
Akira implementa `psi()` (DRIFT-003). Depois REPASSE-001, DOC-001 (README final) e o vídeo (VID-001/002). DRIFT-003 (PSI à mão) segue em paralelo, prazo 13/11. Depois GOV-001 a GOV-004 (11 a 13/11) e DRIFT-003 (13/11).

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
