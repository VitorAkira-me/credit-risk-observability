# STATUS · atualizado em 08/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md`, revisadas com o Akira antes do vídeo (PMF4-38).

## Onde estamos
- Etapas 1 e 2 (parte obrigatória) concluídas. Evidência de drift versionada em `reports/drift/`.
- OBS-001 concluído (08/11): `logs/pipeline.jsonl` com esquema fixo de 9 campos, `pipeline_step`
  mede latência e registra falha até em exceção; sem PII. Relatório de drift agora grava em `outputs/drift/`.
- 99 testes passando; ruff limpo.

## Pendências (Akira)
- Rodar a validação real do OBS-001 (comando na spec) com os lotes reais: a sessão na nuvem não baixa o UCI.
- ADR-004: PMF4-35 está To Do no Jira, e o arquivo diz "aguardando revisão".
- Citar o ADR-005 no card PMF4-22.
- Débitos de `prepare_data.py` e `inject_defects`: PMF4-39, prioridade baixa.

## Próximo passo
OBS-002 (PMF4-20, prazo 10/11): MLflow lendo o `pipeline.jsonl` e os JSON de drift, mais as 3 réguas
herdadas (comentário no Jira). Depois OBS-003 (10/11) e GOV-001 a GOV-004 (11 a 13/11).
DRIFT-003 (PSI à mão) segue em paralelo, prazo 13/11.

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
