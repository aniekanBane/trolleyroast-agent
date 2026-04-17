#!/usr/bin/env python3
import json, os, re, ssl, time, urllib.request
from datetime import datetime
from playwright.sync_api import sync_playwright

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
REPORT_DIR = '/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports'
SUPERMARKET = 'lidl'
CATEGORY = 'dairy'
MAX_ITEMS = 15
START_URL = 'https://www.lidl.co.uk/c/dairy-eggs-chilled/a10026582'
PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
SIZE_RE = re.compile(r'(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|cl|l|litre|litres|pack|pk|each|pint|pints))', re.I)
KEYWORDS = ('milk','butter','cheese','yogurt','yoghurt','cream','custard','kefir','mozzarella','cheddar','brie','feta','halloumi')


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(s):
    m = PRICE_RE.search(s or '')
    return float(m.group(1)) if m else None


def call_ingest(action, payload):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={'Content-Type': 'application/json', 'x-agent-key': AGENT_KEY})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))


def is_valid(item):
    price = item.get('price')
    if price is None or price < 0.40:
        return False
    name = (item.get('item_name') or '').lower()
    return any(k in name for k in KEYWORDS)


def extract_cards(page):
    raw = page.evaluate("""
() => {
  const out = [];
  const nodes = Array.from(document.querySelectorAll('a, article, li, div'));
  for (const el of nodes) {
    const txt = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!txt || !txt.includes('£')) continue;
    if (!/(milk|butter|cheese|yogurt|yoghurt|cream|custard|kefir|mozzarella|cheddar|brie|feta|halloumi)/i.test(txt)) continue;
    const link = el.closest('a') || el.querySelector('a[href]');
    out.push({ text: txt.slice(0, 500), href: link ? link.href : null });
  }
  return out.slice(0, 400);
}
""")
    dedup = {}
    for row in raw:
        text = clean(row.get('text'))
        price = parse_price(text)
        if price is None:
            continue
        msize = SIZE_RE.search(text)
        size = clean(msize.group(1)) if msize else ''
        name = clean(re.split(r'£\s*\d', text, maxsplit=1)[0])[:180]
        item = {
            'supermarket': SUPERMARKET,
            'item_name': name,
            'price': price,
            'size_raw': size,
            'category': CATEGORY,
            'direct_url': row.get('href') or START_URL,
        }
        if is_valid(item) and len(name) >= 4:
            dedup[(name.lower(), price, size)] = item
    return list(dedup.values())


def main():
    ts = int(time.time())
    report = {
        'run': 'lidl_dairy_short_run',
        'timestamp': datetime.now().isoformat(),
        'supermarket': SUPERMARKET,
        'category': CATEGORY,
        'source_url': START_URL,
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'sample_items': []
    }
    found = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME, args=['--disable-http2'])
        page = browser.new_page(viewport={'width': 1400, 'height': 2200})
        page.set_default_timeout(15000)
        page.goto(START_URL, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3500)
        for sel in ['button:has-text("Accept")', 'button:has-text("Allow all")', 'button:has-text("Agree")', '#onetrust-accept-btn-handler']:
            try:
                page.locator(sel).first.click(timeout=2000)
                page.wait_for_timeout(1000)
                break
            except Exception:
                pass
        stagnant = 0
        for _ in range(8):
            before = len(found)
            dedup = {(x['item_name'].lower(), x['price'], x['size_raw']): x for x in found}
            for x in extract_cards(page):
                dedup[(x['item_name'].lower(), x['price'], x['size_raw'])] = x
            found = list(dedup.values())[:MAX_ITEMS]
            if len(found) == before:
                stagnant += 1
            else:
                stagnant = 0
            if len(found) >= MAX_ITEMS or stagnant >= 2:
                break
            page.mouse.wheel(0, 2600)
            page.wait_for_timeout(2200)
        browser.close()
    report['items_found'] = len(found)
    report['sample_items'] = found[:10]
    if found:
        payload = {'prices': []}
        for x in found:
            payload['prices'].append({
                'supermarket': SUPERMARKET,
                'item_key': re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120],
                'item_name': x['item_name'],
                'price': x['price'],
            })
        try:
            res = call_ingest('upsert_prices', payload)
            if isinstance(res, dict) and res.get('error'):
                report['blockers'].append(f"ingest_error: {res['error']}")
            else:
                report['items_ingested'] = len(payload['prices'])
        except Exception as e:
            report['blockers'].append(f'ingest_exception: {e!r}')
    else:
        report['blockers'].append('No Lidl dairy items extracted')
    out = os.path.join(REPORT_DIR, f'lidl_dairy_short_run_{ts}.json')
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)
    print(json.dumps({'report_path': out, 'items_found': report['items_found'], 'items_ingested': report['items_ingested'], 'blockers': report['blockers'], 'sample_items': report['sample_items'][:5]}))

if __name__ == '__main__':
    main()
