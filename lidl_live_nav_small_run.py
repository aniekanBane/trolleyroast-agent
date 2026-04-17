#!/usr/bin/env python3
import json, os, re, ssl, time, urllib.request
from datetime import datetime
from pathlib import Path
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
BAD_NAME = {'add', 'remove', 'favourite', 'favorite', 'buy now', 'shop now'}
CATEGORIES = ['Cheese & Dairy', 'Fresh Fruit & Vegetables', 'Bakery, Bread & Baked Goods', 'Fresh Meat & Poultry', 'Chilled Fish & Seafood', 'Eggs & staple foods']


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


def dismiss_overlays(page):
    selectors = [
        '#onetrust-accept-btn-handler',
        'button:has-text("Accept")',
        'button:has-text("Allow all")',
        'button:has-text("Accept All")',
        'button:has-text("I agree")',
        'button:has-text("Got it")',
        'button[aria-label="Close"]',
        '[data-testid="modal-close-button"]',
    ]
    for _ in range(3):
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1200):
                    loc.click(timeout=1500)
                    page.wait_for_timeout(700)
            except Exception:
                pass


def visible_texts(page):
    try:
        return page.evaluate("""
() => Array.from(document.querySelectorAll('a,button,h1,h2,h3,[role="button"]'))
  .map(el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim())
  .filter(Boolean)
  .slice(0, 300)
""")
    except Exception:
        return []


def open_shop_surface(page, report):
    candidates = [
        'a:has-text("Browse our products")',
        'a:has-text("Browse products")',
        'a:has-text("Our products")',
        'button:has-text("Our products")',
        'a:has-text("In Store")',
        'button:has-text("In Store")',
        'a:has-text("Food Cupboard")',
        'a:has-text("Fruit & veg")',
        'button:has-text("Browse our products")',
        'button:has-text("Browse products")',
        'a[href*="/c/"]',
        'a[href*="/products"]',
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                href = loc.get_attribute('href') if 'a' in sel else None
                if href and ('leaflet' in href or 'online-leaflets' in href):
                    report['nav_attempts'].append({'type': 'shop_surface_skip_leaflet', 'selector': sel, 'href': href})
                    continue
                report['nav_attempts'].append({'type': 'shop_surface', 'selector': sel, 'href': href})
                with page.expect_navigation(wait_until='domcontentloaded', timeout=15000):
                    loc.click(timeout=2000)
                page.wait_for_timeout(2000)
                dismiss_overlays(page)
                if 'online-leaflets' in page.url or 'leaflet' in page.url:
                    report['nav_attempts'].append({'type': 'landed_leaflet', 'url': page.url})
                    try:
                        page.go_back(wait_until='domcontentloaded', timeout=10000)
                        page.wait_for_timeout(1500)
                        dismiss_overlays(page)
                    except Exception:
                        pass
                    continue
                return True
        except Exception:
            continue
    return False


def navigate_category(page, report):
    for name in CATEGORIES:
        selectors = [
            f'a:has-text("{name}")',
            f'button:has-text("{name}")',
            f'[role="link"]:has-text("{name}")',
            f'[role="button"]:has-text("{name}")',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1200):
                    href = None
                    try:
                        href = loc.get_attribute('href')
                    except Exception:
                        pass
                    report['nav_attempts'].append({'type': 'category_click', 'category': name, 'selector': sel, 'href': href})
                    if href:
                        with page.expect_navigation(wait_until='domcontentloaded', timeout=15000):
                            loc.click(timeout=2000)
                    else:
                        loc.click(timeout=2000)
                        page.wait_for_timeout(2000)
                    dismiss_overlays(page)
                    page.wait_for_timeout(1500)
                    return name
            except Exception:
                pass
    return None


def extract_items(page, category_guess):
    raw = page.evaluate("""
() => {
  const abs = (u) => { try { return new URL(u, location.href).href; } catch(e) { return null; } };
  const nodes = Array.from(document.querySelectorAll('a, article, li, div'));
  const out = [];
  for (const el of nodes) {
    const txt = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!txt || !txt.includes('£')) continue;
    if (txt.length < 6 || txt.length > 500) continue;
    const a = el.closest('a') || el.querySelector('a[href]');
    const href = a && a.getAttribute('href') ? abs(a.getAttribute('href')) : null;
    out.push({text: txt, href});
  }
  return out.slice(0, 500);
}
""")
    seen = {}
    for row in raw:
        text = clean(row.get('text'))
        price = parse_price(text)
        if price is None or price <= 0:
            continue
        name = clean(re.split(r'£\s*\d', text, maxsplit=1)[0])
        if not name or name.lower() in BAD_NAME or len(name) < 4:
            continue
        if name.count('£'):
            continue
        size_m = SIZE_RE.search(text)
        size_raw = clean(size_m.group(1)) if size_m else ''
        item = {
            'item_name': name[:180],
            'price': price,
            'size_raw': size_raw[:60],
            'category': category_guess or '',
            'direct_url': row.get('href') or page.url,
        }
        key = (item['item_name'].lower(), item['price'], item['size_raw'])
        seen[key] = item
    return list(seen.values())


def classify_valid(items):
    valid = []
    for item in items:
        url = item['direct_url'] or ''
        if not url.startswith('http'):
            continue
        if item['price'] < 0.3:
            continue
        valid.append(item)
    return valid


def small_ingest(items):
    payload = {'prices': []}
    for x in items:
        payload['prices'].append({
            'supermarket': SUPERMARKET,
            'item_key': re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120],
            'item_name': x['item_name'],
            'price': x['price'],
        })
    return call_ingest('upsert_prices', payload), len(payload['prices'])


