"""AST-backed SQL governance for the read-only OpsLens analytics boundary.

Phase 3 keeps SQLGlot as the primary parser when the dependency is available, while
retaining a conservative dependency-free fallback so the deterministic local demo and
unit tests still run in restricted environments. The fallback intentionally accepts a
narrow subset of SELECT/CTE SQL and blocks anything ambiguous.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import settings

_SqlParseError: type[Exception]
try:  # pragma: no cover - exercised when sqlglot is installed in CI/dev containers
    from sqlglot import exp, parse
    from sqlglot.errors import ParseError as _ImportedSqlParseError
    _SqlParseError = _ImportedSqlParseError
except ModuleNotFoundError:  # pragma: no cover - local sandbox fallback
    exp = None  # type: ignore[assignment]
    parse = None  # type: ignore[assignment]

    class _FallbackParseError(Exception):
        pass

    _SqlParseError = _FallbackParseError

ALLOWED_SCHEMAS = {"", "public", "retail"}
ALLOWED_TABLES = {
    "sales_transactions", "returns", "inventory_records", "products", "branches", "suppliers",
    "product_categories", "purchase_orders", "purchase_order_line_items", "alerts", "data_sources",
    "metric_definitions", "forecast_runs", "anomaly_records", "data_quality_issues",
}
DANGEROUS_FUNCTIONS = {
    "pg_read_file", "pg_ls_dir", "dblink", "dblink_connect", "lo_import", "lo_export",
    "copy_program", "http_get", "http_post", "sleep", "pg_sleep", "load_extension",
}
BLOCKED_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke",
    "copy", "call", "execute", "merge", "commit", "rollback", "vacuum", "analyze", "attach",
    "detach", "pragma",
}
BLOCKED_NODE_NAMES = {
    "Insert", "Update", "Delete", "Drop", "Alter", "Create", "TruncateTable", "Truncate",
    "Grant", "Revoke", "Copy", "Command", "Transaction", "Commit", "Rollback", "Merge",
}


@dataclass
class ValidationReport:
    valid: bool
    reasons: list[str]
    tables: list[str]
    row_limit: int
    complexity_score: int
    normalized_sql: str
    limit_injected: bool = False
    parser: str = "sqlglot"


def _fallback_tables(sql: str) -> list[str]:
    tables: list[str] = []
    for match in re.finditer(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", sql, flags=re.IGNORECASE):
        raw = match.group(1).strip('"').lower()
        name = raw.split(".")[-1]
        if name and name not in {"select"}:
            tables.append(name)
    # Remove CTE aliases from the table list when the query starts with WITH.
    ctes = {m.group(1).lower() for m in re.finditer(r"\bwith\s+([a-zA-Z_][\w]*)\s+as\s*\(", sql, flags=re.IGNORECASE)}
    return [table for table in tables if table not in ctes]


def _fallback_table_aliases(sql: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    pattern = r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)\s+(?:as\s+)?([a-zA-Z_][\w]*)"
    for match in re.finditer(pattern, sql, flags=re.IGNORECASE):
        table = match.group(1).strip('"').lower().split(".")[-1]
        alias = match.group(2).lower()
        if alias not in {"where", "join", "on", "group", "order", "limit", "left", "right", "inner", "outer"}:
            pairs.append((table, alias))
    return pairs


def _fallback_validate(sql: str, *, require_tenant_scope: bool, max_rows: int) -> ValidationReport:
    source = sql.strip().rstrip(";")
    reasons: list[str] = []
    lower = re.sub(r"\s+", " ", source.lower())
    if not source:
        return ValidationReport(False, ["SQL is empty."], [], 0, 0, source, parser="fallback_ast")
    if ";" in source:
        return ValidationReport(False, ["Multiple SQL statements are blocked."], [], 0, 0, source, parser="fallback_ast")
    if not (lower.startswith("select ") or lower.startswith("with ")):
        reasons.append("Only SELECT or CTE queries are allowed.")
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lower):
            reasons.append(f"Prohibited SQL operation: {keyword.upper()}.")
    for func in DANGEROUS_FUNCTIONS:
        if re.search(rf"\b{re.escape(func)}\s*\(", lower):
            reasons.append(f"Dangerous function is blocked: {func}().")
    tables = _fallback_tables(source)
    for table in tables:
        if table not in ALLOWED_TABLES:
            reasons.append(f"Unapproved table requested: {table}.")
    if require_tenant_scope and tables and ":organization_id" not in lower and ":org_id" not in lower:
        reasons.append("Tenant scope bind parameter is required for governed execution.")
    if require_tenant_scope and tables:
        aliases = _fallback_table_aliases(source)
        scoped_names = {alias for _, alias in aliases} | set(tables)
        if len(tables) == 1 and re.search(r"\borganization_id\b", lower):
            scoped_names = set()
        for table, alias in aliases:
            if not re.search(rf"\b{re.escape(alias)}\s*\.\s*organization_id\b", lower) and not re.search(rf"\b{re.escape(table)}\s*\.\s*organization_id\b", lower):
                reasons.append(f"Tenant predicate is missing for relation alias {alias} ({table}).")
    joins = len(re.findall(r"\bjoin\b", lower))
    ctes = len(re.findall(r"\bas\s*\(", lower)) if lower.startswith("with ") else 0
    subqueries = max(0, lower.count("select") - 1)
    functions = len(re.findall(r"[a-zA-Z_][\w]*\s*\(", source))
    complexity = joins * 2 + ctes * 2 + subqueries * 3 + functions
    if complexity > settings.sql_complexity_limit:
        reasons.append(f"Query complexity {complexity} exceeds budget {settings.sql_complexity_limit}.")
    limit_match = re.search(r"\blimit\s+(\d+)", lower)
    injected = False
    limit = max_rows
    normalized = source
    if limit_match:
        limit = int(limit_match.group(1))
        if limit > max_rows:
            reasons.append(f"Row limit {limit} exceeds the {max_rows}-row policy budget.")
    elif lower.startswith("select ") or lower.startswith("with "):
        normalized = f"{source} LIMIT {max_rows}"
        injected = True
        reasons.append(f"Row limit was automatically bounded at {max_rows} rows.")
    hard_failures = [reason for reason in reasons if not reason.startswith("Row limit was automatically")]
    if not hard_failures:
        reasons.append("AST validation passed: read-only statement, approved relations, bounded result set.")
    return ValidationReport(not hard_failures, reasons, sorted(set(tables)), min(limit, max_rows), complexity, normalized, injected, "fallback_ast")


def _cte_names(tree: Any) -> set[str]:
    assert exp is not None
    return {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE) if cte.alias_or_name}


def _node_name(node: Any) -> str:
    return node.__class__.__name__


def validate_sql(sql: str, *, require_tenant_scope: bool = False, max_rows: int | None = None) -> ValidationReport:
    """Validate generated SQL before it reaches a read-only execution role."""
    reasons: list[str] = []
    max_rows = max_rows or settings.sql_row_limit
    source = sql.strip()
    if parse is None or exp is None:
        return _fallback_validate(source, require_tenant_scope=require_tenant_scope, max_rows=max_rows)
    if not source:
        return ValidationReport(False, ["SQL is empty."], [], 0, 0, "")
    try:
        statements = parse(source, read="postgres")
    except _SqlParseError as exc:
        return ValidationReport(False, [f"SQL parser rejected the statement: {str(exc).splitlines()[0]}"], [], 0, 0, source)
    if len(statements) != 1:
        return ValidationReport(False, ["Multiple SQL statements are blocked."], [], 0, 0, source)

    tree: Any = statements[0]
    if tree is None:
        return ValidationReport(False, ["SQL parser returned no statement."], [], 0, 0, source)
    normalized = tree.sql(dialect="postgres", pretty=False)
    node_names = {_node_name(node) for node in tree.walk()}
    blocked = sorted(node_names & BLOCKED_NODE_NAMES)
    if blocked:
        reasons.append(f"Prohibited SQL operation: {', '.join(blocked)}.")
    if not tree.find(exp.Select):
        reasons.append("Only SELECT or CTE queries are allowed.")

    ctes = _cte_names(tree)
    table_names: list[str] = []
    tenant_relations: list[tuple[str, str]] = []
    for table in tree.find_all(exp.Table):
        name = (table.name or "").lower()
        schema = (table.db or "").lower()
        if name in ctes:
            continue
        table_names.append(name)
        tenant_relations.append((name, (table.alias_or_name or name).lower()))
        if schema not in ALLOWED_SCHEMAS:
            reasons.append(f"Unapproved schema requested: {schema}.")
        if name not in ALLOWED_TABLES:
            reasons.append(f"Unapproved table requested: {name}.")

    for func in tree.find_all(exp.Func):
        name = (func.name or func.sql_name() or "").lower()
        if name in DANGEROUS_FUNCTIONS:
            reasons.append(f"Dangerous function is blocked: {name}().")

    joins = sum(1 for _ in tree.find_all(exp.Join))
    subqueries = sum(1 for _ in tree.find_all(exp.Subquery))
    cte_count = sum(1 for _ in tree.find_all(exp.CTE))
    aggregations = sum(1 for _ in tree.find_all(exp.AggFunc))
    complexity_score = joins * 2 + subqueries * 3 + cte_count * 2 + aggregations
    if complexity_score > settings.sql_complexity_limit:
        reasons.append(f"Query complexity {complexity_score} exceeds budget {settings.sql_complexity_limit}.")

    limit_node = tree.args.get("limit")
    injected = False
    limit = max_rows
    if limit_node is None and tree.find(exp.Select):
        tree = tree.limit(max_rows)
        normalized = tree.sql(dialect="postgres", pretty=False)
        injected = True
        reasons.append(f"Row limit was automatically bounded at {max_rows} rows.")
    else:
        expression = getattr(limit_node, "expression", None)
        try:
            limit = int(expression.this)  # type: ignore[union-attr]
        except (ValueError, TypeError, AttributeError):
            reasons.append("LIMIT must be a numeric literal.")
            limit = max_rows
        if limit > max_rows:
            reasons.append(f"Row limit {limit} exceeds the {max_rows}-row policy budget.")

    if require_tenant_scope and table_names:
        compact = re.sub(r"\s+", " ", normalized.lower())
        raw_compact = re.sub(r"\s+", " ", source.lower())
        tenant_bind = (":organization_id" in raw_compact or ":org_id" in raw_compact or "%(organization_id)s" in compact or "%(org_id)s" in compact)
        if not tenant_bind:
            reasons.append("Tenant scope bind parameter is required for governed execution.")
        elif len(tenant_relations) > 1:
            for table, relation in tenant_relations:
                if not re.search(rf"\b{re.escape(relation)}\s*\.\s*organization_id\b", compact) and not re.search(rf"\b{re.escape(table)}\s*\.\s*organization_id\b", compact):
                    reasons.append(f"Tenant predicate is missing for relation alias {relation} ({table}).")

    hard_failures = [r for r in reasons if not r.startswith("Row limit was automatically")]
    if not hard_failures:
        reasons.append("AST validation passed: read-only statement, approved relations, bounded result set.")
    return ValidationReport(not hard_failures, reasons, sorted(set(table_names)), min(limit, max_rows), complexity_score, normalized, injected)
