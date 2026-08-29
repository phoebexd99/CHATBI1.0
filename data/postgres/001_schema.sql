CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGINT PRIMARY KEY,
  customer_name TEXT NOT NULL,
  region TEXT NOT NULL,
  signup_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  product_id BIGINT PRIMARY KEY,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
  order_id BIGINT PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
  order_date DATE NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('paid', 'refunded', 'cancelled')),
  channel TEXT NOT NULL,
  region TEXT NOT NULL,
  gross_amount NUMERIC(14,2) NOT NULL,
  discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
  refund_amount NUMERIC(14,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGINT PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id),
  product_id BIGINT NOT NULL REFERENCES products(product_id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  item_gross_amount NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_daily (
  metric_date DATE NOT NULL,
  campaign_name TEXT NOT NULL,
  channel TEXT NOT NULL,
  impressions INTEGER NOT NULL CHECK (impressions >= 0),
  clicks INTEGER NOT NULL CHECK (clicks >= 0),
  sessions INTEGER NOT NULL CHECK (sessions >= 0),
  attributed_orders INTEGER NOT NULL CHECK (attributed_orders >= 0),
  attributed_revenue NUMERIC(14,2) NOT NULL CHECK (attributed_revenue >= 0),
  spend NUMERIC(14,2) NOT NULL CHECK (spend >= 0),
  PRIMARY KEY(metric_date, campaign_name)
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
  snapshot_date DATE NOT NULL,
  product_id BIGINT NOT NULL REFERENCES products(product_id),
  available_qty INTEGER NOT NULL CHECK (available_qty >= 0),
  PRIMARY KEY(snapshot_date, product_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_date_status ON orders(order_date, status);
CREATE INDEX IF NOT EXISTS idx_orders_region_channel ON orders(region, channel);
CREATE INDEX IF NOT EXISTS idx_campaign_daily_date_channel ON campaign_daily(metric_date, channel);
CREATE INDEX IF NOT EXISTS idx_inventory_snapshots_date ON inventory_snapshots(snapshot_date);

