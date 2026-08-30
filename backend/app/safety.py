from __future__ import annotations

import re
import sqlglot
from sqlglot import exp


class UnsafeSQL(ValueError):
    pass


class SQLSafetyGate:
    ALLOWED_TABLES = {
        "orders", "customers", "products", "order_items", "campaign_daily", "inventory_snapshots",
        "fct_order", "fct_order_item", "fct_marketing_lead", "fct_payment", "fct_review",
        "fct_inventory_snapshot", "dim_customer", "dim_product", "dim_seller",
    }
    ALLOWED_SCHEMAS = {"public", "chatbi_mart"}
    FORBIDDEN_FUNCTIONS = {"pg_read_file", "pg_ls_dir", "dblink", "lo_import", "lo_export"}

    def validate(
        self,
        sql: str,
        dialect: str,
        allowed_tables: set[str] | None = None,
        allowed_schemas: set[str] | None = None,
    ) -> str:
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise UnsafeSQL("SQL comments are not allowed")
        try:
            statements = sqlglot.parse(sql, read=dialect)
        except sqlglot.errors.ParseError as error:
            raise UnsafeSQL(f"SQL parse failed: {error}") from error
        if len(statements) != 1:
            raise UnsafeSQL("Exactly one SQL statement is required")
        statement = statements[0]
        if not isinstance(statement, exp.Select):
            raise UnsafeSQL("Only SELECT statements are allowed")
        forbidden_nodes = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Command)
        if any(statement.find(node) for node in forbidden_nodes):
            raise UnsafeSQL("DDL, DML, and commands are forbidden")
        table_nodes = list(statement.find_all(exp.Table))
        tables = {table.name.lower() for table in table_nodes}
        effective_tables = self.ALLOWED_TABLES if allowed_tables is None else {item.lower() for item in allowed_tables}
        effective_schemas = self.ALLOWED_SCHEMAS if allowed_schemas is None else {item.lower() for item in allowed_schemas}
        unknown = tables - effective_tables
        if unknown:
            raise UnsafeSQL(f"Table not allow-listed: {', '.join(sorted(unknown))}")
        unknown_schemas = {
            table.db.lower() for table in table_nodes if table.db and table.db.lower() not in effective_schemas
        }
        if unknown_schemas:
            raise UnsafeSQL(f"Schema not allow-listed: {', '.join(sorted(unknown_schemas))}")
        functions = {function.sql_name().lower() for function in statement.find_all(exp.Func)}
        if functions & self.FORBIDDEN_FUNCTIONS:
            raise UnsafeSQL("Dangerous function is forbidden")
        rendered = statement.sql(dialect=dialect)
        if re.search(r"\b(information_schema|pg_catalog)\b", rendered, re.IGNORECASE):
            raise UnsafeSQL("System catalogs are forbidden")
        return rendered

