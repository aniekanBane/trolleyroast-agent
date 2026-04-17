import os
import urllib.request
import json
import ssl

CRAWLER_ENDPOINT = os.getenv('CRAWLER_ENDPOINT', 'http://127.0.0.1:3000')
CRAWLER_API_KEY = os.getenv('CRAWLER_API_KEY', 'fc-key-trolley-roast-secret-123')

def crawl(url, render=True):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # Try different auth schemes
    # 1. Bearer token (what we tried, got 401)
    # 2. X-API-Key header (often used in simple local setups)
    # 3. Just the key as 'Authorization' (though less common)
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': f'{CRAWLER_API_KEY}'
    }
    payload = json.dumps({'url': url, 'render': render}).encode('utf-8')
    req = urllib.request.Request(f"{CRAWLER_ENDPOINT}/v1/crawl", data=payload, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}
