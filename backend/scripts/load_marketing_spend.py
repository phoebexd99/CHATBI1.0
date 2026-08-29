"""Validate and load a de-identified ad-platform daily export.

Required columns: metric_date (or date), campaign_key (or campaign_id),
channel, spend. Optional numeric columns are impressions, clicks, sessions,
attributed_orders, and attributed_revenue. The loader does not claim ROAS
quality; attribution review remains a governance step.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import psycopg

from backend.app.config import settings


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "data" / "postgres" / "005_marketing_attribution.sql"


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
    raise ValueError(f"invalid metric_date: {value}")


def _number(value: str, field: str, integer: bool = False) -> str:
    if not value:
        return "0"
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{field} is not numeric: {value}") from error
    if parsed < 0:
        raise ValueError(f"{field} must be >= 0")
    if integer and not parsed.is_integer():
        raise ValueError(f"{field} must be an integer")
    return str(int(parsed)) if integer else str(parsed)


def read_campaign_csv(path: Path, source: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    duplicates = 0
    errors: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("marketing CSV has no header")
        for line_number, row in enumerate(reader, start=2):
            try:
                metric_date = _parse_date(_value(row, ("metric_date", "date", "日期"))).isoformat()
                campaign_key = _value(row, ("campaign_key", "campaign_id", "campaign", "活动ID", "活动"))
                channel = _value(row, ("channel", "source", "渠道"))
                if not campaign_key or not channel:
                    raise ValueError("campaign_key and channel are required")
                impressions = _number(_value(row, ("impressions", "曝光量", "展示量")), "impressions", True)
                clicks = _number(_value(row, ("clicks", "点击量")), "clicks", True)
                sessions = _number(_value(row, ("sessions", "会话数")), "sessions", True)
                attributed_orders = _number(_value(row, ("attributed_orders", "orders", "归因订单")), "attributed_orders", True)
                attributed_revenue = _number(_value(row, ("attributed_revenue", "revenue", "归因收入")), "attributed_revenue")
                spend = _number(_value(row, ("spend", "cost", "花费", "广告花费")), "spend")
                if int(clicks) > int(impressions):
                    raise ValueError("clicks cannot exceed impressions")
            except ValueError as error:
                errors.append(f"line {line_number}: {error}")
                continue
            key = (metric_date, campaign_key, channel, source)
            if key in seen:
                duplicates += 1
            seen.add(key)
            rows.append({
                "metric_date": metric_date,
                "campaign_key": campaign_key,
                "campaign_name": _value(row, ("campaign_name", "campaign", "活动名称")) or campaign_key,
                "channel": channel,
                "impressions": impressions,
                "clicks": clicks,
                "sessions": sessions,
                "attributed_orders": attributed_orders,
                "attributed_revenue": attributed_revenue,
                "spend": spend,
                "marketing_source": source,
                "source_record_id": _value(row, ("source_record_id", "record_id", "记录ID")) or None,
            })
    if errors:
        raise ValueError(f"marketing validation failed ({len(errors)} errors): {'; '.join(errors[:5])}")
    if duplicates:
        raise ValueError(f"marketing validation failed: {duplicates} duplicate date/campaign/channel rows")
    return rows, {"row_count": len(rows), "duplicate_count": 0, "error_count": 0}


def statements(sql_text: str) -> list[str]:
    return [part.strip() for part in sql_text.split(";") if part.strip()]


def load_campaign_csv(path: Path, source: str, replace: bool = False) -> dict[str, int | str]:
    rows, quality = read_campaign_csv(path, source)
    run_id = str(uuid4())
    with psycopg.connect(settings.database_url) as connection:
        for statement in statements(MIGRATION.read_text(encoding="utf-8")):
            connection.execute(statement)
        if replace:
            connection.execute("DELETE FROM chatbi_raw.ad_campaign_daily WHERE marketing_source = %s", (source,))
            connection.execute("DELETE FROM chatbi_mart.fct_marketing_daily WHERE marketing_source = %s", (source,))
        connection.executemany(
            "INSERT INTO chatbi_raw.ad_campaign_daily "
            "(metric_date, campaign_key, campaign_name, channel, impressions, clicks, sessions, attributed_orders, attributed_revenue, spend, marketing_source, source_record_id) "
            "VALUES (%(metric_date)s, %(campaign_key)s, %(campaign_name)s, %(channel)s, %(impressions)s, %(clicks)s, %(sessions)s, %(attributed_orders)s, %(attributed_revenue)s, %(spend)s, %(marketing_source)s, %(source_record_id)s)",
            rows,
        )
        connection.executemany(
            "INSERT INTO chatbi_mart.fct_marketing_daily "
            "(metric_date, campaign_key, campaign_name, channel, impressions, clicks, sessions, attributed_orders, attributed_revenue, spend, marketing_source, source_record_id) "
            "VALUES (%(metric_date)s, %(campaign_key)s, %(campaign_name)s, %(channel)s, %(impressions)s, %(clicks)s, %(sessions)s, %(attributed_orders)s, %(attributed_revenue)s, %(spend)s, %(marketing_source)s, %(source_record_id)s) "
            "ON CONFLICT (metric_date, campaign_key, channel, marketing_source) DO UPDATE SET "
            "campaign_name = EXCLUDED.campaign_name, impressions = EXCLUDED.impressions, clicks = EXCLUDED.clicks, sessions = EXCLUDED.sessions, attributed_orders = EXCLUDED.attributed_orders, attributed_revenue = EXCLUDED.attributed_revenue, spend = EXCLUDED.spend, source_record_id = EXCLUDED.source_record_id, loaded_at = now()",
            rows,
        )
        connection.execute(
            "INSERT INTO chatbi_meta.data_quality_run "
            "(run_id, dataset_key, status, row_count, duplicate_count, error_count, details) "
            "VALUES (%s, %s, 'passed', %s, %s, %s, %s::jsonb)",
            (run_id, f"marketing:{source}", quality["row_count"], quality["duplicate_count"], quality["error_count"], json.dumps({"source_file": path.name})),
        )
    return {**quality, "run_id": run_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="Ad-platform daily export CSV")
    parser.add_argument("--source", required=True, help="Stable source identifier, e.g. ads_meta_prod")
    parser.add_argument("--replace", action="store_true", help="Replace this source's prior rows")
    args = parser.parse_args()
    print(json.dumps(load_campaign_csv(args.csv.resolve(), args.source, args.replace), ensure_ascii=False))


if __name__ == "__main__":
    main()
