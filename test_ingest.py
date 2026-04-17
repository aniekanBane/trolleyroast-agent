#!/usr/bin/env python3
"""Test ingest endpoint"""
import json
import urllib.request
import ssl
import os

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))

print(f"Testing ingest endpoint: {INGEST_URL}", flush=True)
print(f"Using agent key: {AGENT_KEY[:10]}...", flush=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

data = json.dumps({'action': 'health_check', 'payload': {}}).encode('utf-8')
req = urllib.request.Request(INGEST_URL, data=data, headers={
    'Content-Type': 'application/json',
    'x-agent-key': AGENT_KEY
})

print("Sending health check...", flush=True)
try:
    with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
        result = response.read().decode('utf-8')
        print(f"Response: {result}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
