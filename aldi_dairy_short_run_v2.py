#!/usr/bin/env python3
import json, os, re, ssl, time, urllib.request
from datetime import datetime
from playwright.sync_api import sync_playwright

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
REPORT_DIR = '/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports'
PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
SIZE_LINE_RE = re.compile(r'^(\d+(?:\.\d+)?\s*(?:L|G|KG|ML))$', re.I)
KEYWORDS = ['milk','butter','cheese','yogurt','yoghurt','cream','mozzarella','cheddar','brie','feta','halloumi','custard']
URLS = [
    'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001',
    'https://www.aldi.co.uk/products/chilled-food/dairy/k/1588161416978051002',
    'https://www.aldi.co.uk/products/chilled-food/cheese/k/1588161416978051004',
    'https://www.aldi.co.uk/products/chilled-food/yogurts/k/1588161416978051005',
]
MAX_ITEMS = 15


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(s):
    m = PRICE_RE.search(s or '')
    return float(m.group(1)) if m else None


def call_ingest(action, payload):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={'Content-Type': 'application/json', 'x-agent-key': AGENT_KEY})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))


def extract_from_page(page, url):
    text = page.locator('body').inner_text()
    lines = [clean(x) for x in text.splitlines() if clean(x)]
    out = []
    for i in range(len(lines) - 4):
        brand, name, size, unit, price_line = lines[i:i+5]
        low = f'{brand} {name}'.lower()
        if not any(k in low for k in KEYWORDS):
            continue
        if not SIZE_LINE_RE.match(size):
            continue
        if not price_line.startswith('£'):
            continue
        price = parse_price(price_line)
        if price is None or price < 0.40:
            continue
        out.append({
            'supermarket': 'aldi',
            'item_name': clean(f'{brand} {name}')[:180],
            'price': price,
            'size_raw': size,
            'category': 'dairy',
            'direct_url': url,
        })
    dedup = {}
    for x in out:
        dedup[(x['item_name'].lower(), x['price'], x['size_raw'])] = x
    return list(dedup.values())


def main():
    ts = int(time.time())
    report = {
        'run': 'aldi_dairy_short_run',
        'timestamp': datetime.now().isoformat(),
        'supermarket': 'aldi',
        'category': 'dairy',
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'sample_items': []
    }
    found = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME, args=['--disable-http2'])
        page = browser.new_page(viewport={'width': 1280, 'height': 1800})
        page.set_default_timeout(12000)
        for url in URLS:
            page.goto(url, wait_until='domcontentloaded', timeout=25000)
            page.wait_for_timeout(2500)
            found.extend(extract_from_page(page, url))
            if len(found) >= MAX_ITEMS:
                break
        browser.close()
    dedup = {}
    for x in found:
        dedup[(x['item_name'].lower(), x['price'], x['size_raw'])] = x
    found = list(dedup.values())[:MAX_ITEMS]
    report['items_found'] = len(found)
    report['sample_items'] = found[:10]
    if found:
        payload = {'prices': []}
        for x in found:
            payload['prices'].append({
                'supermarket': 'aldi',
                'item_key': re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120],
                'item_name': x['item_name'],
                'price': x['price'],
            })
        try:
            res = call_ingest('upsert_prices', payload)
            if 'error' in res:
                report['blockers'].append(f"ingest_error: {res['error']}")
            else:
                report['items_ingested'] = len(payload['prices'])
        except Exception as e:
            report['blockers'].append(f'ingest_exception: {e!r}')
    else:
        report['blockers'].append('No Aldi dairy items extracted')
    out = os.path.join(REPORT_DIR, f'aldi_dairy_short_run_{ts}.json')
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)
    print(json.dumps({'report_path': out, 'items_found': report['items_found'], 'items_ingested': report['items_ingested'], 'blockers': report['blockers']}))

if __name__ == '__main__':
    main()
