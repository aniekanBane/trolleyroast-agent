#!/usr/bin/env python3
import json, os, re, ssl, time, urllib.request
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
REPORT_DIR = Path('/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports')
HOME_URL = 'https://www.lidl.co.uk/'
SUPERMARKET = 'lidl'
MAX_ITEMS = 15
PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
SIZE_RE = re.compile(r'(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|cl|l|litre|litres|pack|pk|x\s?\d+|each|pint|pints))', re.I)
CATS = [
    ('Fresh Fruit & Vegetables', 'https://www.lidl.co.uk/c/fruit-veg/s10023100'),
    ('Bakery, Bread & Baked Goods', 'https://www.lidl.co.uk/c/bakery/s10023103'),
    ('Eggs & staple foods', 'https://www.lidl.co.uk/c/dairy-eggs-chilled/a10026582'),
    ('Cheese & Dairy', 'https://www.lidl.co.uk/c/dairy-eggs-chilled/a10026582'),
    ('Fresh Meat & Poultry', 'https://www.lidl.co.uk/c/fresh-meat-poultry/s10023101'),
]
SEARCH_TERMS = ['milk', 'cheese', 'bread']


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(s):
    m = PRICE_RE.search(s or '')
    return float(m.group(1)) if m else None


def dismiss(page):
    sels = ['#onetrust-accept-btn-handler','button:has-text("Accept")','button:has-text("Allow all")','button:has-text("Accept All")','button[aria-label="Close"]']
    for _ in range(3):
        for sel in sels:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1200):
                    loc.click(timeout=1500)
                    page.wait_for_timeout(500)
            except Exception:
                pass


def extract_script_payloads(page):
    return page.evaluate("""
() => {
  const out = [];
  for (const s of Array.from(document.scripts)) {
    const txt = s.textContent || '';
    if (!txt) continue;
    if (/price|£|product|offer|sku|variant/i.test(txt)) {
      out.push(txt.slice(0, 4000));
    }
    if (out.length >= 10) break;
  }
  return out;
}
""")


def extract_items(page, category):
    raw = page.evaluate("""
() => {
  const abs = (u) => { try { return new URL(u, location.href).href; } catch(e) { return null; } };
  const nodes = Array.from(document.querySelectorAll('a, article, li, div, section'));
  const out = [];
  for (const el of nodes) {
    const txt = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!txt || !txt.includes('£')) continue;
    if (txt.length < 5 || txt.length > 600) continue;
    const a = el.closest('a') || el.querySelector('a[href]');
    out.push({ text: txt.slice(0, 600), href: a && a.getAttribute('href') ? abs(a.getAttribute('href')) : null, cls: el.className || '', tag: el.tagName });
  }
  return out.slice(0, 800);
}
""")
    seen = {}
    for row in raw:
        text = clean(row.get('text'))
        price = parse_price(text)
        if price is None or price < 0.3:
            continue
        name = clean(re.split(r'£\s*\d', text, maxsplit=1)[0])
        if not name or len(name) < 3:
            continue
        size_m = SIZE_RE.search(text)
        size = clean(size_m.group(1)) if size_m else ''
        direct = row.get('href') or page.url
        item = {'item_name': name[:180], 'price': price, 'size_raw': size[:60], 'category': category, 'direct_url': direct}
        seen[(item['item_name'].lower(), item['price'], item['size_raw'])] = item
    return list(seen.values())


def sniff_search(page, report):
    for sel in ['input[type="search"]','input[placeholder*="Search"]','input[aria-label*="Search"]']:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                for term in SEARCH_TERMS:
                    try:
                        loc.click(timeout=1000)
                        loc.fill(term, timeout=2000)
                        page.keyboard.press('Enter')
                        page.wait_for_timeout(2500)
                        dismiss(page)
                        report['search_attempts'].append({'term': term, 'url': page.url})
                        items = extract_items(page, f'search:{term}')
                        if items:
                            return items
                    except Exception as e:
                        report['search_attempts'].append({'term': term, 'error': repr(e)})
                break
        except Exception:
            pass
    return []


