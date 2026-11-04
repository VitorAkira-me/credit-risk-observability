# STATUS · atualizado em 04/11/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.
> Tarefas e prazos: Jira, projeto PMF4 (mapeamento em `docs/KANBAN.md`).

## Modo de trabalho
**Modo prazo até a entrega:** Claude decide e segue, parando só em commit/PR, algo irreversível ou mudança no que é entregue.
Decisões em `docs/REPASSE.md`, revisadas com o Akira antes do vídeo (PMF4-38).

## Onde estamos
- Etapa 1 concluída. Evidently 0.7.23 confirmado com pandas 3.0.6 (SPIKE-001). ADR-005 será implementado no GOV-001 (PMF4-22).
- DRIFT-001 concluído, com 2 lotes aprovados no contrato e manifesto em `reports/drift/`.
  - Data drift (faturas × 1,25, limite × 0,75): PSI do limite 0,27; PSI das faturas de 0,025 a 0,046; AUC 0,7144.
  - Concept drift (459 rótulos, nenhuma entrada mudou): AUC 0,6647, contra 0,7149 da Produção-base.
- 59 testes passando; ruff limpo.

## Pendências (Akira)
- ADR-004: PMF4-35 está To Do no Jira, e o arquivo diz "aguardando revisão".
- Citar o ADR-005 no card PMF4-22, para a decisão não se perder.

## Próximo passo
DRIFT-002: `detect.py`, relatório Evidently e predições, usando o `DataDefinition` proposto no REPASSE (entrada 7).
DRIFT-003 (PSI à mão): a referência é a regra de bins documentada no SPIKE-001.

## Prazo
A referência é o Jira. Entrega em 17/11/2026. Plano de corte no CLAUDE.md §8.
