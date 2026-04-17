#!/usr/bin/env python3
import json, os, re, ssl, time, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path('/Users/tosin/.openclaw/workspace-main/trolleyroast-agent')
ENV_PATH = BASE_DIR / '.env'
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
REPORT_DIR = Path('/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports')
SUPERMARKET = 'lidl'
SEARCH_TERMS = [
    'semi skimmed milk',
    'whole milk',
    'cheddar',
    'greek yoghurt',
    'chicken breast',
    'wholemeal bread',
]
MAX_DETAIL_PAGES = 10
PER_TERM_TARGET = 2
CHUNK_SIZE = 2
PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
SIZE_RE = re.compile(r'(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|cl|l|litre|litres|pack|pk|x\s?\d+|each|pint|pints))', re.I)
PRODUCT_URL_RE = re.compile(r'https://www\.lidl\.co\.uk/p/[^\s\"#]+')
TERM_CATEGORY = {
    'semi skimmed milk': 'Cheese & Dairy',
    'whole milk': 'Cheese & Dairy',
    'cheddar': 'Cheese & Dairy',
    'greek yoghurt': 'Cheese & Dairy',
    'chicken breast': 'Fresh Meat & Poultry',
    'wholemeal bread': 'Bakery, Bread & Baked Goods',
}
TERM_REQUIRE = {
    'semi skimmed milk': ['semi skimmed'],
    'whole milk': ['whole milk', 'whole fresh milk'],
    'cheddar': ['cheddar'],
    'greek yoghurt': ['greek yoghurt', 'greek-style yoghurt', 'greek yogurt', 'greek-style yogurt'],
    'chicken breast': ['chicken breast', 'chicken breast fillet', 'chicken fillets'],
    'wholemeal bread': ['wholemeal bread', 'wholemeal loaf'],
}
GLOBAL_EXCLUDE = [
    'easter', 'bunny', 'bunnies', 'mini eggs', 'egg hunt', 'chocolate', 'dessert', 'snack', 'oatcakes',
    'biscuits', 'slices', 'pie', 'balmoral', 'corn snacks', 'flavoured corn', 'protein bar', 'ice cream',
    'cereal', 'granola', 'crisps', 'cake', 'hot cross', 'seasonal', 'limited edition', 'filled', 'mister choc',
    'maltesers', 'cadbury', 'after eight'
]
TERM_EXCLUDE = {
    'semi skimmed milk': ['whole milk', 'chocolate', 'dessert'],
    'whole milk': ['semi skimmed', 'chocolate', 'dessert'],
    'cheddar': ['cheese balls', 'oatcakes', 'snacks', 'flavour', 'flavoured'],
    'greek yoghurt': ['slices', 'bars', 'dessert'],
    'chicken breast': ['pie', 'curry', 'balmoral', 'wings', 'nuggets', 'kiev'],
    'wholemeal bread': ['breadcrumbs', 'breaded', 'hot cross'],
}


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(s):
    m = PRICE_RE.search(s or '')
    return float(m.group(1)) if m else None