def call_ingest(items):
    payload = {'prices': []}
    for x in items:
        payload['prices'].append({
            'supermarket': SUPERMARKET,
            'item_key': re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120],
            'item_name': x['item_name'],
            'price': x['price'],
        })
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': 'upsert_prices', 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={'Content-Type':'application/json','x-agent-key':AGENT_KEY})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode('utf-8')), len(payload['prices'])


def main():
    ts = int(time.time())
    report = {
        'run': 'lidl_surgical_discovery',
        'timestamp': datetime.now().isoformat(),
        'homepage': HOME_URL,
        'route_found': False,
        'route_type': None,
        'route_category': None,
        'final_url': None,
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'nav_attempts': [],
        'search_attempts': [],
        'dom_signals': [],
        'sample_items': []
    }
    all_items = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=CHROME, args=['--disable-http2'])
        page = browser.new_page(viewport={'width': 1440, 'height': 2200})
        page.set_default_timeout(15000)
        page.goto(HOME_URL, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        dismiss(page)

        # Try actual homepage interactions first.
        for sel in ['a:has-text("Our Products")','button:has-text("Our Products")','a:has-text("Fresh Fruit & Vegetables")','a:has-text("Bakery, Bread & Baked Goods")','a:has-text("Eggs & staple foods")','a:has-text("Cheese & Dairy")','a:has-text("Fresh Meat & Poultry")']:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1500):
                    href = None
                    try: href = loc.get_attribute('href')
                    except Exception: pass
                    report['nav_attempts'].append({'selector': sel, 'href': href, 'from': page.url})
                    try:
                        loc.click(timeout=2000)
                    except Exception:
                        if href:
                            page.goto(href if href.startswith('http') else 'https://www.lidl.co.uk'+href, wait_until='domcontentloaded', timeout=20000)
                    page.wait_for_timeout(2000)
                    dismiss(page)
                    break
            except Exception:
                pass

        # Probe direct category routes if homepage interaction does not expose products.
        for category, url in CATS:
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2500)
                dismiss(page)
                for _ in range(3):
                    items = extract_items(page, category)
                    if items:
                        all_items = items
                        report['route_found'] = True
                        report['route_type'] = 'direct_category_or_rendered_dom'
                        report['route_category'] = category
                        break
                    page.mouse.wheel(0, 2200)
                    page.wait_for_timeout(1500)
                payloads = extract_script_payloads(page)
                if payloads:
                    report['dom_signals'].append({'category': category, 'url': page.url, 'payload_snippets': payloads[:2]})
                if all_items:
                    break
                report['nav_attempts'].append({'category': category, 'url': url, 'result': 'no_items'})
            except Exception as e:
                report['nav_attempts'].append({'category': category, 'url': url, 'error': repr(e)})

        if not all_items:
            try:
                page.goto(HOME_URL, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2500)
                dismiss(page)
                all_items = sniff_search(page, report)
                if all_items:
                    report['route_found'] = True
                    report['route_type'] = 'search_surface'
                    report['route_category'] = all_items[0].get('category')
            except Exception as e:
                report['blockers'].append(f'search_exception: {e!r}')

        browser.close()

    all_items = all_items[:MAX_ITEMS]
    report['final_url'] = page.url if 'page' in locals() else None
    report['items_found'] = len(all_items)
    report['sample_items'] = all_items[:10]
    if not all_items:
        report['blockers'].append('No real Lidl product list extracted from homepage/category/search run')
    if all_items and AGENT_KEY:
        try:
            _, n = call_ingest(all_items[:5])
            report['items_ingested'] = n
        except Exception as e:
            report['blockers'].append(f'ingest_exception: {e!r}')
    elif all_items and not AGENT_KEY:
        report['blockers'].append('Missing ingest agent key')

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f'lidl_surgical_discovery_{ts}.json'
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({'report_path': str(out), 'route_found': report['route_found'], 'route_type': report['route_type'], 'route_category': report['route_category'], 'final_url': report['final_url'], 'items_found': report['items_found'], 'items_ingested': report['items_ingested'], 'blockers': report['blockers'], 'sample_items': report['sample_items'][:5]}, indent=2))

if __name__ == '__main__':
    main()
