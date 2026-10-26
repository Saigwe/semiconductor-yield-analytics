"""SQL guardrail for the NL-to-SQL agent, built on DuckDB's own parser instead of regular expressions.

A query passes only when:
  - it parses as exactly one SELECT statement (json_serialize_sql serialises SELECTs only: DDL/DML is rejected);
  - every table it reads, at any depth (joins, comma joins, subqueries, CTE bodies, set operations), is an approved
    gold model or a CTE defined in the same query;
  - it calls no table function (read_csv, read_parquet, glob, query, ...) and no blocked scalar function
    (getenv, current_setting, read_text, read_blob, ...).
Execution then runs on a read-only connection with external access disabled, and returns at most MAX_ROWS rows.

legacy_regex_guardrail is the scaffold's original check, kept only so results/guardrail.md can compare the two.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import yaml

HERE = Path(__file__).parent
MAX_ROWS = 1000
BLOCKED_FUNCTIONS = {"getenv", "current_setting", "read_text", "read_blob", "read_csv", "read_csv_auto",
                     "read_parquet", "read_json", "read_json_auto", "glob", "query", "query_table", "sniff_csv",
                     "duckdb_secrets", "duckdb_settings", "which_secret"}


class GuardrailError(ValueError):
    pass


def allowed_models() -> set[str]:
    return {m.lower() for m in yaml.safe_load((HERE / "allowed_models.yml").read_text())["allowed_models"]}


def _walk(node, tables: list[tuple[str, str]], ctes: set[str], functions: list[str], table_functions: list[str]):
    if isinstance(node, dict):
        if node.get("type") == "BASE_TABLE":
            tables.append(((node.get("schema_name") or "").lower(), (node.get("table_name") or "").lower()))
        if node.get("type") == "TABLE_FUNCTION":
            table_functions.append(json.dumps(node.get("function", {}).get("function_name", "?")))
        if node.get("class") == "FUNCTION" and "function_name" in node:
            functions.append(node["function_name"].lower())
        cte_map = node.get("cte_map")
        if isinstance(cte_map, dict):
            ctes.update(entry["key"].lower() for entry in cte_map.get("map", []))
        for value in node.values():
            _walk(value, tables, ctes, functions, table_functions)
    elif isinstance(node, list):
        for value in node:
            _walk(value, tables, ctes, functions, table_functions)


def check(sql: str, allowed: set[str] | None = None) -> None:
    """Raise GuardrailError with a readable reason, so an agent can correct itself."""
    allowed = allowed if allowed is not None else allowed_models()
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as exc:
        raise GuardrailError(f"could not parse SQL: {exc}") from None
    if len(statements) != 1:
        raise GuardrailError("exactly one SQL statement is allowed")
    tree = json.loads(duckdb.execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    if tree.get("error"):
        raise GuardrailError(f"only a single SELECT is allowed ({tree.get('error_message', 'not a SELECT')})")
    tables, ctes, functions, table_functions = [], set(), [], []
    _walk(tree["statements"], tables, ctes, functions, table_functions)
    if table_functions:
        raise GuardrailError(f"table functions are not allowed: {', '.join(sorted(set(table_functions)))}")
    blocked = sorted(set(functions) & BLOCKED_FUNCTIONS)
    if blocked:
        raise GuardrailError(f"functions not allowed: {blocked}")
    illegal = sorted({f"{s}.{t}" if s else t for s, t in tables if not (f"{s}.{t}" in allowed or (not s and t in ctes))})
    if illegal:
        raise GuardrailError(f"only approved gold models may be read; not allowed: {illegal}")


def connect(db: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(db, read_only=True, config={"enable_external_access": False})


def run(con: duckdb.DuckDBPyConnection, sql: str, allowed: set[str] | None = None) -> list[tuple]:
    check(sql, allowed)
    return con.execute(sql).fetchmany(MAX_ROWS)


TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", re.IGNORECASE)


def legacy_regex_guardrail(sql: str, allowed: set[str]) -> None:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped or not re.match(r"^\s*(with|select)\b", stripped, re.IGNORECASE):
        raise GuardrailError("only a single SELECT statement is allowed")
    used = {t.lower() for t in TABLE_REF.findall(stripped)}
    ctes = {m.lower() for m in re.findall(r"\b(\w+)\s+as\s*\(", stripped, re.IGNORECASE)}
    illegal = used - allowed - ctes
    if illegal:
        raise GuardrailError(f"tables not allowed: {sorted(illegal)}")