def normalise_name(name):
    name = clean(name)
    words = name.split()
    if len(words) % 2 == 0 and words[:len(words)//2] == words[len(words)//2:]:
        return ' '.join(words[:len(words)//2])
    return name


def dismiss(page):
    selectors = [
        '#onetrust-accept-btn-handler',
        'button:has-text("Accept")',
        'button:has-text("Allow all")',
        'button:has-text("Accept All")',
        'button:has-text("I agree")',
        'button[aria-label="Close"]',
    ]
    for _ in range(3):
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=800):
                    loc.click(timeout=1200)
                    page.wait_for_timeout(300)
            except Exception:
                pass


def matches_term(term, text, name):
    lower = f' {text.lower()} '
    lname = f' {name.lower()} '
    return any(tok in lower or tok in lname for tok in TERM_REQUIRE.get(term, [term.lower()]))


def is_contaminated(term, text, name, price):
    lower = f' {text.lower()} '
    lname = f' {name.lower()} '
    if price is None or price < 0.4:
        return True
    if any(bad in lower or bad in lname for bad in GLOBAL_EXCLUDE):
        return True
    if any(bad in lower or bad in lname for bad in TERM_EXCLUDE.get(term, [])):
        return True
    return False


def extract_search_candidates(page, term):
    rows = page.evaluate("""
() => {
  const abs = (u) => { try { return new URL(u, location.href).href; } catch(e) { return null; } };
  const out = [];
  const anchors = Array.from(document.querySelectorAll('a[href*="/p/"]'));
  for (const a of anchors) {
    const href = abs(a.getAttribute('href'));
    const card = a.closest('article, li, div, section') || a;
    const text = ((card && card.innerText) || a.innerText || '').replace(/\s+/g, ' ').trim();
    if (!href || !text) continue;
    out.push({href, text: text.slice(0, 900)});
  }
  return out;
}
""")
    seen = {}
    for row in rows:
        href = row.get('href') or ''
        text = clean(row.get('text'))
        if '/p/' not in href or not text:
            continue
        price = parse_price(text)
        name = normalise_name(clean(re.split(r'£\s*\d', text, maxsplit=1)[0]))
        if not name or len(name) < 4:
            continue
        if not matches_term(term, text, name):
            continue
        if is_contaminated(term, text, name, price):
            continue
        size_m = SIZE_RE.search(text)
        size_raw = clean(size_m.group(1)) if size_m else ''
        item = {
            'item_name': name[:180],
            'price': price,
            'size_raw': size_raw[:60],
            'category': TERM_CATEGORY.get(term, ''),
            'direct_url': href.split('#')[0],
            'search_term': term,
            'source': 'search_card',
        }
        seen[item['direct_url']] = item
    return list(seen.values())


def extract_detail(page, term):
    text = clean(page.locator('body').inner_text(timeout=5000))[:12000]
    url = page.url.split('#')[0]
    title = ''
    for sel in ['h1', '[data-testid="product-title"]', 'main h1']:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.inner_text(timeout=1200).strip():
                title = clean(loc.inner_text(timeout=1200))
                break
        except Exception:
            pass
    if not title:
        m = re.search(r'^(.*?)\s+£\s*\d', text)
        if m:
            title = clean(m.group(1))
    title = normalise_name(title)
    price = parse_price(text)
    size_raw = ''
    m = SIZE_RE.search(text)
    if m:
        size_raw = clean(m.group(1))
    detail_bits = []
    for pattern in [
        r'(?:Description|Product Details|Features)\s*(.{0,240})',
        r'(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|l|pack|pk|x\s?\d+|each)[^\.]{0,120})',
    ]:
        dm = re.search(pattern, text, re.I)
        if dm:
            detail_bits.append(clean(dm.group(1)))
    detail_text = ' | '.join(dict.fromkeys([x for x in detail_bits if x]))[:300]
    category = TERM_CATEGORY.get(term, '')
    if not title or not matches_term(term, text, title) or is_contaminated(term, text, title, price):
        return None
    return {
        'item_name': title[:180],
        'price': price,
        'size_raw': size_raw[:60],
        'category': category,
        'direct_url': url,
        'detail_text': detail_text,
        'search_term': term,
        'source': 'detail_page',
    }


def call_ingest_chunk(items):
    payload = {'prices': []}
    for x in items:
        payload['prices'].append({
            'supermarket': SUPERMARKET,
            'item_key': re.sub(r'[^a-z0-9]+', '_', x['item_name'].lower()).strip('_')[:120],
            'item_name': x['item_name'],
            'price': x['price'],
        })
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': 'upsert_prices', 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={'Content-Type': 'application/json', 'x-agent-key': AGENT_KEY})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def main():
    ts = int(time.time())
    report = {
        'run': 'lidl_browser_details_run',
        'timestamp': datetime.now().isoformat(),
        'search_terms_used': SEARCH_TERMS,
        'detail_pages_reached': 0,
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'per_term': [],
        'clean_items': []
    }
    collected = []
    seen_urls = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME, args=['--disable-http2'])
        page = browser.new_page(viewport={'width': 1440, 'height': 2200})
        page.set_default_timeout(20000)
        for term in SEARCH_TERMS:
            if len(collected) >= MAX_DETAIL_PAGES:
                break
            search_url = f'https://www.lidl.co.uk/q/search?q={urllib.parse.quote(term)}'
            term_info = {'term': term, 'search_url': search_url, 'detail_urls_attempted': [], 'clean_found': 0, 'sample': []}
            try:
                page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2500)
                dismiss(page)
                for _ in range(2):
                    page.mouse.wheel(0, 1600)
                    page.wait_for_timeout(700)
                candidates = extract_search_candidates(page, term)
                term_candidates = []
                for c in candidates:
                    if c['direct_url'] in seen_urls:
                        continue
                    term_candidates.append(c)
                    if len(term_candidates) >= PER_TERM_TARGET + 1:
                        break
                for cand in term_candidates:
                    if len(collected) >= MAX_DETAIL_PAGES:
                        break
                    url = cand['direct_url']
                    term_info['detail_urls_attempted'].append(url)
                    try:
                        detail = browser.new_page(viewport={'width': 1440, 'height': 2200})
                        detail.set_default_timeout(20000)
                        detail.goto(url, wait_until='domcontentloaded', timeout=30000)
                        detail.wait_for_timeout(2200)
                        dismiss(detail)
                        item = extract_detail(detail, term)
                        report['detail_pages_reached'] += 1
                        detail.close()
                        if not item:
                            continue
                        if item['direct_url'] in seen_urls:
                            continue
                        seen_urls.add(item['direct_url'])
                        collected.append(item)
                        term_info['clean_found'] += 1
                        term_info['sample'].append(item)
                        if term_info['clean_found'] >= PER_TERM_TARGET:
                            break
                    except Exception as e:
                        term_info.setdefault('errors', []).append(repr(e))
            except Exception as e:
                term_info['error'] = repr(e)
                report['blockers'].append(f'{term}: {e!r}')
            report['per_term'].append(term_info)
        browser.close()

    report['items_found'] = len(collected)
    report['clean_items'] = collected

    if collected and AGENT_KEY:
        for chunk in chunks(collected, CHUNK_SIZE):
            try:
                res = call_ingest_chunk(chunk)
                if isinstance(res, dict) and res.get('error'):
                    report['blockers'].append(f'ingest_error: {res.get("error")}')
                else:
                    report['items_ingested'] += len(chunk)
                time.sleep(0.7)
            except Exception as e:
                report['blockers'].append(f'ingest_exception: {e!r}')
                break
    elif collected and not AGENT_KEY:
        report['blockers'].append('Missing ingest agent key')
    else:
        report['blockers'].append('No clean Lidl product detail items extracted')

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f'lidl_browser_details_run_{ts}.json'
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({
        'report_path': str(out),
        'detail_pages_reached': report['detail_pages_reached'],
        'items_found': report['items_found'],
        'items_ingested': report['items_ingested'],
        'blockers': report['blockers'],
        'clean_items': report['clean_items'][:10]
    }, indent=2))

if __name__ == '__main__':
    main()
