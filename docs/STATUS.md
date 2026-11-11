# STATUS · atualizado em 08/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md` (1 a 50), revisadas com o Akira depois da entrega (PMF4-38, 21/11).

## Onde estamos
- **Etapas 1 a 4 concluídas** (épicos PMF4-2, 4 e 5 em Done).
  - Etapa 2: evidência em `reports/drift/`, reproduzível (CI confere os hashes).
  - Etapa 3: log estruturado, MLflow com 5 semanas, réguas calibradas, painel e métricas no README.
  - Etapa 4: inventário de PII e ADR-005; viés (idade reprova a regra dos 4/5: 0,663); análise causal
    por dose-resposta (o concept drift causa a queda); base legal e retenção por código.
- CI (ruff, pytest, portão de contrato com dados reais) e CD (pipeline a cada merge) verdes na `main`.
- DRIFT-003 em revisão: `psi()` feita pelo Claude por decisão do Akira; ele refaz à mão no repasse.
- DOC-001 concluído (PR #21): README final reestruturado; "como rodar" testado do zero (2min46, Linux).
- VID-001 em revisão: roteiro v3 em `docs/video/roteiro.md`, números conferidos (4min10 de fala, 9 telas).
- DOC-002 (PMF4-40) concluído (PR #24): Model Card, ML Canvas, Roadmap, README reestruturado, Makefile, pre-commit
  e cobertura de 93%; ADR-006 decidido (B + D no próximo retreino).
- 130 testes passando; ruff limpo.

## Pendências (Akira)
- Cronometrar o roteiro em voz alta e gravar (VID-001 e VID-002).
- ADR-004 aceito por delegação (PMF4-35): revisar no repasse. ADR-006: tirar `AGE` no próximo retreino.
- Conferir as citações da LGPD no Planalto (listas nas specs do GOV-001 e GOV-002): o site recusa a nuvem.
- Revisar os textos "Akira pilota" escritos pelo Claude (OBS-003, GOV-001 a GOV-004).
- Exigir os checks do CI na proteção da `main` (Settings > Branches).
- Apagar a branch remota `claude/project-continuity-jira-51vtlk` (a sessão não tem permissão).
- Débitos: PMF4-39; `run_validation.py`/`make_drift_batch.py` ainda gravam em `reports/` (REPASSE 27).

## Próximo passo
Finalização delegada em andamento (ADR-004, LGPD, GitHub, AWS com corte em 13/11).
VID-002 (gravação, 15/11), ENTREGA-001 (17/11), REPASSE-001 (21/11, depois da entrega).

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
