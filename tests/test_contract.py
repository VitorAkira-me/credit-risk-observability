import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import FEATURE_COLUMNS, ID_COLUMN, TARGET
from credit_risk_observability.contracts.validate import validate_batch


@pytest.fixture
def clean_batch() -> pd.DataFrame:
    """Lote válido pequeno, incluindo códigos legados que o contrato aceita."""
    n = 6
    df = pd.DataFrame({ID_COLUMN: np.arange(1, n + 1)})
    for col in FEATURE_COLUMNS:
        df[col] = 0
    df["LIMIT_BAL"] = 50_000
    df["SEX"] = [1, 2, 1, 2, 1, 2]
    df["EDUCATION"] = [1, 2, 3, 0, 5, 6]
    df["MARRIAGE"] = [1, 2, 3, 0, 1, 2]
    df["AGE"] = [18, 25, 40, 60, 79, 100]
    df["PAY_0"] = [-2, -1, 0, 1, 8, 9]
    df["BILL_AMT1"] = [-500, 0, 1_000, 2_000, 3_000, 4_000]
    df[TARGET] = [0, 1, 0, 0, 1, 0]
    return df


def assert_blocked_by(df: pd.DataFrame, rule: str, count: int = 1) -> None:
    result = validate_batch(df)
    assert not result.passed
    assert result.failures_by_rule.get(rule) == count, result.failures_by_rule


def test_clean_batch_passes(clean_batch):
    result = validate_batch(clean_batch)

    assert result.passed, result.failures_by_rule
    assert result.rows == 6


def test_batch_without_target_passes(clean_batch):
    assert validate_batch(clean_batch.drop(columns=TARGET)).passed


def test_underage_is_blocked(clean_batch):
    clean_batch.loc[0, "AGE"] = 17

    assert_blocked_by(clean_batch, "AGE:in_range(18, 100)")


def test_non_positive_limit_is_blocked(clean_batch):
    clean_batch.loc[[0, 1], "LIMIT_BAL"] = [0, -10]

    assert_blocked_by(clean_batch, "LIMIT_BAL:greater_than(0)", count=2)


def test_null_limit_is_blocked(clean_batch):
    clean_batch["LIMIT_BAL"] = clean_batch["LIMIT_BAL"].astype(float)
    clean_batch.loc[0, "LIMIT_BAL"] = np.nan

    result = validate_batch(clean_batch)

    assert not result.passed
    assert result.failures_by_rule["LIMIT_BAL:not_nullable"] == 1
    assert "LIMIT_BAL:dtype('int64')" in result.failures_by_rule


def test_duplicated_id_is_blocked(clean_batch):
    clean_batch.loc[1, ID_COLUMN] = clean_batch.loc[0, ID_COLUMN]

    assert_blocked_by(clean_batch, "ID:field_uniqueness", count=2)


def test_unknown_sex_code_is_blocked(clean_batch):
    clean_batch.loc[0, "SEX"] = 3

    assert_blocked_by(clean_batch, "SEX:isin([1, 2])")


def test_pay_status_out_of_domain_is_blocked(clean_batch):
    clean_batch.loc[0, "PAY_0"] = 10

    assert_blocked_by(clean_batch, "PAY_0:isin([-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9])")


def test_negative_payment_is_blocked(clean_batch):
    clean_batch.loc[0, "PAY_AMT1"] = -1

    assert_blocked_by(clean_batch, "PAY_AMT1:greater_than_or_equal_to(0)")


def test_non_binary_target_is_blocked(clean_batch):
    clean_batch.loc[0, TARGET] = 2

    assert_blocked_by(clean_batch, "default:isin([0, 1])")


def test_unexpected_column_is_blocked(clean_batch):
    clean_batch["CPF"] = "000.000.000-00"

    assert_blocked_by(clean_batch, "<lote>:column_in_schema")


def test_missing_column_is_blocked(clean_batch):
    assert_blocked_by(clean_batch.drop(columns="AGE"), "<lote>:column_in_dataframe")


def test_empty_batch_is_blocked(clean_batch):
    assert_blocked_by(clean_batch.iloc[0:0], "<lote>:lote_nao_vazio")


def test_all_errors_are_reported_at_once(clean_batch):
    clean_batch.loc[0, "AGE"] = 15
    clean_batch.loc[1, "LIMIT_BAL"] = 0
    clean_batch.loc[2, "SEX"] = 9

    assert len(validate_batch(clean_batch).failures_by_rule) == 3
