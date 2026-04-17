#!/usr/bin/env python3
"""Test query capabilities of ingest endpoint"""
import json
import urllib.request
import ssl
import os

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def test_action(action, payload):
    """Test an action on the ingest endpoint"""
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={
        'Content-Type': 'application/json',
        'x-agent-key': AGENT_KEY
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except Exception as e:
        return {'error': str(e)}

print("Testing available actions...", flush=True)

# Test health check
print("\n1. Testing health_check...", flush=True)
result = test_action('health_check', {})
print(f"Result: {json.dumps(result, indent=2)}", flush=True)

# Test get_items
print("\n2. Testing get_items for Tesco...", flush=True)
result = test_action('get_items', {'supermarket': 'tesco', 'limit': 5})
print(f"Result: {json.dumps(result, indent=2)}", flush=True)

# Test list_actions
print("\n3. Testing list_actions...", flush=True)
result = test_action('list_actions', {})
print(f"Result: {json.dumps(result, indent=2)}", flush=True)
