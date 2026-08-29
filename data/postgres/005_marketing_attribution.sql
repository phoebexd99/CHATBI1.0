-- External advertising spend and attribution contract.
-- Olist's public Marketing Funnel has leads/deals but no media spend, so this
-- source is deliberately separate and remains empty until an approved export
-- from an ad platform is supplied.

CREATE TABLE IF NOT EXISTS chatbi_raw.ad_campaign_daily (
  metric_date TEXT NOT NULL,
  campaign_key TEXT NOT NULL,
  campaign_name TEXT,
  channel TEXT NOT NULL,
  impressions TEXT,
  clicks TEXT,
  sessions TEXT,
  attributed_orders TEXT,
  attributed_revenue TEXT,
  spend TEXT NOT NULL,
  marketing_source TEXT NOT NULL,
  source_record_id TEXT,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_campaign_daily_date
  ON chatbi_raw.ad_campaign_daily(metric_date, channel);
CREATE INDEX IF NOT EXISTS idx_ad_campaign_daily_source
  ON chatbi_raw.ad_campaign_daily(marketing_source);

CREATE TABLE IF NOT EXISTS chatbi_mart.fct_marketing_daily (
  metric_date DATE NOT NULL,
  campaign_key TEXT NOT NULL,
  campaign_name TEXT,
  channel TEXT NOT NULL,
  impressions INTEGER NOT NULL DEFAULT 0 CHECK (impressions >= 0),
  clicks INTEGER NOT NULL DEFAULT 0 CHECK (clicks >= 0),
  sessions INTEGER NOT NULL DEFAULT 0 CHECK (sessions >= 0),
  attributed_orders INTEGER NOT NULL DEFAULT 0 CHECK (attributed_orders >= 0),
  attributed_revenue NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (attributed_revenue >= 0),
  spend NUMERIC(14,2) NOT NULL CHECK (spend >= 0),
  marketing_source TEXT NOT NULL,
  source_record_id TEXT,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (metric_date, campaign_key, channel, marketing_source)
);

COMMENT ON TABLE chatbi_raw.ad_campaign_daily IS
  'Approved ad-platform daily export; raw values preserved for audit.';
COMMENT ON TABLE chatbi_mart.fct_marketing_daily IS
  'Certified marketing spend/attribution fact; publish ROAS only after source and attribution review.';
