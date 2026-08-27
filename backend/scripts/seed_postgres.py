from __future__ import annotations

from pathlib import Path

import psycopg

from backend.app.config import settings


ROOT = Path(__file__).resolve().parents[2]


def statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]


def main() -> None:
    schema_sql = (ROOT / "data" / "postgres" / "001_schema.sql").read_text(encoding="utf-8")
    schema_sql = schema_sql.replace("CREATE EXTENSION IF NOT EXISTS vector;", "")
    seed_sql = (ROOT / "data" / "postgres" / "002_seed.sql").read_text(encoding="utf-8")
    with psycopg.connect(settings.database_url) as connection:
        for statement in statements(schema_sql):
            connection.execute(statement)
        for statement in statements(seed_sql):
            connection.execute(statement)
    print("Initialized CHATBI PostgreSQL tables and synthetic seed data (pgvector extension skipped).")


if __name__ == "__main__":
    main()