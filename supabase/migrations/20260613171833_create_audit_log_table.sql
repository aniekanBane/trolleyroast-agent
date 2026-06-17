-- Table: public.worker_audit_logs
CREATE TABLE IF NOT EXISTS public.worker_audit_logs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    run_type text NOT NULL,
    run_date date NOT NULL,
    items_checked integer NOT NULL DEFAULT 0::integer,
    prices_updated integer NOT NULL DEFAULT 0::integer,
    alerts_generated integer NOT NULL DEFAULT 0::integer,
    errors jsonb,
    summary text NOT NULL,
    CONSTRAINT pk_worker_audit_logs PRIMARY KEY (id),
    CONSTRAINT ck_worker_audit_logs_run_type_length CHECK (length(run_type) <= 32)
);

-- Index: public.ix_worker_audit_logs_run_type
CREATE INDEX IF NOT EXISTS ix_worker_audit_logs_run_type 
    ON public.worker_audit_logs(run_type);

-- RLS Configuration
ALTER TABLE public.worker_audit_logs ENABLE ROW LEVEL SECURITY;

-- Default deny all for non-admin roles (service_role bypasses RLS)
CREATE POLICY "service_role_only_access" 
    ON public.worker_audit_logs FOR ALL TO service_role USING (true);

-- Grant Access to Data API Roles
GRANT ALL ON TABLE public.worker_audit_logs TO service_role;