#!/usr/bin/env python3
import asyncio, json, os, re, ssl, time, urllib.request
from datetime import datetime
from playwright.async_api import async_playwright

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
REPORT_DIR = '/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports'
SUPERMARKET = 'aldi'
MAX_ITEMS = 15
PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
SIZE_RE = re.compile(r'\b(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|l|litre|litres|x\s*\d+|pack|pk|pints?|pt|each))\b', re.I)


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(text):
    m = PRICE_RE.search(text or '')
    return float(m.group(1)) if m else None


def valid(item):
    p = item.get('price')
    if p is None:
        return False, 'missing_price'
    if p < 0.40:
        return False, 'rejected_low_price_contamination'
    if not item.get('item_name') or len(item['item_name']) < 3:
        return False, 'bad_name'
    if not item.get('direct_url'):
        return False, 'missing_url'
    return True, None


def call_ingest(action, payload):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={'Content-Type': 'application/json', 'x-agent-key': AGENT_KEY})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
        return json.loads(response.read().decode('utf-8'))


async def run():
    ts = int(time.time())
    report = {
        'run': 'aldi_dairy_short_run',
        'timestamp': datetime.now().isoformat(),
        'supermarket': SUPERMARKET,
        'category': 'dairy',
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'sample_items': []
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=CHROME, args=['--disable-http2'])
        context = await browser.new_context(viewport={'width': 1440, 'height': 2200}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        page = await context.new_page()
        page.set_default_timeout(15000)
        await page.goto('https://www.aldi.co.uk/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)

        for sel in ['#onetrust-accept-btn-handler', '#onetrust-reject-all-handler', 'button:has-text("Accept All")', 'button:has-text("Accept")']:
            try:
                await page.locator(sel).click(timeout=2000)
                break
            except Exception:
                pass

        category_urls = [
            'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001',
            'https://www.aldi.co.uk/products/chilled-food/dairy/k/1588161416978051002',
            'https://www.aldi.co.uk/products/chilled-food/cheese/k/1588161416978051004',
            'https://www.aldi.co.uk/products/chilled-food/yogurts/k/1588161416978051005',
        ]

        items = {}
        for url in category_urls:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3500)
            body = clean(await page.locator('body').inner_text())
            lines = [clean(x) for x in body.split('\n') if clean(x)]
            i = 0
            while i < len(lines) - 3 and len(items) < MAX_ITEMS:
                brand = lines[i]
                name = lines[i + 1] if i + 1 < len(lines) else ''
                size = lines[i + 2] if i + 2 < len(lines) else ''
                unit = lines[i + 3] if i + 3 < len(lines) else ''
                price_line = lines[i + 4] if i + 4 < len(lines) else ''
                if price_line.startswith('£') and size and any(c.isdigit() for c in size):
                    full_name = clean(f'{brand} {name}')
                    item = {
                        'supermarket': SUPERMARKET,
                        'item_name': full_name[:180],
                        'price': parse_price(price_line),
                        'size_raw': size,
                        'category': 'dairy',
                        'direct_url': url,
                    }
                    low = full_name.lower()
                    if any(k in low for k in ['milk', 'butter', 'cheese', 'yogurt', 'yoghurt', 'cream', 'mozzarella', 'cheddar', 'brie', 'feta', 'halloumi', 'custard']):
                        ok, reason = valid(item)
                        if ok:
                            key = (item['item_name'].lower(), item['price'], item['size_raw'])
                            items[key] = item
                    i += 5
                else:
                    i += 1
            if len(items) >= MAX_ITEMS:
                break

        found = list(items.values())[:MAX_ITEMS]
        report['items_found'] = len(found)
        report['sample_items'] = found[:10]
        await browser.close()

    if not found:
        report['blockers'].append('No Aldi dairy items extracted from rendered search results')
    else:
        payload = {'prices': []}
        for x in found:
            item_key = re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120]
            payload['prices'].append({
                'supermarket': x['supermarket'],
                'item_key': item_key,
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

    out = os.path.join(REPORT_DIR, f'aldi_dairy_short_run_{ts}.json')
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)
    print(json.dumps({'report_path': out, 'items_found': report['items_found'], 'items_ingested': report['items_ingested'], 'blockers': report['blockers']}))


if __name__ == '__main__':
    asyncio.run(run())
