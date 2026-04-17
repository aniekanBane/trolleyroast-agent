#!/usr/bin/env python3
"""TrolleyPriceBot welcome sequence runner.

Flow:
1) Fetch active subscribers via ingest endpoint.
2) Send immediate welcome for welcome_sent=false.
3) Send day+3 value email.
4) Send day+7 pro waitlist email (only if wants_pro_alerts=false).

All DB reads/writes go through ingest endpoint actions.
"""

from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from urllib import request, error

ROOT = os.path.dirname(__file__)
ENV_PATH = os.path.join(ROOT, ".env")


def load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k and k not in os.environ:
                os.environ[k] = v


def post_json(url: str, payload: dict, headers: dict, timeout: int = 30):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST", headers=headers)
    with request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(body)
        except Exception:
            return r.status, {"raw": body}


def ingest(action: str, payload: dict):
    url = os.environ["TROLLEYROAST_INGEST_URL"]
    key = os.environ.get("TROLLEYROAST_AGENT_KEY") or os.environ.get("TROLLEYROAST_AGENT")
    if not key:
        raise RuntimeError("Missing TROLLEYROAST_AGENT_KEY/TROLLEYROAST_AGENT")
    headers = {"x-agent-key": key, "Content-Type": "application/json"}
    return post_json(url, {"action": action, "payload": payload}, headers)


def send_resend(to_email: str, subject: str, html: str):
    url = "https://api.resend.com/emails"
    api_key = os.environ["RESEND_API_KEY"]
    payload = {
        "from": "TrolleyRoast <alerts@trolleyroast.app>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return post_json(url, payload, headers)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def run():
    load_env(ENV_PATH)

    # Connectivity check
    h_status, h_body = ingest("health_check", {})
    if h_status != 200 or h_body.get("status") != "ok":
        raise RuntimeError(f"health_check failed: {h_status} {h_body}")

    s_status, s_body = ingest("get_subscribers", {"is_active": True})
    if s_status != 200:
        raise RuntimeError(f"get_subscribers failed: {s_status} {s_body}")

    subscribers = s_body.get("subscribers", [])
    sent = 0
    failed = []

    for sub in subscribers:
        email = sub.get("email")
        if not email:
            continue

        welcome_sent = bool(sub.get("welcome_sent", False))
        welcome_sent_at = sub.get("welcome_sent_at")
        wants_pro = bool(sub.get("wants_pro_alerts", False))
        now = datetime.now(timezone.utc)

        # Stage 1: immediate welcome
        if not welcome_sent:
            subject = "Welcome to TrolleyRoast 🛒"
            html = (
                "<h1 style='font-family:Georgia;color:#1B3A2D'>You're in.</h1>"
                "<p style='font-family:Arial'>Every Monday morning we'll tell you where to shop that week to save the most on your regular items. No noise. Just the deals that matter to your trolley.</p>"
            )
            if wants_pro:
                html += "<p style='font-family:Arial'>You're also on the early list for TrolleyRoast Pro — we'll be in touch.</p>"

            try:
                r_status, _ = send_resend(email, subject, html)
                if r_status not in (200, 201, 202):
                    failed.append({"email": email, "stage": "welcome", "status": r_status})
                    continue
                ingest("update_subscriber", {
                    "email": email,
                    "fields": {"welcome_sent": True, "welcome_sent_at": now_iso(), "welcome_stage": 1}
                })
                sent += 1
                time.sleep(0.5)
            except Exception as e:
                failed.append({"email": email, "stage": "welcome", "error": str(e)})
            continue

        # Stage 2/3 timing requires welcome_sent_at
        if not welcome_sent_at:
            continue

        try:
            w_at = datetime.fromisoformat(welcome_sent_at.replace("Z", "+00:00"))
        except Exception:
            continue

        age_days = (now - w_at).days
        stage = int(sub.get("welcome_stage", 1))

        # Stage 2 (+3 days)
        if age_days >= 3 and stage < 2:
            subject = "This week's biggest price drops across UK supermarkets 🛒"
            html = "<h2 style='font-family:Georgia;color:#1B3A2D'>This week's biggest drops</h2><p style='font-family:Arial'>Your weekly savings summary is ready.</p>"
            try:
                r_status, _ = send_resend(email, subject, html)
                if r_status in (200, 201, 202):
                    ingest("update_subscriber", {"email": email, "fields": {"welcome_stage": 2, "value_email_sent_at": now_iso()}})
                    sent += 1
                else:
                    failed.append({"email": email, "stage": "value", "status": r_status})
                time.sleep(0.5)
            except Exception as e:
                failed.append({"email": email, "stage": "value", "error": str(e)})
            continue

        # Stage 3 (+7 days total, only non-pro)
        if age_days >= 7 and stage < 3 and not wants_pro:
            subject = "Before you do your next shop..."
            html = (
                "<p style='font-family:Arial'>We're building something that'll text you before you leave the house with exactly where to buy your usual items this week for the least money.</p>"
                "<p style='font-family:Arial'><a href='https://trolleyroast.app/pro'>Join the Pro waitlist →</a></p>"
            )
            try:
                r_status, _ = send_resend(email, subject, html)
                if r_status in (200, 201, 202):
                    ingest("update_subscriber", {"email": email, "fields": {"welcome_stage": 3, "pro_waitlist_email_sent_at": now_iso()}})
                    sent += 1
                else:
                    failed.append({"email": email, "stage": "pro_waitlist", "status": r_status})
                time.sleep(0.5)
            except Exception as e:
                failed.append({"email": email, "stage": "pro_waitlist", "error": str(e)})

    try:
        ingest("write_log", {
            "run_type": "welcome_sequence",
            "run_date": datetime.now(timezone.utc).date().isoformat(),
            "items_checked": len(subscribers),
            "prices_updated": 0,
            "alerts_generated": sent,
            "errors": failed,
            "summary": f"welcome sequence run: sent={sent}, failed={len(failed)}"
        })
    except Exception as e:
        failed.append({"stage": "write_log", "error": str(e)})

    print(json.dumps({"ok": True, "subscribers": len(subscribers), "emails_sent": sent, "failed": len(failed)}))


if __name__ == "__main__":
    run()
