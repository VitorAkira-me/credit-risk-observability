"""Caminhos e constantes do projeto, num lugar só."""

from pathlib import Path

# src/credit_risk_observability/config.py -> parents[2] é a raiz do repositório
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_PATH = DATA_DIR / "raw" / "credit_default.parquet"
REFERENCE_PATH = DATA_DIR / "reference" / "reference.parquet"
PRODUCTION_BASE_PATH = DATA_DIR / "production" / "production_base.parquet"
SPLIT_METADATA_PATH = DATA_DIR / "split_metadata.json"

REPORTS_DIR = PROJECT_ROOT / "reports"
EDA_REPORT_PATH = REPORTS_DIR / "eda" / "eda_summary.md"

MODELS_DIR = PROJECT_ROOT / "models"

UCI_DATASET_ID = 350  # Default of Credit Card Clients (Taiwan)
SEED = 42
PRODUCTION_SIZE = 0.30

ID_COLUMN = "ID"
TARGET = "default"

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

# Códigos documentados pelo UCI. Valores fora daqui aparecem nos dados reais e
# são investigados na EDA (insumo para o contrato de dados do DQ-001).
DOCUMENTED_CODES = {
    "SEX": {1, 2},
    "EDUCATION": {1, 2, 3, 4},
    "MARRIAGE": {1, 2, 3},
    **{col: {-1, *range(1, 10)} for col in PAY_STATUS_COLUMNS},
}
