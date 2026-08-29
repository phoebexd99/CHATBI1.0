-- CHATBI Olist warehouse contract.
-- This migration is additive and isolated from the existing demo tables.
-- Raw tables intentionally keep source columns as text; parsing and business
-- rules live in chatbi_mart views so a reload is auditable and reversible.

CREATE SCHEMA IF NOT EXISTS chatbi_raw;
CREATE SCHEMA IF NOT EXISTS chatbi_mart;
CREATE SCHEMA IF NOT EXISTS chatbi_meta;

CREATE TABLE IF NOT EXISTS chatbi_meta.dataset_registry (
  dataset_key TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  license_note TEXT,
  data_classification TEXT NOT NULL DEFAULT 'anonymized_public',
  loaded_at TIMESTAMPTZ,
  row_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'loaded', 'retired')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS chatbi_meta.metric_registry (
  metric_key TEXT PRIMARY KEY,
  metric_version TEXT NOT NULL,
  display_name TEXT NOT NULL,
  definition TEXT NOT NULL,
  grain TEXT NOT NULL,
  owner TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'published', 'retired')),
  effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
  effective_to DATE,
  reviewed_at TIMESTAMPTZ,
  reviewed_by TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS chatbi_meta.verified_sql (
  example_key TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  sql_text TEXT NOT NULL,
  metric_keys TEXT[] NOT NULL DEFAULT '{}',
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'verified', 'retired')),
  owner TEXT NOT NULL,
  reviewed_at TIMESTAMPTZ,
  reviewed_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chatbi_raw.olist_customers (
  customer_id TEXT, customer_unique_id TEXT, customer_zip_code_prefix TEXT,
  customer_city TEXT, customer_state TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_geolocation (
  geolocation_zip_code_prefix TEXT, geolocation_lat TEXT, geolocation_lng TEXT,
  geolocation_city TEXT, geolocation_state TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_order_items (
  order_id TEXT, order_item_id TEXT, product_id TEXT, seller_id TEXT,
  shipping_limit_date TEXT, price TEXT, freight_value TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_order_payments (
  order_id TEXT, payment_sequential TEXT, payment_type TEXT,
  payment_installments TEXT, payment_value TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_order_reviews (
  review_id TEXT, order_id TEXT, review_score TEXT, review_comment_title TEXT,
  review_comment_message TEXT, review_creation_date TEXT, review_answer_timestamp TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_orders (
  order_id TEXT, customer_id TEXT, order_status TEXT,
  order_purchase_timestamp TEXT, order_approved_at TEXT,
  order_delivered_carrier_date TEXT, order_delivered_customer_date TEXT,
  order_estimated_delivery_date TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_products (
  product_id TEXT, product_category_name TEXT, product_name_length TEXT,
  product_description_length TEXT, product_photos_qty TEXT, product_weight_g TEXT,
  product_length_cm TEXT, product_height_cm TEXT, product_width_cm TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_sellers (
  seller_id TEXT, seller_zip_code_prefix TEXT, seller_city TEXT, seller_state TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.product_category_translation (
  product_category_name TEXT, product_category_name_english TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_marketing_qualified_leads (
  mql_id TEXT, first_contact_date TEXT, landing_page_id TEXT, origin TEXT
);
CREATE TABLE IF NOT EXISTS chatbi_raw.olist_closed_deals (
  mql_id TEXT, seller_id TEXT, sdr_id TEXT, sr_id TEXT, won_date TEXT,
  business_segment TEXT, lead_type TEXT, lead_behaviour_profile TEXT,
  has_company TEXT, has_gtin TEXT, average_stock TEXT, business_type TEXT,
  declared_product_catalog_size TEXT, declared_monthly_revenue TEXT
);

CREATE INDEX IF NOT EXISTS idx_olist_raw_orders_customer
  ON chatbi_raw.olist_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_olist_raw_order_items_order
  ON chatbi_raw.olist_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_olist_raw_order_items_product
  ON chatbi_raw.olist_order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_olist_raw_order_items_seller
  ON chatbi_raw.olist_order_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_olist_raw_payments_order
  ON chatbi_raw.olist_order_payments(order_id);
CREATE INDEX IF NOT EXISTS idx_olist_raw_mql_origin
  ON chatbi_raw.olist_marketing_qualified_leads(origin);

COMMENT ON SCHEMA chatbi_raw IS 'Olist source-shaped, append/reload-controlled raw layer';
COMMENT ON SCHEMA chatbi_mart IS 'CHATBI certified analytics views and inventory contract';
COMMENT ON SCHEMA chatbi_meta IS 'Metric versions, dataset lineage, and verified SQL governance';

CREATE OR REPLACE VIEW chatbi_mart.dim_customer AS
SELECT
  c.customer_unique_id AS customer_key,
  MIN(c.customer_state) AS region,
  MIN(c.customer_city) AS city,
  COUNT(DISTINCT c.customer_id) AS source_customer_ids,
  COUNT(DISTINCT o.order_id) AS order_count,
  MIN(NULLIF(o.order_purchase_timestamp, '')::timestamp)::date AS first_order_date,
  MAX(NULLIF(o.order_purchase_timestamp, '')::timestamp)::date AS last_order_date
FROM chatbi_raw.olist_customers c
LEFT JOIN chatbi_raw.olist_orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_unique_id;

CREATE OR REPLACE VIEW chatbi_mart.dim_product AS
SELECT
  p.product_id AS product_key,
  COALESCE(t.product_category_name_english, p.product_category_name) AS category,
  p.product_category_name AS source_category,
  NULLIF(p.product_weight_g, '')::numeric AS weight_g,
  NULLIF(p.product_length_cm, '')::numeric AS length_cm,
  NULLIF(p.product_height_cm, '')::numeric AS height_cm,
  NULLIF(p.product_width_cm, '')::numeric AS width_cm
FROM chatbi_raw.olist_products p
LEFT JOIN chatbi_raw.product_category_translation t
  ON t.product_category_name = p.product_category_name;

CREATE OR REPLACE VIEW chatbi_mart.dim_seller AS
SELECT seller_id AS seller_key, seller_city AS city, seller_state AS region,
       seller_zip_code_prefix AS zip_code_prefix
FROM chatbi_raw.olist_sellers;

CREATE OR REPLACE VIEW chatbi_mart.fct_order_item AS
SELECT
  oi.order_item_id,
  oi.order_id,
  o.customer_id AS source_customer_key,
  c.customer_unique_id AS customer_key,
  oi.product_id AS product_key,
  oi.seller_id AS seller_key,
  NULLIF(o.order_purchase_timestamp, '')::timestamp AS order_ts,
  NULLIF(oi.shipping_limit_date, '')::timestamp AS shipping_limit_ts,
  o.order_status,
  COALESCE(NULLIF(oi.price, '')::numeric, 0) AS item_gmv,
  COALESCE(NULLIF(oi.freight_value, '')::numeric, 0) AS freight_value,
  COALESCE(t.product_category_name_english, p.product_category_name) AS category,
  c.customer_state AS region
FROM chatbi_raw.olist_order_items oi
JOIN chatbi_raw.olist_orders o ON o.order_id = oi.order_id
LEFT JOIN chatbi_raw.olist_customers c ON c.customer_id = o.customer_id
LEFT JOIN chatbi_raw.olist_products p ON p.product_id = oi.product_id
LEFT JOIN chatbi_raw.product_category_translation t
  ON t.product_category_name = p.product_category_name;

CREATE OR REPLACE VIEW chatbi_mart.fct_order AS
WITH items AS (
  SELECT order_id, SUM(COALESCE(NULLIF(price, '')::numeric, 0)) AS item_gmv,
         SUM(COALESCE(NULLIF(freight_value, '')::numeric, 0)) AS freight_value,
         COUNT(*) AS item_count, COUNT(DISTINCT seller_id) AS seller_count
  FROM chatbi_raw.olist_order_items
  GROUP BY order_id
), payments AS (
  SELECT order_id, SUM(COALESCE(NULLIF(payment_value, '')::numeric, 0)) AS paid_value
  FROM chatbi_raw.olist_order_payments
  GROUP BY order_id
)
SELECT
  o.order_id,
  c.customer_unique_id AS customer_key,
  o.customer_id AS source_customer_key,
  NULLIF(o.order_purchase_timestamp, '')::timestamp AS order_ts,
  NULLIF(o.order_delivered_customer_date, '')::timestamp AS delivered_ts,
  NULLIF(o.order_estimated_delivery_date, '')::timestamp AS estimated_delivery_ts,
  o.order_status,
  COALESCE(i.item_gmv, 0) AS item_gmv,
  COALESCE(i.freight_value, 0) AS freight_value,
  COALESCE(i.item_gmv, 0) + COALESCE(i.freight_value, 0) AS order_value,
  COALESCE(p.paid_value, 0) AS paid_value,
  COALESCE(i.item_count, 0) AS item_count,
  COALESCE(i.seller_count, 0) AS seller_count,
  CASE WHEN o.order_status IN ('canceled', 'unavailable') THEN 0
       ELSE COALESCE(i.item_gmv, 0) END AS net_revenue,
  c.customer_state AS region
FROM chatbi_raw.olist_orders o
LEFT JOIN chatbi_raw.olist_customers c ON c.customer_id = o.customer_id
LEFT JOIN items i ON i.order_id = o.order_id
LEFT JOIN payments p ON p.order_id = o.order_id;

CREATE OR REPLACE VIEW chatbi_mart.fct_payment AS
SELECT order_id, payment_sequential::integer AS payment_sequence,
       payment_type, NULLIF(payment_installments, '')::integer AS installments,
       COALESCE(NULLIF(payment_value, '')::numeric, 0) AS payment_value
FROM chatbi_raw.olist_order_payments;

CREATE OR REPLACE VIEW chatbi_mart.fct_review AS
SELECT review_id, order_id, NULLIF(review_score, '')::integer AS review_score,
       review_comment_title, review_comment_message,
       NULLIF(review_creation_date, '')::timestamp AS created_ts,
       NULLIF(review_answer_timestamp, '')::timestamp AS answered_ts
FROM chatbi_raw.olist_order_reviews;

CREATE OR REPLACE VIEW chatbi_mart.fct_marketing_lead AS
SELECT
  m.mql_id,
  NULLIF(m.first_contact_date, '')::date AS first_contact_date,
  m.origin AS channel,
  m.landing_page_id,
  d.seller_id AS seller_key,
  NULLIF(d.won_date, '')::date AS won_date,
  CASE WHEN d.mql_id IS NULL THEN 'mql' ELSE 'closed_deal' END AS funnel_stage,
  d.business_segment,
  d.lead_type,
  d.lead_behaviour_profile AS lead_behavior_profile,
  CASE WHEN d.mql_id IS NULL THEN 0 ELSE 1 END AS is_won
FROM chatbi_raw.olist_marketing_qualified_leads m
LEFT JOIN chatbi_raw.olist_closed_deals d ON d.mql_id = m.mql_id;

-- Olist does not publish warehouse stock snapshots. Keep a formal contract
-- empty rather than inventing available quantity from sales activity.
CREATE TABLE IF NOT EXISTS chatbi_mart.fct_inventory_snapshot (
  snapshot_date DATE NOT NULL,
  product_key TEXT NOT NULL,
  available_qty INTEGER NOT NULL CHECK (available_qty >= 0),
  inventory_source TEXT NOT NULL,
  is_proxy BOOLEAN NOT NULL DEFAULT false,
  source_record_id TEXT,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_date, product_key, inventory_source)
);
COMMENT ON TABLE chatbi_mart.fct_inventory_snapshot IS
  'Inventory contract; Olist public source has no on-hand stock, so rows require a WMS/ERP source.';

INSERT INTO chatbi_meta.dataset_registry(dataset_key, source_name, source_url, license_note, notes)
VALUES (
  'olist_brazilian_ecommerce',
  'Olist Brazilian E-Commerce Public Dataset + Marketing Funnel',
  'https://www.kaggle.com/olistbr/brazilian-ecommerce',
  'Verify current Kaggle terms before redistribution; public anonymized dataset.',
  'Orders/customers/products/payments/reviews/sellers plus optional marketing funnel. Inventory is not supplied.'
)
ON CONFLICT (dataset_key) DO UPDATE SET source_name = EXCLUDED.source_name,
  source_url = EXCLUDED.source_url, license_note = EXCLUDED.license_note,
  notes = EXCLUDED.notes;

INSERT INTO chatbi_meta.metric_registry(metric_key, metric_version, display_name, definition, grain, owner, status)
VALUES
  ('olist_gmv', '1.0.0', '商品成交额', '订单明细 price 之和；不含运费，取消/不可用订单按业务规则排除。', 'order_item', 'chatbi-data', 'draft'),
  ('olist_net_revenue', '1.0.0', '净收入', '有效订单的商品成交额；当前 Olist 无退款流水，不能冒充退款后收入。', 'order', 'chatbi-data', 'draft'),
  ('olist_order_count', '1.0.0', '订单数', 'fct_order 的订单数；按订单粒度去重。', 'order', 'chatbi-data', 'draft'),
  ('olist_marketing_conversion_rate', '1.0.0', '线索转化率', 'closed_deal MQL 数 / 全部 MQL 数；需注明 Olist marketing funnel 的观察窗口。', 'mql', 'chatbi-growth', 'draft')
ON CONFLICT (metric_key) DO NOTHING;
