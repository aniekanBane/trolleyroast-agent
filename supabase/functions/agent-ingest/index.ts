// Setup type definitions for built-in Supabase Runtime APIs
import "@supabase/functions-js/edge-runtime.d.ts";
import { withSupabase } from "@supabase/server";
import { handleAction, IngestAction } from "./actions.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "apikey, content-type, x-agent-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  Vary: "Access-Control-Request-Headers",
};

const AGENT_KEY = Deno.env.get("AGENT_KEY");
if (!AGENT_KEY) {
  console.error("AGENT_KEY is not set.");
}

interface IngestRequest {
  action: IngestAction;
  payload: Record<string, unknown>;
}

export default {
  fetch: withSupabase({ auth: "publishable" }, async (req, ctx) => {
    if (req.method === "OPTIONS") {
      return new Response("ok", { headers: corsHeaders });
    }

    const agentKey = req.headers.get("x-agent-key");
    if (!agentKey || agentKey !== AGENT_KEY) {
      return new Response(
        JSON.stringify({ error: "Unauthorized" }),
        {
          status: 401,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    let body: IngestRequest;
    try {
      body = await req.json();
    } catch {
      return new Response(
        JSON.stringify({ error: "Invalid JSON" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    const { action, payload } = body;
    try {
      const result = await handleAction(action, payload, ctx.supabaseAdmin);
      return new Response(
        JSON.stringify(result),
        {
          status: 200,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    } catch (err: unknown) {
      console.error(`Action ${action} failed:`, err);
      let errorMessage = "An unknown error occurred";
      let details: string | undefined = undefined;

      if (err && typeof err === "object") {
        const errObj = err as Record<string, unknown>;
        if (typeof errObj.message === "string") {
          errorMessage = errObj.message;
        } else if (typeof errObj.messageText === "string") {
          errorMessage = errObj.messageText;
        } else {
          errorMessage = JSON.stringify(errObj);
        }

        if (typeof errObj.details === "string") {
          details = errObj.details;
        }
      } else {
        errorMessage = String(err);
      }

      return new Response(
        JSON.stringify({ error: errorMessage, details }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }
  }),
};