def main():
    ts = int(time.time())
    report = {
        'run': 'lidl_live_nav_small_run',
        'timestamp': datetime.now().isoformat(),
        'supermarket': SUPERMARKET,
        'start_url': HOME_URL,
        'final_url': None,
        'live_route_found': False,
        'route_category': None,
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'nav_attempts': [],
        'visible_text_sample': [],
        'sample_items': []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=CHROME, args=['--disable-http2'])
        page = browser.new_page(viewport={'width': 1440, 'height': 2200})
        page.set_default_timeout(15000)
        page.goto(HOME_URL, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3500)
        dismiss_overlays(page)
        report['visible_text_sample'] = visible_texts(page)[:40]

        opened = open_shop_surface(page, report)
        if not opened:
            try:
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(1200)
                dismiss_overlays(page)
                opened = open_shop_surface(page, report)
            except Exception:
                pass

        chosen_category = None
        if opened:
            chosen_category = navigate_category(page, report)
            if not chosen_category:
                for _ in range(3):
                    page.mouse.wheel(0, 1600)
                    page.wait_for_timeout(1200)
                    dismiss_overlays(page)
                    chosen_category = navigate_category(page, report)
                    if chosen_category:
                        break

        items = []
        if opened and chosen_category:
            for _ in range(5):
                extracted = extract_items(page, chosen_category)
                if extracted:
                    items = extracted
                if len(items) >= MAX_ITEMS:
                    break
                page.mouse.wheel(0, 2200)
                page.wait_for_timeout(1800)
                dismiss_overlays(page)
        else:
            report['blockers'].append('Could not reach live Lidl product discovery surface via homepage navigation')

        items = classify_valid(items)[:MAX_ITEMS]
        report['final_url'] = page.url
        report['route_category'] = chosen_category
        report['live_route_found'] = bool(opened and chosen_category and items)
        report['items_found'] = len(items)
        report['sample_items'] = items[:10]

        if items and AGENT_KEY:
            try:
                _, ingested = small_ingest(items[:10])
                report['items_ingested'] = ingested
            except Exception as e:
                report['blockers'].append(f'ingest_exception: {e!r}')
        elif items and not AGENT_KEY:
            report['blockers'].append('Missing TROLLEYROAST_AGENT_KEY/TROLLEYROAST_AGENT for ingest')

        browser.close()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f'lidl_live_nav_small_run_{ts}.json'
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({'report_path': str(out), 'live_route_found': report['live_route_found'], 'final_url': report['final_url'], 'route_category': report['route_category'], 'items_found': report['items_found'], 'items_ingested': report['items_ingested'], 'blockers': report['blockers'], 'sample_items': report['sample_items'][:5]}, indent=2))

if __name__ == '__main__':
    main()
