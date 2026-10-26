"""
SQL guard for the analytics agent.

Everything the model writes goes through validate_sql() before it reaches
BigQuery. It accepts exactly one read-only SELECT (optionally with CTEs or
UNIONs) that only touches the `analytics` table, and forces a LIMIT.

The SQL is parsed with sqlglot (BigQuery dialect) instead of matched with
regexes, so comments, odd spacing and stacked statements can't slip through.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ALLOWED_TABLE = "analytics"
MAX_ROWS = 100

# Nodes that must never appear anywhere in the query, even nested.
_FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Into,
)


class SqlGuardError(ValueError):
    """Raised when a query is not allowed to run. The message is shown to the model."""


def validate_sql(
    sql: str,
    project: str | None = None,
    dataset: str | None = None,
    table: str = ALLOWED_TABLE,
    max_rows: int = MAX_ROWS,
) -> str:
    """Return a safe version of `sql` (single SELECT, LIMIT <= max_rows) or raise SqlGuardError.

    `project` and `dataset` are the only qualifiers accepted in front of the
    table name. A bare `analytics` is always accepted (the agent runs queries
    with the dataset as default).
    """
    if not sql or not sql.strip():
        raise SqlGuardError("The query is empty.")

    try:
        parsed = sqlglot.parse(sql, read="bigquery")
    except SqlglotError as e:
        raise SqlGuardError(f"Could not parse the SQL: {_first_line(e)}") from e

    statements = [s for s in parsed if s is not None]
    if len(statements) != 1:
        raise SqlGuardError("Only a single SQL statement is allowed.")
    stmt = statements[0]

    if not isinstance(stmt, (exp.Select, exp.SetOperation)):
        raise SqlGuardError(
            f"Only SELECT queries are allowed (got {type(stmt).__name__.upper()})."
        )

    bad = next(stmt.find_all(*_FORBIDDEN_NODES), None)
    if bad is not None:
        raise SqlGuardError(f"{type(bad).__name__.upper()} is not allowed in a query.")

    _check_tables(stmt, project, dataset, table)

    return _force_limit(stmt, max_rows).sql(dialect="bigquery", comments=False)


def _check_tables(stmt: exp.Expression, project, dataset, table: str) -> None:
    cte_names = {cte.alias_or_name for cte in stmt.find_all(exp.CTE)}
    uses_allowed_table = False

    for t in stmt.find_all(exp.Table):
        is_bare = not t.db and not t.catalog

        if is_bare and t.name in cte_names:
            continue  # reference to a CTE defined in the same query

        if t.name != table:
            shown = ".".join(p for p in (t.catalog, t.db, t.name) if p) or "a table function"
            raise SqlGuardError(f"Only the `{table}` table can be queried, not {shown}.")

        if t.catalog and t.catalog != project or t.db and t.db != dataset:
            raise SqlGuardError(f"Only the `{table}` table of the configured dataset can be queried.")

        uses_allowed_table = True

    if not uses_allowed_table:
        raise SqlGuardError(f"The query must read from the `{table}` table.")


def _force_limit(stmt: exp.Expression, max_rows: int) -> exp.Expression:
    limit = stmt.args.get("limit")
    if limit is not None:
        value = limit.expression
        if isinstance(value, exp.Literal) and not value.is_string:
            try:
                if int(value.name) <= max_rows:
                    return stmt
            except ValueError:
                pass
    return stmt.limit(max_rows, copy=False)


def _first_line(error: Exception) -> str:
    return str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
