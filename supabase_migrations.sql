-- ============================================================
-- TrolleyRoast Supabase Migrations
-- Run these in order in the Supabase SQL Editor at:
-- https://supabase.com/dashboard/project/oyqtywxocmqjtobkmoxj/sql
-- ============================================================

-- Migration 001: Calculator leads
CREATE TABLE IF NOT EXISTS calculator_leads (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email            TEXT NOT NULL,
  calculator       TEXT NOT NULL DEFAULT 'weekly-basket-savings',
  household_size   TEXT,
  weekly_spend     NUMERIC(10,2),
  current_store    TEXT,
  shopping_style   TEXT,
  categories       TEXT[],
  weekly_saving    NUMERIC(10,2),
  monthly_saving   NUMERIC(10,2),
  annual_saving    NUMERIC(10,2),
  top_suggested_store TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_calculator_leads_email      ON calculator_leads(email);
CREATE INDEX IF NOT EXISTS idx_calculator_leads_created_at ON calculator_leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calculator_leads_store      ON calculator_leads(current_store);

-- Migration 002: Live price snapshots (from price_sweep_v2.py)
CREATE TABLE IF NOT EXISTS price_snapshots (
  id          BIGSERIAL PRIMARY KEY,
  item_key    TEXT NOT NULL,
  item_name   TEXT NOT NULL,
  category    TEXT NOT NULL,
  store       TEXT NOT NULL,
  price_gbp   NUMERIC(10,2) NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(item_key, store, observed_at::date)   -- one snapshot per item per store per day
);

CREATE INDEX IF NOT EXISTS idx_snapshots_item_store ON price_snapshots(item_key, store, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_store_date  ON price_snapshots(store, observed_at DESC);

-- Migration 003: Store index snapshots (daily computed averages)
CREATE TABLE IF NOT EXISTS store_index_history (
  id          BIGSERIAL PRIMARY KEY,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  store       TEXT NOT NULL,
  index_value NUMERIC(6,4) NOT NULL,
  item_count  INT NOT NULL DEFAULT 0
);

-- Migration 004: Useful view — latest store indices
CREATE OR REPLACE VIEW v_current_store_index AS
SELECT DISTINCT ON (store)
  store,
  index_value,
  item_count,
  computed_at
FROM store_index_history
ORDER BY store, computed_at DESC;

-- Migration 005: Useful view — cheapest store per item today
CREATE OR REPLACE VIEW v_cheapest_per_item AS
SELECT DISTINCT ON (item_key)
  item_key,
  item_name,
  category,
  store,
  price_gbp,
  observed_at
FROM price_snapshots
WHERE observed_at >= now() - interval '48 hours'
ORDER BY item_key, price_gbp ASC;

-- ============================================================
-- After running migrations, set RLS to allow service_role only:
-- ============================================================
ALTER TABLE calculator_leads    ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_snapshots     ENABLE ROW LEVEL SECURITY;
ALTER TABLE store_index_history ENABLE ROW LEVEL SECURITY;

-- Service role bypass (handled automatically by Supabase)
-- No additional policies needed for server-side only access.
