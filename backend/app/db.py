from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator


class Database:
    """Small read-oriented DB boundary supporting PostgreSQL and a Day-1 SQLite fallback."""

    def __init__(self, url: str):
        self.url = url
        self.is_postgres = url.startswith("postgresql://") or url.startswith("postgres://")

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(self.url, row_factory=dict_row) as connection:
                yield connection
            return

        path = self.url.removeprefix("sqlite:///")
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def ping(self) -> bool:
        with self.connect() as connection:
            connection.execute("SELECT 1")
        return True

    def explain(self, sql: str) -> None:
        prefix = "EXPLAIN " if self.is_postgres else "EXPLAIN QUERY PLAN "
        with self.connect() as connection:
            connection.execute(prefix + sql)

    def query(self, sql: str, max_rows: int = 500) -> tuple[list[str], list[list[Any]]]:
        with self.connect() as connection:
            cursor = connection.execute(sql)
            columns = [item.name if hasattr(item, "name") else item[0] for item in cursor.description]
            raw_rows = cursor.fetchmany(max_rows)
        if self.is_postgres:
            rows = [[self._json_value(row[column]) for column in columns] for row in raw_rows]
        else:
            rows = [[self._json_value(value) for value in row] for row in raw_rows]
        return columns, rows

    def distinct_values(self, qualified_column: str, limit: int = 100) -> list[str]:
        """Discover low-cardinality filter values from an allow-listed catalog column."""
        if not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", qualified_column):
            raise ValueError("Invalid catalog column")
        table, column = qualified_column.split(".", 1)
        bounded_limit = min(max(limit, 1), 200)
        sql = f"SELECT DISTINCT {column} AS value FROM {table} WHERE {column} IS NOT NULL LIMIT {bounded_limit}"
        _, rows = self.query(sql, max_rows=bounded_limit)
        return [str(row[0]) for row in rows]

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date,)):
            return value.isoformat()
        return value


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  customer_id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL,
  region TEXT NOT NULL, signup_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL,
  category TEXT NOT NULL, unit_price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL,
  order_date TEXT NOT NULL, status TEXT NOT NULL, channel TEXT NOT NULL,
  region TEXT NOT NULL, gross_amount REAL NOT NULL,
  discount_amount REAL NOT NULL DEFAULT 0, refund_amount REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS order_items (
  order_item_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL, quantity INTEGER NOT NULL,
  item_gross_amount REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_daily (
  metric_date TEXT NOT NULL, campaign_name TEXT NOT NULL, channel TEXT NOT NULL,
  impressions INTEGER NOT NULL, clicks INTEGER NOT NULL, sessions INTEGER NOT NULL,
  attributed_orders INTEGER NOT NULL, attributed_revenue REAL NOT NULL, spend REAL NOT NULL,
  PRIMARY KEY(metric_date, campaign_name)
);
CREATE TABLE IF NOT EXISTS inventory_snapshots (
  snapshot_date TEXT NOT NULL, product_id INTEGER NOT NULL, available_qty INTEGER NOT NULL,
  PRIMARY KEY(snapshot_date, product_id)
);
CREATE INDEX IF NOT EXISTS idx_orders_date_status ON orders(order_date, status);
CREATE INDEX IF NOT EXISTS idx_campaign_daily_date_channel ON campaign_daily(metric_date, channel);
CREATE INDEX IF NOT EXISTS idx_inventory_snapshots_date ON inventory_snapshots(snapshot_date);
"""


def seed_sqlite(database: Database, today: date | None = None) -> None:
    """Idempotent synthetic seed mirroring data/postgres/002_seed.sql."""
    if database.is_postgres:
        raise ValueError("seed_sqlite only accepts a SQLite database")
    today = today or date.today()
    customers = [
        (1, "晨曦商贸", "华东", str(today - timedelta(days=180))),
        (2, "远山零售", "华南", str(today - timedelta(days=150))),
        (3, "北辰生活", "华北", str(today - timedelta(days=120))),
        (4, "西岭优选", "西南", str(today - timedelta(days=90))),
    ]
    products = [
        (1, "智能水杯", "家居", 199), (2, "降噪耳机", "数码", 599),
        (3, "轻量背包", "服饰", 299), (4, "咖啡礼盒", "食品", 159),
    ]
    orders = []
    items = []
    for n in range(1, 121):
        status = "refunded" if n % 17 == 0 else "cancelled" if n % 23 == 0 else "paid"
        channel = ("抖音", "天猫", "小程序")[n % 3]
        region = ("华东", "华南", "华北", "西南")[n % 4]
        gross = 100 + (n % 9) * 75
        orders.append((1000 + n, 1 + n % 4, str(today - timedelta(days=n % 60)), status, channel, region, gross, (n % 4) * 10, 50 if n % 17 == 0 else 0))
        items.append((5000 + n, 1000 + n, 1 + n % 4, 1 + n % 3, gross))
    campaigns = [("开学季", "抖音"), ("会员复购", "小程序"), ("新品首发", "天猫"), ("年中大促", "天猫")]
    campaign_daily = []
    for day in range(60):
        for index, (campaign_name, channel) in enumerate(campaigns, start=1):
            sessions = 55 + ((day * 7 + index * 11) % 90)
            attributed_orders = 4 + ((day + index * 2) % 16)
            attributed_revenue = attributed_orders * (160 + index * 35)
            campaign_daily.append((
                str(today - timedelta(days=day)), campaign_name, channel,
                sessions * 18, sessions * 3, sessions, attributed_orders,
                attributed_revenue, 180 + index * 55 + (day % 7) * 8,
            ))
    inventory_snapshots = []
    for day in range(60):
        for product_id in range(1, 5):
            available_qty = 0 if (day + product_id * 5) % 19 == 0 else 12 + ((day * 3 + product_id * 7) % 75)
            inventory_snapshots.append((str(today - timedelta(days=day)), product_id, available_qty))
    with database.connect() as connection:
        connection.executescript(SQLITE_SCHEMA)
        connection.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?)", customers)
        connection.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?)", products)
        connection.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", orders)
        connection.executemany("INSERT OR IGNORE INTO order_items VALUES (?, ?, ?, ?, ?)", items)
        connection.executemany("INSERT OR IGNORE INTO campaign_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", campaign_daily)
        connection.executemany("INSERT OR IGNORE INTO inventory_snapshots VALUES (?, ?, ?)", inventory_snapshots)
        connection.commit()

