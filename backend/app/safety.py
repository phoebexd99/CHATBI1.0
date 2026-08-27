from __future__ import annotations

import re
import sqlglot
from sqlglot import exp


class UnsafeSQL(ValueError):
    pass


class SQLSafetyGate:
    ALLOWED_TABLES = {"orders", "customers", "products", "order_items"}
    FORBIDDEN_FUNCTIONS = {"pg_read_file", "pg_ls_dir", "dblink", "lo_import", "lo_export"}

    def validate(self, sql: str, dialect: str) -> str:
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
        tables = {table.name.lower() for table in statement.find_all(exp.Table)}
        unknown = tables - self.ALLOWED_TABLES
        if unknown:
            raise UnsafeSQL(f"Table not allow-listed: {', '.join(sorted(unknown))}")
        functions = {function.sql_name().lower() for function in statement.find_all(exp.Func)}
        if functions & self.FORBIDDEN_FUNCTIONS:
            raise UnsafeSQL("Dangerous function is forbidden")
        rendered = statement.sql(dialect=dialect)
        if re.search(r"\b(information_schema|pg_catalog)\b", rendered, re.IGNORECASE):
            raise UnsafeSQL("System catalogs are forbidden")
        return rendered

