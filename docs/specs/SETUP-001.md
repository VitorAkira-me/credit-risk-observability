# SETUP-001 · Estrutura inicial do projeto

- Etapa: 0 (fundação)
- Status: rascunho
- Data: 15/10/2026

## Objetivo
Deixar o repositório pronto para receber código: git iniciado, ambiente Python 3.12 gerenciado
pelo `uv` com versões fixadas, estrutura de pastas do CLAUDE.md §6, `.gitignore` e um teste
trivial passando. Não atende diretamente um critério da nota, mas atende "commits organizados"
e evita o drift de ambiente que nos mordeu na Fase 3.

## Conceito por trás (didático)
Um projeto reprodutível é como uma receita com as marcas e quantidades exatas dos ingredientes:
qualquer pessoa (ou o avaliador) obtém o mesmo bolo. O `pyproject.toml` diz *quais* bibliotecas
queremos; o `uv.lock` grava *exatamente quais versões* foram instaladas. Sem o lock, "funciona na
minha máquina" vira loteria. O layout `src/` obriga o código a ser instalado como pacote, então os
testes importam `credit_obs` do mesmo jeito que um usuário importaria, e não por acaso do diretório atual.

## Escopo
- Dentro:
  - `git init` com branch `main`; trabalho na branch `chore/SETUP-001-estrutura`.
  - `uv init` com layout de pacote (`src/credit_obs/`), Python fixado em 3.12 (`.python-version`).
  - Dependências de dev: `pytest`, `ruff`. Só isso agora.
  - Pastas do CLAUDE.md §6 (vazias com `.gitkeep` onde preciso).
  - `.gitignore`: `.venv/`, `__pycache__/`, `data/raw/`, `mlruns/`, caches.
  - `tests/test_smoke.py`: importa o pacote e confere a versão.
  - README mínimo (só título e "como rodar"; governança vem no GOV-001).
- Fora:
  - Dependências de domínio (pandas, sklearn, pandera, evidently, mlflow): entram em cada card
    que precisar delas, com versão fixada, para o lock crescer junto com o uso.
  - Criar o repo no GitHub e proteger a `main`: passo manual do Akira ao final (eu passo os comandos).
  - CI no GitHub Actions: já é melhoria prevista no Kanban.

## Passos
1. `git init -b main`, criar branch do card.
2. `uv init --package --python 3.12` e ajustar `pyproject.toml` (nome, descrição, autor).
3. `uv add --dev pytest ruff` (gera `uv.lock`).
4. Criar pastas + `.gitkeep`, `.gitignore`, README mínimo.
5. Escrever `tests/test_smoke.py`.
6. Validar (abaixo) e commitar `chore(setup): estrutura inicial do projeto`.

## Critérios de aceite (verificáveis)
- [ ] `uv run python --version` mostra 3.12.x (a máquina tem 3.11 global; o uv baixa o 3.12)
- [ ] `uv run pytest -q` mostra `1 passed`, exit code 0
- [ ] `uv run ruff check .` sem erros
- [ ] `uv.lock` existe e está versionado
- [ ] `git status` limpo após o commit; `data/raw/` ignorado (`git check-ignore data/raw/x.csv` responde)

## Como validar de verdade
```
uv run python --version
uv run pytest -q ; echo "exit=$?"
uv run ruff check .
git check-ignore -v data/raw/teste.csv
git log --oneline
```
Rodar também no PowerShell (lição da Fase 3).

## Riscos e perguntas em aberto
- O Python global é 3.11; se o `uv python install 3.12` falhar (rede/proxy), precisamos instalar manualmente.
- `reports/` será versionado (evidência), `data/reference` e `data/production` serão gerados por script:
  versionar ou não? Proposta: **não** versionar parquet (regerável e pesado), só `reports/`.

## Resultado (preencher ao concluir)
