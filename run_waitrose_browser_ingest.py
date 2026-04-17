#!/usr/bin/env python3
import asyncio
import json
import os
import re
import ssl
import time
import urllib.request
from datetime import datetime
from urllib.parse import urljoin
from playwright.async_api import async_playwright

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', '')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
REPORT_DIR = '/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports'
SUPERMARKET = 'waitrose'

CATEGORIES = {
    'dairy': 'https://www.waitrose.com/ecom/shop/browse/groceries/fresh_and_chilled/milk_butter_and_eggs',
    'bakery': 'https://www.waitrose.com/ecom/shop/browse/groceries/bakery/bread',
    'meat': 'https://www.waitrose.com/ecom/shop/browse/groceries/fresh_and_chilled/fresh_meat',
    'fresh produce': 'https://www.waitrose.com/ecom/shop/browse/groceries/fresh_and_chilled/fresh_fruit',
    'pantry': 'https://www.waitrose.com/ecom/shop/browse/groceries/food_cupboard/rice_pasta_and_pulses',
}

PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
PENCE_RE = re.compile(r'(?<!\d)(\d{1,3})p(?![a-z])', re.I)
SIZE_RE = re.compile(r'^(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|litre|l|cl|pack|s|each|pints?|pt))$', re.I)


def call_ingest(action, payload):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={
        'Content-Type': 'application/json',
        'x-agent-key': AGENT_KEY,
    })
    with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
        return json.loads(response.read().decode('utf-8'))


def clean_text(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(text):
    text = text or ''
    m = PRICE_RE.search(text)
    if m:
        return float(m.group(1))
    m = PENCE_RE.search(text)
    if m:
        return round(int(m.group(1)) / 100.0, 2)
    return None


def is_valid_item(item):
    price = item.get('price')
    name = (item.get('item_name') or '').lower()
    size = (item.get('size_raw') or '').lower()
    if price is None:
        return False, 'missing_price'
    if price < 0.40:
        # obvious unit-price contamination unless genuinely low edge-case small item
        if any(k in name for k in ['lemon', 'lime', 'banana', 'onion', 'garlic', 'roll']) or 'each' in size:
            return True, None
        return False, 'rejected_unit_price_contamination'
    if len(item.get('item_name') or '') < 3:
        return False, 'bad_name'
    return True, None


async def extract_cards(page, category):
    results = []
    articles = await page.locator('article').all()
    for article in articles:
        try:
            raw_text = await article.inner_text()
            text = clean_text(raw_text)
            if 'view product details for' not in text or 'Item price' not in text:
                continue
            lines = [clean_text(x) for x in raw_text.splitlines() if clean_text(x)]
            name = None
            size = None
            price = None
            for i, line in enumerate(lines):
                if line.lower() == 'view product details for' and i + 1 < len(lines):
                    name = lines[i + 1]
                if line.lower() == 'item price' and i + 1 < len(lines):
                    price = parse_price(lines[i + 1])
            if not name:
                for i, line in enumerate(lines):
                    if ' in trolley.' in line.lower() and i + 1 < len(lines):
                        name = lines[i + 1]
                        break
            for line in lines:
                if SIZE_RE.match(line) or any(tok in line.lower() for tok in ['litre', 'pints', 'g', 'kg', 'ml', 'each']) and any(ch.isdigit() for ch in line):
                    size = line
                    break
            href = None
            links = await article.locator('a').evaluate_all("els => els.map(a => a.href).filter(Boolean)")
            for l in links:
                if '/ecom/products/' in l or '/ecom/shop/product/' in l or '/shop/product/' in l:
                    href = l
                    break
            if not href and links:
                href = links[0]
            item = {
                'supermarket': SUPERMARKET,
                'item_name': clean_text(name),
                'price': price,
                'size_raw': clean_text(size),
                'category': category,
                'direct_url': href,
            }
            ok, reason = is_valid_item(item)
            if ok:
                results.append(item)
        except Exception:
            continue
    return results


async def scrape_category(context, category, url):
    page = await context.new_page()
    page.set_default_timeout(20000)
    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
    await page.wait_for_timeout(5000)
    seen = {}
    stagnant = 0
    for _ in range(10):
        items = await extract_cards(page, category)
        for item in items:
            key = (item['item_name'], item['price'], item.get('size_raw') or '')
            seen[key] = item
        before = len(seen)
        await page.mouse.wheel(0, 2600)
        await page.wait_for_timeout(2500)
        items = await extract_cards(page, category)
        for item in items:
            key = (item['item_name'], item['price'], item.get('size_raw') or '')
            seen[key] = item
        if len(seen) == before:
            stagnant += 1
        else:
            stagnant = 0
        if stagnant >= 2:
            break
    await page.close()
    return list(seen.values())


async def run():
    ts = int(time.time())
    report = {
        'run': 'waitrose_browser_ingest',
        'timestamp': datetime.now().isoformat(),
        'supermarket': SUPERMARKET,
        'categories': {},
        'summary': {},
        'blockers': [],
    }
    all_items = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=CHROME, args=['--disable-http2'])
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 2200},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await page.goto('https://www.waitrose.com/', wait_until='domcontentloaded', timeout=20000)
        try:
            await page.locator('#onetrust-reject-all-handler').click(timeout=5000)
        except Exception:
            pass
        await page.close()
        for category, url in CATEGORIES.items():
            try:
                items = await scrape_category(context, category, url)
                report['categories'][category] = {'found': len(items), 'url': url}
                all_items.extend(items)
            except Exception as e:
                report['categories'][category] = {'found': 0, 'url': url, 'error': repr(e)}
                report['blockers'].append(f'{category}: {e!r}')
        await browser.close()

    # dedupe across categories
    deduped = {}
    for item in all_items:
        key = (item['item_name'], item['price'], item.get('size_raw') or '')
        deduped[key] = item
    items = list(deduped.values())

    ingested = 0
    ingest_errors = []
    batch_size = 25
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        payload = {'prices': [
            {
                'supermarket': x['supermarket'],
                'item_key': re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120],
                'item_name': x['item_name'],
                'price': x['price'],
            }
            for x in batch
        ]}
        try:
            res = call_ingest('upsert_prices', payload)
            if 'error' in res:
                ingest_errors.append(res['error'])
            else:
                ingested += len(batch)
        except Exception as e:
            ingest_errors.append(repr(e))

    report['summary'] = {
        'total_items_found': len(items),
        'total_ingested': ingested,
        'ingest_errors': len(ingest_errors),
    }
    report['sample_items'] = items[:20]
    report['ingest_error_samples'] = ingest_errors[:10]

    out = os.path.join(REPORT_DIR, f'waitrose_browser_ingest_{ts}.json')
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)
    print(json.dumps({'report_path': out, **report['summary']}))


if __name__ == '__main__':
    if not AGENT_KEY:
        raise SystemExit('Missing TROLLEYROAST_AGENT_KEY')
    asyncio.run(run())
