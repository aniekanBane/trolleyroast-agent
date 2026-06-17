import { SupabaseClient } from "@supabase/supabase-js";

export enum IngestAction {
  HEALTH_CHECK = "health_check",
  UPSERT_PRICES = "upsert_prices",
  GET_PRICES = "get_prices",
  UPDATE_SUBSCRIBER = "update_subscriber",
  GET_SUBCRIBERS = "get_subscribers",
  INSERT_WORKER_LOG = "insert_worker_log",
}

export async function handleAction(
  action: IngestAction,
  payload: Record<string, unknown>,
  supabase: SupabaseClient,
): Promise<unknown> {
  switch (action) {
    case IngestAction.HEALTH_CHECK:
      return { status: "Healthy" };
    case IngestAction.UPSERT_PRICES:
      return await upsertPrices(supabase, payload);
    case IngestAction.GET_PRICES:
      return await getPrices(supabase, payload);
    case IngestAction.UPDATE_SUBSCRIBER:
      return await updateSubscriber(supabase, payload);
    case IngestAction.GET_SUBCRIBERS:
      return await getSubcribers(supabase, payload);
    case IngestAction.INSERT_WORKER_LOG:
      return insertWorkerLog(supabase, payload);
    default:
      throw new Error(`Unknown action: ${action}`);
  }
}

async function upsertPrices(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
) {
  const prices = payload.items as Array<{
    item_key: string;
    item_name: string;
    item_category: string;
    store: string;
    price_gbp: number;
  }>;

  const { data, error } = await supabase
    .from("price_snapshots")
    .upsert(prices, { onConflict: "item_key,store,observed_date" })
    .select();

  if (error) throw error;

  return { count: data?.length ?? 0 };
}

async function getPrices(
  supabase: SupabaseClient,
  filter: Record<string, unknown>,
) {
  const itemKey = filter.item_key as string | undefined;
  const store = filter.store as string | undefined;

  let query = supabase.from("price_snapshots").select();

  if (itemKey) query = query.eq("item_key", itemKey);

  if (store) query = query.eq("store", store);

  const { data, error } = await query;

  if (error) throw error;

  if (!data) {
    return { prices: [] };
  }

  return { prices: data };
}

async function updateSubscriber(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
) {
  const subscribers = payload.subscribers as Array<{
    email_address: string;
    welcome_sent: boolean;
    welcome_sent_at: string | null;
  }>;

  const { data, error } = await supabase
    .from("alert_subscribers")
    .upsert(subscribers, { onConflict: "email_address" })
    .select();

  if (error) throw error;

  return { count: data?.length ?? 0 };
}

async function getSubcribers(
  supabase: SupabaseClient,
  filter: Record<string, unknown>,
) {
  const isActive = filter.is_active as boolean | undefined;

  let query = supabase.from("alert_subscribers").select();

  if (isActive !== undefined) {
    query = query.eq("is_active", isActive);
  }

  const { data, error } = await query;

  if (error) throw error;

  if (!data) {
    return { subcribers: [] };
  }

  const subscribers = data.map((subscriber) => {
    return {
      email_address: subscriber.email_address,
      name: subscriber.full_name,
      welcome_sent: subscriber.welcome_sent,
      welcome_sent_at: subscriber.welcome_sent_at,
      wants_pro: subscriber.wants_pro,
    };
  });
  return { subscribers };
}

async function insertWorkerLog(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
) {
  const log = {
    run_type: payload.run_type as string,
    run_date: payload.run_date as string,
    items_checked: payload.items_checked as number,
    prices_updated: payload.prices_updated as number,
    alerts_generated: payload.alerts_generated as number,
    errors: payload.errors as Record<string, unknown> | undefined,
    summary: payload.summary as string,
  };

  const { data, error } = await supabase
    .from("worker_audit_logs")
    .insert(log)
    .select();

  if (error) throw error;

  return { logId: data?.at(-1)?.id };
}
