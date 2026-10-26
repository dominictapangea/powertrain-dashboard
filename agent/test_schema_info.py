from pathlib import Path

import pandas as pd
import pytest

import schema_info

CSV = Path(__file__).resolve().parent.parent / "cleaned_horse_powertrain_data_v2.csv"


@pytest.fixture(scope="module")
def data():
    if not CSV.exists():
        pytest.skip("cleaned CSV not found")
    return pd.read_csv(CSV)


def test_powertrain_types_match_csv(data):
    assert sorted(data["powertrain_type"].unique()) == sorted(schema_info.POWERTRAIN_TYPES)


def test_efficiency_tiers_match_csv(data):
    assert sorted(data["efficiency_tier"].unique()) == sorted(schema_info.EFFICIENCY_TIERS)


def test_fuel_type_codes_and_years_match_csv(data):
    assert sorted(data["fuel_type_code"].unique()) == sorted(schema_info.FUEL_TYPE_CODES)
    assert sorted(data["model_year"].unique()) == sorted(schema_info.MODEL_YEARS)


def test_every_csv_column_is_described(data):
    assert set(data.columns) == set(schema_info.COLUMN_NOTES)


def test_schema_prompt_mentions_columns_and_values():
    fields = [("powertrain_type", "STRING", "NULLABLE"), ("model_year", "INTEGER", "NULLABLE")]
    text = schema_info.build_schema_prompt(fields)
    assert "powertrain_type (STRING, nullable)" in text
    assert "'Battery Electric (BEV)'" in text
    assert "'A - Best in Class'" in text
