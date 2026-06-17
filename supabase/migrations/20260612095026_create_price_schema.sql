-- Table: public.price_snapshots (Nightly price updates)
CREATE TABLE IF NOT EXISTS public.price_snapshots (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    item_key text NOT NULL,
    item_name text NOT NULL,
    item_category text NOT NULL,
    store text NOT NULL,
    price_gbp numeric(10, 2) NOT NULL,
    observed_date date GENERATED ALWAYS AS ((observed_at AT TIME ZONE 'UTC')::date) STORED,
    observed_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT pk_price_snapshots PRIMARY KEY (id),
    CONSTRAINT uq_price_snapshots_item_store_date UNIQUE (item_key, store, observed_date), -- (One snapshot per item per store per day)
    CONSTRAINT ck_price_snapshots_item_key_length CHECK (length(item_key) <= 64),
    CONSTRAINT ck_price_snapshots_item_name_length CHECK (length(item_name) <= 255),
    CONSTRAINT ck_price_snapshots_item_category_length CHECK (length(item_category) <= 64),
    CONSTRAINT ck_price_snapshots_store_length CHECK (length(store) <= 25),
    CONSTRAINT ck_price_snapshots_price_gbp CHECK (price_gbp >= 0::numeric),
    CONSTRAINT ck_price_snapshots_store_value CHECK (store = ANY(ARRAY['tesco', 'asda', 'sainsburys', 'morrisons', 'aldi', 'lidl', 'waitrose', 'co-op']))
);

-- Index: public.ix_price_snapshots_item_key_store_date
CREATE INDEX IF NOT EXISTS ix_price_snapshots_item_key_store_date
    ON public.price_snapshots(item_key, store, observed_at DESC);

-- Index: public.ix_price_snapshots_store_date
CREATE INDEX IF NOT EXISTS ix_price_snapshots_store_date
    ON public.price_snapshots(store, observed_at DESC);

-- Table: public.store_index_history (Daily computed averages)
CREATE TABLE IF NOT EXISTS public.store_index_history (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    store text NOT NULL,
    indexed_value numeric(10, 2) NOT NULL,
    item_count integer NOT NULL DEFAULT 0::integer,
    computed_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT pk_store_index_history PRIMARY KEY (id),
    CONSTRAINT ck_store_index_history_store_length CHECK (length(store) <= 25),
    CONSTRAINT ck_store_index_history_store_value CHECK (store = ANY(ARRAY['tesco', 'asda', 'sainsburys', 'morrisons', 'aldi', 'lidl', 'waitrose', 'co-op']))
);

-- Index: ix_store_index_history_store
CREATE INDEX IF NOT EXISTS ix_store_index_history_store 
    ON public.store_index_history(store);

-- RLS Configuration
ALTER TABLE public.price_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.store_index_history ENABLE ROW LEVEL SECURITY;

-- Default deny all for non-admin roles (service_role bypasses RLS)
CREATE POLICY "service_role_only_access" 
    ON public.price_snapshots FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_only_access" 
    ON public.store_index_history FOR ALL TO service_role USING (true);

-- Grant Access to Data API Roles
GRANT ALL ON TABLE public.price_snapshots TO service_role;
GRANT ALL ON TABLE public.store_index_history TO service_role;