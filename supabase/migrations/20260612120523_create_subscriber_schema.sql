-- Table: public.alert_subscribers 
CREATE TABLE IF NOT EXISTS public.alert_subscribers (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    email_address text NOT NULL,
    full_name text,
    is_active boolean NOT NULL DEFAULT false,
    wants_pro boolean NOT NULL DEFAULT false,
    welcome_sent boolean NOT NULL DEFAULT false,
    welcome_sent_at timestamp with time zone,
    joined_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT pk_alert_subscriber PRIMARY KEY (id),
    CONSTRAINT uq_alert_subscribers_email_address UNIQUE (email_address), -- Unique subscriber
    CONSTRAINT ck_alert_subscribers_email_address_length CHECK(length(email_address) <= 255),
    CONSTRAINT ck_alert_subscribers_full_name_length CHECK(length(full_name) <= 100),
    CONSTRAINT ck_alert_subscribers_welcome_sent CHECK (welcome_sent = (welcome_sent_at IS NOT NULL))
);

-- Table: public.subscriber_watchlist
CREATE TABLE IF NOT EXISTS public.subscriber_watchlist (
    subscriber_id uuid NOT NULL,
    item_key text NOT NULL,
    CONSTRAINT pk_subscriber_watchlist PRIMARY KEY (subscriber_id, item_key),
    CONSTRAINT ck_subscriber_watchlist_item_key_length CHECK(length(item_key) <= 64),
    CONSTRAINT fk_subscriber_watchlist_subscriber_id_alert_subscribers_id FOREIGN KEY (subscriber_id)
        REFERENCES public.alert_subscribers(id)
        ON DELETE CASCADE
);

-- RLS Configuration
ALTER TABLE public.alert_subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriber_watchlist ENABLE ROW LEVEL SECURITY;

-- Default deny all for non-admin roles (service_role bypasses RLS)
CREATE POLICY "service_role_only_access" 
    ON public.alert_subscribers FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_only_access" 
    ON public.subscriber_watchlist FOR ALL TO service_role USING (true);

-- Grant Access to Data API Roles
GRANT ALL ON TABLE public.alert_subscribers TO service_role;
GRANT ALL ON TABLE public.subscriber_watchlist TO service_role;