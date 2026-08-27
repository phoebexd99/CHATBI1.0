from __future__ import annotations

import getpass
from pathlib import Path
from urllib.parse import quote

import psycopg


ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"


def main() -> None:
    if ENV_PATH.exists():
        raise SystemExit(f"{ENV_PATH} already exists; edit it manually instead of overwriting it.")
    username = input("PostgreSQL username [user_AhHijf]: ").strip() or "user_AhHijf"
    database = input("PostgreSQL database [postgres]: ").strip() or "postgres"
    password = getpass.getpass("PostgreSQL password (hidden): ")
    connection = psycopg.connect(
        host="127.0.0.1",
        port=15432,
        dbname=database,
        user=username,
        password=password,
        connect_timeout=8,
    )
    try:
        current_user, current_database = connection.execute(
            "select current_user, current_database()"
        ).fetchone()
    finally:
        connection.close()
    database_url = (
        f"postgresql://{quote(username, safe='')}:{quote(password, safe='')}"
        f"@127.0.0.1:15432/{quote(database, safe='')}"
    )
    ENV_PATH.write_text(
        "# Local-only CHATBI configuration. This file is gitignored.\n"
        f"DATABASE_URL={database_url}\n"
        "NEXT_PUBLIC_DEMO_MODE=live\n"
        "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000\n",
        encoding="utf-8",
    )
    print(f"Connected as {current_user} to {current_database}; wrote local .env safely.")


if __name__ == "__main__":
    main()