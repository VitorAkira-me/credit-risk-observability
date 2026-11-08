"""Caminhos e constantes do projeto, num lugar só.

O que faz: define onde cada arquivo fica e os números e nomes de colunas usados no pipeline.
Por que existe: se um caminho ou uma coluna mudar, o ajuste é feito só aqui.
Onde entra no fluxo: não executa nada sozinho; os módulos e scripts importam daqui.
"""

from pathlib import Path

# src/credit_risk_observability/config.py -> parents[2] é a raiz do repositório
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Dados: a pasta data/ fica fora do git, porque os arquivos são pesados e têm atributos pessoais.
# Referência: os dados de treino. Produção: os dados "do futuro", onde o drift é simulado.
# Parquet: formato de arquivo para tabelas, que guarda o tipo de cada coluna.
DATA_DIR = PROJECT_ROOT / "data"
RAW_PATH = DATA_DIR / "raw" / "credit_default.parquet"
REFERENCE_PATH = DATA_DIR / "reference" / "reference.parquet"
PRODUCTION_DIR = DATA_DIR / "production"
PRODUCTION_BASE_PATH = DATA_DIR / "production" / "production_base.parquet"
SPLIT_METADATA_PATH = DATA_DIR / "split_metadata.json"
CORRUPTED_BATCH_PATH = DATA_DIR / "production" / "batch_corrupted.parquet"
CORRUPTED_EXPECTED_PATH = DATA_DIR / "production" / "batch_corrupted_expected.json"

# Relatórios: a evidência da entrega, versionada no git.
REPORTS_DIR = PROJECT_ROOT / "reports"
EDA_REPORT_PATH = REPORTS_DIR / "eda" / "eda_summary.md"
VALIDATION_REPORTS_DIR = REPORTS_DIR / "validation"
DRIFT_REPORTS_DIR = REPORTS_DIR / "drift"

# Saídas de execuções do pipeline: ficam fora do git (cada HTML do Evidently tem cerca de 6 MB e muda
# a cada geração). Só os relatórios de reports/drift/ são evidência versionada (REPASSE, decisão 19).
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DRIFT_RUNS_DIR = OUTPUTS_DIR / "drift"
# ADR-005: o detalhe das falhas (com os valores barrados) fica só local, fora do git.
VALIDATION_DETAIL_DIR = OUTPUTS_DIR / "validation"

# OBS-002: monitoramento semanal. Os limites calibrados são evidência (versionados); o banco do
# MLflow e os artefatos de cada semana são regeráveis e ficam fora do git.
MONITORING_REPORTS_DIR = REPORTS_DIR / "monitoring"
ALERT_THRESHOLDS_PATH = MONITORING_REPORTS_DIR / "alert_thresholds.json"
WEEKLY_RUNS_DIR = OUTPUTS_DIR / "weekly"
WEEKLY_BATCH_SIZE = 2_000  # 4 semanas disjuntas cabem nos 9.000 clientes da Produção-base
MLFLOW_DB_PATH = PROJECT_ROOT / "mlflow.db"
MLFLOW_TRACKING_URI = f"sqlite:///{MLFLOW_DB_PATH.as_posix()}"
MLFLOW_ARTIFACTS_DIR = PROJECT_ROOT / "mlartifacts"
MLFLOW_EXPERIMENT = "credit-risk-monitoramento"

MODELS_DIR = PROJECT_ROOT / "models"

UCI_DATASET_ID = 350  # Default of Credit Card Clients (Taiwan)
# Seed: número que fixa os sorteios. Com ela, cada execução sorteia exatamente a mesma coisa.
SEED = 42
PRODUCTION_SIZE = 0.30  # 30% dos clientes vão para a Produção: 9.000 de 30.000

ID_COLUMN = "ID"
# Alvo (y): o que o modelo tenta prever. 1 se o cliente deu default (calote) no mês seguinte.
TARGET = "default"

# Grupos de colunas. Feature é uma coluna de entrada do modelo (o X).
# PAY_*: situação do pagamento em cada mês. BILL_AMT*: valor da fatura. PAY_AMT*: valor pago.
PAY_STATUS_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLUMNS = [f"BILL_AMT{i}" for i in range(1, 7)]
PAY_AMOUNT_COLUMNS = [f"PAY_AMT{i}" for i in range(1, 7)]
CATEGORICAL_COLUMNS = ["SEX", "EDUCATION", "MARRIAGE"]
FEATURE_COLUMNS = [
    "LIMIT_BAL",
    *CATEGORICAL_COLUMNS,
    "AGE",
    *PAY_STATUS_COLUMNS,
    *BILL_COLUMNS,
    *PAY_AMOUNT_COLUMNS,
]

# ADR-004: atributos sensíveis ficam nos dados (para auditar viés), mas fora do modelo.
SENSITIVE_EXCLUDED = ["SEX", "MARRIAGE"]
MODEL_FEATURES = [c for c in FEATURE_COLUMNS if c not in SENSITIVE_EXCLUDED]
MODEL_CATEGORICAL = [c for c in CATEGORICAL_COLUMNS if c not in SENSITIVE_EXCLUDED]
MODEL_NUMERIC = [c for c in MODEL_FEATURES if c not in MODEL_CATEGORICAL]

VALIDATION_SIZE = 0.20  # 20% da Referência ficam fora do treino, para medir o modelo
# Probabilidade a partir da qual o modelo classifica o cliente como default.
DECISION_THRESHOLD = 0.5
MODEL_PATH = MODELS_DIR / "baseline_logreg.joblib"
METRICS_PATH = MODELS_DIR / "baseline_metrics.json"

# Códigos documentados pelo UCI. Valores fora daqui aparecem nos dados reais e
# são investigados na EDA (insumo para o contrato de dados do DQ-001).
DOCUMENTED_CODES = {
    "SEX": {1, 2},
    "EDUCATION": {1, 2, 3, 4},
    "MARRIAGE": {1, 2, 3},
    **{col: {-1, *range(1, 10)} for col in PAY_STATUS_COLUMNS},
}
