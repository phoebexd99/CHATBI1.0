"""Validate and load a de-identified WMS/ERP inventory snapshot CSV.

Expected columns are snapshot_date, product_key (or product_id/sku), and
available_qty. warehouse_key and source_record_id are optional. The loader
never derives stock from orders and never prints DATABASE_URL or credentials.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import psycopg

from backend.app.config import settings


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "data" / "postgres" / "004_inventory_ingestion.sql"


def _value(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = (row.get(name) or "").strip()
        if value:
            return value
    return ""


def _parse_date(value: str) -> date:
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise ValueError(f"invalid snapshot_date: {value}")


def read_snapshot(path: Path, source: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    raw_rows: list[dict[str, str]] = []
    errors: list[str] = []
    duplicate_keys: set[tuple[str, str, str, str]] = set()
    seen: set[tuple[str, str, str, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("inventory CSV has no header")
        for line_number, row in enumerate(reader, start=2):
            snapshot_date = _value(row, ("snapshot_date", "date", "快照日期"))
            product_key = _value(row, ("product_key", "product_id", "sku", "商品ID", "商品编码"))
            available_qty = _value(row, ("available_qty", "available_quantity", "stock_qty", "可用库存"))
            warehouse_key = _value(row, ("warehouse_key", "warehouse_id", "仓库ID", "仓库编码"))
            source_record_id = _value(row, ("source_record_id", "record_id", "库存记录ID"))
            try:
                parsed_date = _parse_date(snapshot_date)
                quantity = int(float(available_qty))
                if quantity < 0:
                    raise ValueError("available_qty must be >= 0")
                if not product_key:
                    raise ValueError("product key is empty")
            except ValueError as error:
                errors.append(f"line {line_number}: {error}")
                continue
            key = (parsed_date.isoformat(), product_key, warehouse_key, source)
            if key in seen:
                duplicate_keys.add(key)
            seen.add(key)
            raw_rows.append({
                "snapshot_date": parsed_date.isoformat(),
                "product_key": product_key,
                "available_qty": str(quantity),
                "warehouse_key": warehouse_key or None,
                "inventory_source": source,
                "source_record_id": source_record_id or None,
            })
    if errors:
        preview = "; ".join(errors[:5])
        raise ValueError(f"inventory validation failed ({len(errors)} errors): {preview}")
    if duplicate_keys:
        raise ValueError(f"inventory validation failed: {len(duplicate_keys)} duplicate date/product/warehouse rows")
    return raw_rows, {"row_count": len(raw_rows), "duplicate_count": 0, "error_count": 0}


def statements(sql_text: str) -> list[str]:
    return [part.strip() for part in sql_text.split(";") if part.strip()]


def load_snapshot(path: Path, source: str, replace: bool = False) -> dict[str, int | str]:
    raw_rows, quality = read_snapshot(path, source)
    run_id = str(uuid4())
    aggregated: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    for row in raw_rows:
        aggregated[(row["snapshot_date"], row["product_key"], source)] += int(row["available_qty"])
    with psycopg.connect(settings.database_url) as connection:
        for statement in statements(MIGRATION.read_text(encoding="utf-8")):
            connection.execute(statement)
        if replace:
            connection.execute(
                "DELETE FROM chatbi_raw.wms_inventory_snapshot WHERE inventory_source = %s",
                (source,),
            )
            connection.execute(
                "DELETE FROM chatbi_mart.fct_inventory_snapshot WHERE inventory_source = %s",
                (source,),
            )
        connection.executemany(
            "INSERT INTO chatbi_raw.wms_inventory_snapshot "
            "(snapshot_date, product_key, available_qty, warehouse_key, inventory_source, source_record_id) "
            "VALUES (%(snapshot_date)s, %(product_key)s, %(available_qty)s, %(warehouse_key)s, %(inventory_source)s, %(source_record_id)s)",
            raw_rows,
        )
        connection.executemany(
            "INSERT INTO chatbi_mart.fct_inventory_snapshot "
            "(snapshot_date, product_key, available_qty, inventory_source, is_proxy, source_record_id) "
            "VALUES (%s, %s, %s, %s, false, %s) "
            "ON CONFLICT (snapshot_date, product_key, inventory_source) DO UPDATE SET "
            "available_qty = EXCLUDED.available_qty, is_proxy = false, loaded_at = now()",
            [(*key, quantity, f"{source}:{key[0]}:{key[1]}") for key, quantity in aggregated.items()],
        )
        connection.execute(
            "INSERT INTO chatbi_meta.data_quality_run "
            "(run_id, dataset_key, status, row_count, duplicate_count, error_count, details) "
            "VALUES (%s, %s, 'passed', %s, %s, %s, %s::jsonb)",
            (run_id, f"inventory:{source}", quality["row_count"], quality["duplicate_count"], quality["error_count"], json.dumps({"source_file": path.name})),
        )
    return {**quality, "aggregated_rows": len(aggregated), "run_id": run_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="WMS/ERP snapshot CSV")
    parser.add_argument("--source", required=True, help="Stable source identifier, e.g. wms_prod")
    parser.add_argument("--replace", action="store_true", help="Replace this source's prior rows")
    args = parser.parse_args()
    result = load_snapshot(args.csv.resolve(), args.source, replace=args.replace)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
