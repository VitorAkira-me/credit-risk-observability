# STATUS · atualizado em 21/10/2026

> Arquivo curto de "onde paramos". Atualize ao fim de toda sessão. Máximo ~40 linhas.

## Onde estamos
- SETUP-001 concluído: uv + Python 3.12.10, pacote `src/credit_risk_observability/`, `uv.lock`,
  pytest (3 passed) e ruff (check + format) limpos. Detalhes em `docs/specs/SETUP-001.md`.
- Repo no GitHub: `VitorAkira-me/credit-risk-observability`, `main` criada, trabalho via PR por card.
- Decisões aceitas: ADR-001 (dataset UCI Taiwan), ADR-002 (Pandera), ADR-003 (MLflow local).
- Lição da sessão: `ruff --show-files` revelou lint vazio (só checava o pyproject). Sempre confira
  *o que* a ferramenta analisou, não só o veredito.

## Pendências manuais (Akira)
- Proteger a `main` no GitHub (Settings > Branches) e definir `main` como branch padrão, se ainda não estiver.

## Próximo passo
DATA-001: download via `ucimlrepo`, EDA curta, split Referência / Produção em parquet.
Modo: Akira pediu que Claude pilote por causa do prazo; manter explicações curtas.

## Prazo
Entrega 17/11/2026. Semana atual: 2 de 5 (atrasado ~1 semana: DATA-001 e ML-001 eram da semana 1).
