"""Load the public Olist CSV package into the isolated CHATBI raw schema.

The script never prints DATABASE_URL or any credential. It applies the additive
warehouse contract, then COPY-loads only files present in --raw-dir. A reload
requires the explicit --replace flag because raw-table replacement is destructive
inside the dedicated chatbi_raw schema.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg
from psycopg import sql

from backend.app.config import settings


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "data" / "postgres" / "003_olist_warehouse.sql"

FILES: dict[str, tuple[str, ...]] = {
    "olist_customers_dataset.csv": ("chatbi_raw.olist_customers", "customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"),
    "olist_geolocation_dataset.csv": ("chatbi_raw.olist_geolocation", "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"),
    "olist_order_items_dataset.csv": ("chatbi_raw.olist_order_items", "order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"),
    "olist_order_payments_dataset.csv": ("chatbi_raw.olist_order_payments", "order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"),
    "olist_order_reviews_dataset.csv": ("chatbi_raw.olist_order_reviews", "review_id", "order_id", "review_score", "review_comment_title", "review_comment_message", "review_creation_date", "review_answer_timestamp"),
    "olist_orders_dataset.csv": ("chatbi_raw.olist_orders", "order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"),
    "olist_products_dataset.csv": ("chatbi_raw.olist_products", "product_id", "product_category_name", "product_name_length", "product_description_length", "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"),
    "olist_sellers_dataset.csv": ("chatbi_raw.olist_sellers", "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
    "product_category_name_translation.csv": ("chatbi_raw.product_category_translation", "product_category_name", "product_category_name_english"),
    "olist_marketing_qualified_leads_dataset.csv": ("chatbi_raw.olist_marketing_qualified_leads", "mql_id", "first_contact_date", "landing_page_id", "origin"),
    "olist_closed_deals_dataset.csv": ("chatbi_raw.olist_closed_deals", "mql_id", "seller_id", "sdr_id", "sr_id", "won_date", "business_segment", "lead_type", "lead_behaviour_profile", "has_company", "has_gtin", "average_stock", "business_type", "declared_product_catalog_size", "declared_monthly_revenue"),
}


def statements(sql_text: str) -> list[str]:
    return [part.strip() for part in sql_text.split(";") if part.strip()]


def load(raw_dir: Path, replace: bool = False) -> dict[str, int]:
    present = [(raw_dir / filename, spec) for filename, spec in FILES.items() if (raw_dir / filename).is_file()]
    if not present:
        expected = ", ".join(FILES)
        raise SystemExit(f"No Olist CSV files found in {raw_dir}. Expected one of: {expected}")

    counts: dict[str, int] = {}
    with psycopg.connect(settings.database_url) as connection:
        for statement in statements(MIGRATION.read_text(encoding="utf-8")):
            connection.execute(statement)
        if replace:
            connection.execute("TRUNCATE TABLE " + ", ".join(spec[0] for _, spec in present))
        for path, spec in present:
            table, *columns = spec
            copy_query = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')").format(
                sql.Identifier(*table.split(".")),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            )
            with connection.cursor() as cursor:
                with cursor.copy(copy_query) as copy:
                    with path.open("rb") as source:
                        while chunk := source.read(1024 * 1024):
                            copy.write(chunk)
            counts[table] = connection.execute(sql.SQL("SELECT count(*) FROM {} ").format(sql.Identifier(*table.split(".")))).fetchone()[0]
        connection.execute(
            "UPDATE chatbi_meta.dataset_registry SET status = 'loaded', loaded_at = now(), row_counts = %s::jsonb WHERE dataset_key = 'olist_brazilian_ecommerce'",
            [__import__("json").dumps(counts)],
        )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True, help="Directory containing the extracted Olist CSV files")
    parser.add_argument("--replace", action="store_true", help="Replace rows in the dedicated raw tables before loading")
    args = parser.parse_args()
    counts = load(args.raw_dir.resolve(), replace=args.replace)
    print("Loaded Olist raw tables:")
    for table, count in counts.items():
        print(f"- {table}: {count} rows")


if __name__ == "__main__":
    main()
