# Atalhos do projeto. O make é opcional: cada alvo só chama comandos `uv run`, que funcionam
# iguais no Linux, no macOS, no WSL e no Windows sem make (copie a linha do alvo).
# Uso: make <alvo>. Sem alvo, mostra a ajuda.

.DEFAULT_GOAL := help
.PHONY: cdk-synth cdk-diff cdk-deploy cdk-destroy help install data train contract drift monitor governance evidence pipeline mlflow test coverage lint format precommit restore-evidence

# Infra na AWS (ADR-007). Versão do CDK fixada; PROFILE é o perfil de ~/.aws/config.
CDK = npx --yes aws-cdk@2.1148.0
PROFILE ?= RM371483

## Gera o modelo do CloudFormation, sem criar nada
cdk-synth:
	cd infra && $(CDK) synth --strict --quiet --profile $(PROFILE)

## Mostra o que mudaria na AWS, sem criar nada
cdk-diff:
	cd infra && $(CDK) diff --no-change-set --profile $(PROFILE)

## Cria a infra. Uso: make cdk-deploy ALERT_EMAIL=voce@exemplo.com
cdk-deploy:
	cd infra && $(CDK) deploy --profile $(PROFILE) --parameters AlertEmail=$(ALERT_EMAIL)

## Remove a infra (a stack CDKToolkit do bootstrap continua: ver ADR-007)
cdk-destroy:
	cd infra && $(CDK) destroy --profile $(PROFILE)

## Lista os comandos disponíveis
help:
	@echo "Comandos (make <alvo>):"
	@echo "  cdk-synth, cdk-diff, cdk-deploy, cdk-destroy: infra na AWS (ADR-007)"
	@echo "  install           Instala as dependências fixadas e o hook do pre-commit"
	@echo "  data              Etapa 0: download, EDA e split Referência / Produção"
	@echo "  train             Etapa 0: treina o baseline e salva as métricas"
	@echo "  contract          Etapa 1: gera o lote corrompido e mostra o portão barrando (exit 1 esperado)"
	@echo "  drift             Etapa 2: lotes com drift e relatórios do Evidently"
	@echo "  monitor           Etapa 3: calibra as réguas, roda as 5 semanas no MLflow e gera o painel"
	@echo "  governance        Etapa 4: viés por grupo, análise causal e retenção (em simulação)"
	@echo "  evidence          Portão do CI: contrato e hashes da evidência (depois de make drift)"
	@echo "  pipeline          Roda tudo do zero, na ordem do README"
	@echo "  mlflow            Abre o painel do MLflow em http://localhost:5000"
	@echo "  test              Roda os testes"
	@echo "  coverage          Roda os testes com a cobertura do pacote src/"
	@echo "  lint              Confere estilo e formatação com o ruff"
	@echo "  format            Corrige estilo e formatação com o ruff"
	@echo "  precommit         Roda os hooks do pre-commit em todos os arquivos"
	@echo "  restore-evidence  Desfaz as regravações da evidência versionada feitas por uma execução"

## Instala as dependências fixadas e o hook do pre-commit
install:
	uv sync
	uv run pre-commit install

## Etapa 0: download, EDA e split Referência / Produção
data:
	uv run python scripts/prepare_data.py

## Etapa 0: treina o baseline e salva as métricas
train:
	uv run python scripts/train_baseline.py

## Etapa 1: gera o lote corrompido e mostra o portão barrando (exit 1 esperado)
contract:
	uv run python scripts/make_corrupted_batch.py
	-uv run python scripts/run_validation.py data/production/batch_corrupted.parquet

## Etapa 2: lotes com drift e relatórios do Evidently
drift:
	uv run python scripts/make_drift_batch.py --scenario data_drift --intensity 1
	uv run python scripts/make_drift_batch.py --scenario concept_drift --intensity 1
	uv run python scripts/run_drift_report.py data/production/production_base.parquet
	uv run python scripts/run_drift_report.py data/production/batch_data_drift_i100.parquet
	uv run python scripts/run_drift_report.py data/production/batch_concept_drift_i100.parquet

## Etapa 3: calibra as réguas, roda as 5 semanas no MLflow e gera o painel
monitor:
	uv run python scripts/calibrate_alerts.py
	uv run python scripts/run_weekly_pipeline.py
	uv run python scripts/plot_weekly_panel.py

## Etapa 4: viés por grupo, análise causal e retenção (em simulação)
governance:
	uv run python scripts/run_fairness.py
	uv run python scripts/run_causal_analysis.py
	uv run python scripts/apply_retention.py

## Portão do CI: contrato e hashes da evidência (depois de make drift)
evidence:
	uv run python scripts/check_evidence.py

## Roda tudo do zero, na ordem do README
pipeline: data train contract drift monitor governance evidence
	@echo "Pipeline completo. Para desfazer as regravações da evidência: make restore-evidence"

## Abre o painel do MLflow em http://localhost:5000
mlflow:
	uv run mlflow ui --backend-store-uri sqlite:///mlflow.db

## Roda os testes
test:
	uv run pytest -q

## Roda os testes com a cobertura do pacote src/
coverage:
	uv run pytest -q --cov=credit_risk_observability --cov-report=term-missing

## Confere estilo e formatação com o ruff
lint:
	uv run ruff check .
	uv run ruff format --check .

## Corrige estilo e formatação com o ruff
format:
	uv run ruff check --fix .
	uv run ruff format .

## Roda os hooks do pre-commit em todos os arquivos
precommit:
	uv run pre-commit run --all-files

## Desfaz as regravações da evidência versionada feitas por uma execução
restore-evidence:
	git restore reports
