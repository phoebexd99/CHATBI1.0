-- Generic WMS/ERP inventory snapshot landing table and quality audit.
-- This is intentionally separate from the Olist source tables because Olist
-- does not publish on-hand inventory.

CREATE TABLE IF NOT EXISTS chatbi_raw.wms_inventory_snapshot (
  snapshot_date TEXT NOT NULL,
  product_key TEXT NOT NULL,
  available_qty TEXT NOT NULL,
  warehouse_key TEXT,
  inventory_source TEXT NOT NULL,
  source_record_id TEXT,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wms_inventory_date_product
  ON chatbi_raw.wms_inventory_snapshot(snapshot_date, product_key);
CREATE INDEX IF NOT EXISTS idx_wms_inventory_source
  ON chatbi_raw.wms_inventory_snapshot(inventory_source);

CREATE TABLE IF NOT EXISTS chatbi_meta.data_quality_run (
  run_id TEXT PRIMARY KEY,
  dataset_key TEXT NOT NULL,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL CHECK (status IN ('passed', 'failed')),
  row_count INTEGER NOT NULL DEFAULT 0,
  duplicate_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  details JSONB NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE chatbi_raw.wms_inventory_snapshot IS
  'External WMS/ERP inventory landing table; load only approved de-identified snapshots.';
COMMENT ON TABLE chatbi_meta.data_quality_run IS
  'Auditable row-level quality results for external source loads.';
