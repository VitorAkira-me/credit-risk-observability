# STATUS · atualizado em 08/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md` (1 a 44), revisadas com o Akira antes do vídeo (PMF4-38).

## Onde estamos
- **Etapas 1 a 4 concluídas** (épicos PMF4-2, 4 e 5 em Done; PMF4-3 aberto só pelo DRIFT-003).
  - Etapa 2: evidência em `reports/drift/`, reproduzível (CI confere os hashes).
  - Etapa 3: log estruturado, MLflow com 5 semanas, réguas calibradas, painel e métricas no README.
  - Etapa 4: inventário de PII e ADR-005; viés (idade reprova a regra dos 4/5: 0,663); análise causal
    por dose-resposta (o concept drift causa a queda); base legal e retenção por código.
- CI (ruff, pytest, portão de contrato com dados reais) e CD (pipeline a cada merge) verdes na `main`.
- DRIFT-003 em andamento (**Akira pilota**): andaime mergeado (PR #20); falta `psi()`.
- DOC-001 em revisão: README final reestruturado; "como rodar" testado do zero (2min46, Linux).
- VID-001 em andamento: rascunho cronometrado em `docs/video/roteiro.md` (3min16 de fala, 7 telas).
- 125 testes passando (+5 pulados até a `psi()` existir); ruff limpo.

## Pendências (Akira)
- Implementar `psi()` (DRIFT-003, spec em `docs/specs/DRIFT-003.md`).
- Testar o "Como rodar" do README no PowerShell (DOC-001).
- Reescrever o roteiro com a sua voz e cronometrar lendo em voz alta (VID-001), depois do REPASSE.
- Decidir o ADR-006 (viés por idade) e revisar o ADR-004 (PMF4-35).
- Conferir as citações da LGPD no Planalto (listas nas specs do GOV-001 e GOV-002): o site recusa a nuvem.
- Revisar os textos "Akira pilota" escritos pelo Claude (OBS-003, GOV-001 a GOV-004).
- Exigir os checks do CI na proteção da `main` (Settings > Branches).
- Apagar a branch remota `claude/project-continuity-jira-51vtlk` (a sessão não tem permissão).
- Débitos: PMF4-39; `run_validation.py`/`make_drift_batch.py` ainda gravam em `reports/` (REPASSE 27).

## Próximo passo
DRIFT-003 (Akira), REPASSE-001 (sessão de revisão, 13/11, antes do roteiro),
VID-001 e VID-002 (roteiro e gravação, 14 e 15/11), ENTREGA-001 (17/11).

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
