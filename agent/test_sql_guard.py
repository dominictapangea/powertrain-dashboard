import pytest

from sql_guard import MAX_ROWS, SqlGuardError, validate_sql

PROJECT, DATASET = "my-project", "my_dataset"


def check(sql):
    return validate_sql(sql, project=PROJECT, dataset=DATASET)


# --- queries that must pass -------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT powertrain_type, AVG(co2_emissions_g_km) FROM analytics GROUP BY powertrain_type",
        "SELECT * FROM `my-project.my_dataset.analytics`",
        "SELECT * FROM my_dataset.analytics",
        "select count(*) from analytics",
        "SELECT 1 AS one FROM analytics;",
        "WITH t AS (SELECT * FROM analytics WHERE model_year = 2024) SELECT COUNT(*) FROM t",
        "SELECT manufacturer FROM analytics UNION ALL SELECT manufacturer FROM analytics",
        "SELECT * FROM analytics WHERE manufacturer IN (SELECT manufacturer FROM analytics)",
        "SELECT /* a comment */ model FROM analytics -- trailing comment",
    ],
)
def test_valid_select_passes(sql):
    result = check(sql)
    assert result.upper().startswith(("SELECT", "WITH"))
    assert "LIMIT" in result.upper()


# --- LIMIT handling ---------------------------------------------------------

def test_limit_is_added_when_missing():
    assert check("SELECT * FROM analytics").endswith(f"LIMIT {MAX_ROWS}")


def test_small_limit_is_kept():
    assert check("SELECT * FROM analytics LIMIT 5").endswith("LIMIT 5")


def test_large_limit_is_capped():
    assert check("SELECT * FROM analytics LIMIT 100000").endswith(f"LIMIT {MAX_ROWS}")


def test_limit_is_added_to_union_and_cte():
    assert check("SELECT a FROM analytics UNION ALL SELECT a FROM analytics").endswith(f"LIMIT {MAX_ROWS}")
    assert check("WITH c AS (SELECT * FROM analytics) SELECT * FROM c").endswith(f"LIMIT {MAX_ROWS}")


# --- statements that must be rejected --------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE analytics",
        "DELETE FROM analytics WHERE TRUE",
        "INSERT INTO analytics (model) VALUES ('x')",
        "UPDATE analytics SET model = 'x' WHERE TRUE",
        "CREATE TABLE copy AS SELECT * FROM analytics",
        "TRUNCATE TABLE analytics",
        "ALTER TABLE analytics ADD COLUMN x STRING",
        "MERGE analytics a USING analytics b ON a.model = b.model WHEN MATCHED THEN DELETE",
        'EXPORT DATA OPTIONS(uri="gs://bucket/x") AS SELECT * FROM analytics',
    ],
)
def test_non_select_statements_are_rejected(sql):
    with pytest.raises(SqlGuardError):
        check(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 FROM analytics; SELECT 2 FROM analytics",
        "SELECT * FROM analytics; DROP TABLE analytics",
        "SELECT * FROM analytics;\nDELETE FROM analytics WHERE TRUE",
        "SELECT * FROM analytics; -- harmless\nDROP TABLE analytics",
    ],
)
def test_multiple_statements_are_rejected(sql):
    with pytest.raises(SqlGuardError, match="single"):
        check(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM other_table",
        "SELECT * FROM my_dataset.other_table",
        "SELECT * FROM `other-project.my_dataset.analytics`",
        "SELECT * FROM my_dataset.INFORMATION_SCHEMA.TABLES",
        "SELECT * FROM analytics, `x.y.z`",
        "SELECT * FROM analytics WHERE model IN (SELECT model FROM secret.t)",
        "SELECT a FROM analytics UNION ALL SELECT a FROM other_table",
        'SELECT * FROM EXTERNAL_QUERY("conn", "SELECT 1")',
        "SELECT 1",
    ],
)
def test_other_tables_are_rejected(sql):
    with pytest.raises(SqlGuardError):
        check(sql)


@pytest.mark.parametrize("sql", ["", "   ", "\n;\n", "SELEC * FRM analytics", "not sql at all"])
def test_empty_or_invalid_sql_is_rejected(sql):
    with pytest.raises(SqlGuardError):
        check(sql)


def test_qualified_table_is_rejected_without_configured_project():
    with pytest.raises(SqlGuardError):
        validate_sql("SELECT * FROM `my-project.my_dataset.analytics`")
