import numpy as np
import pandas as pd
import pytest

from credit_risk_observability.config import FEATURE_COLUMNS, ID_COLUMN, TARGET
from credit_risk_observability.data.download import standardize_columns
from credit_risk_observability.data.eda import undocumented_codes
from credit_risk_observability.data.split import split_reference_production


@pytest.fixture
def fake_raw() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 1_000
    df = pd.DataFrame({ID_COLUMN: np.arange(1, n + 1)})
    for col in FEATURE_COLUMNS:
        df[col] = rng.integers(1, 3, n)
    df[TARGET] = (rng.random(n) < 0.22).astype(int)
    return df


def test_split_sizes_and_no_shared_ids(fake_raw):
    ref, prod = split_reference_production(fake_raw, production_size=0.3, seed=42)

    assert len(ref) == 700
    assert len(prod) == 300
    assert set(ref[ID_COLUMN]).isdisjoint(prod[ID_COLUMN])


def test_split_preserves_default_rate(fake_raw):
    ref, prod = split_reference_production(fake_raw, production_size=0.3, seed=42)

    assert abs(ref[TARGET].mean() - prod[TARGET].mean()) < 0.01


def test_split_is_deterministic(fake_raw):
    ref_a, _ = split_reference_production(fake_raw, production_size=0.3, seed=42)
    ref_b, _ = split_reference_production(fake_raw, production_size=0.3, seed=42)
    ref_c, _ = split_reference_production(fake_raw, production_size=0.3, seed=7)

    assert ref_a[ID_COLUMN].tolist() == ref_b[ID_COLUMN].tolist()
    assert ref_a[ID_COLUMN].tolist() != ref_c[ID_COLUMN].tolist()


def test_split_rejects_duplicated_ids(fake_raw):
    fake_raw.loc[1, ID_COLUMN] = fake_raw.loc[0, ID_COLUMN]

    with pytest.raises(ValueError, match="duplicados"):
        split_reference_production(fake_raw, production_size=0.3, seed=42)


def test_standardize_columns_renames_uci_names():
    names = [f"X{i}" for i in range(1, 24)]
    variables = pd.DataFrame(
        {
            "name": ["ID", *names, "Y"],
            "role": ["ID", *["Feature"] * 23, "Target"],
            "description": [None, *FEATURE_COLUMNS, "default payment next month"],
        }
    )
    features = pd.DataFrame([list(range(23))], columns=names)

    df = standardize_columns(
        features, pd.DataFrame({"Y": [1]}), pd.DataFrame({"ID": [10]}), variables
    )

    assert list(df.columns) == [ID_COLUMN, *FEATURE_COLUMNS, TARGET]
    assert df.loc[0, TARGET] == 1


def test_undocumented_codes_flags_education_zero(fake_raw):
    fake_raw.loc[:4, "EDUCATION"] = 0

    assert undocumented_codes(fake_raw)["EDUCATION"] == {0: 5}
