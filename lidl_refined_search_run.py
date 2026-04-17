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
    'minced beef',
    'eggs medium',
    'wholemeal bread',
]
MAX_TOTAL = 25
MAX_PER_TERM = 4
CHUNK_SIZE = 3
PRICE_RE = re.compile(r'£\s*(\d+(?:\.\d{1,2})?)')
SIZE_RE = re.compile(r'(\d+(?:[\.,]\d+)?\s?(?:g|kg|ml|cl|l|litre|litres|pack|pk|x\s?\d+|each|pint|pints))', re.I)

TERM_CATEGORY = {
    'semi skimmed milk': 'Cheese & Dairy',
    'whole milk': 'Cheese & Dairy',
    'cheddar': 'Cheese & Dairy',
    'greek yoghurt': 'Cheese & Dairy',
    'chicken breast': 'Fresh Meat & Poultry',
    'minced beef': 'Fresh Meat & Poultry',
    'eggs medium': 'Eggs & staple foods',
    'wholemeal bread': 'Bakery, Bread & Baked Goods',
}

TERM_REQUIRE = {
    'semi skimmed milk': ['semi skimmed'],
    'whole milk': ['whole milk', 'whole fresh milk'],
    'cheddar': ['cheddar'],
    'greek yoghurt': ['greek yoghurt', 'greek-style yoghurt', 'greek yogurt', 'greek-style yogurt'],
    'chicken breast': ['chicken breast', 'chicken breast fillet', 'chicken fillets'],
    'minced beef': ['minced beef', 'beef mince', 'lean beef mince', 'mince beef'],
    'eggs medium': ['medium eggs', 'british eggs'],
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
    'minced beef': ['burger', 'meatballs', 'lasagne'],
    'eggs medium': ['mini eggs', 'chocolate'],
    'wholemeal bread': ['breadcrumbs', 'breaded'],
}


def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def parse_price(s):
    m = PRICE_RE.search(s or '')
    return float(m.group(1)) if m else None


def normalise_name(name):
    name = clean(name)
    words = name.split()
    if len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            return ' '.join(words[:half])
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
                if loc.is_visible(timeout=1000):
                    loc.click(timeout=1500)
                    page.wait_for_timeout(400)
            except Exception:
                pass


def extract_candidates(page):
    return page.evaluate("""
() => {
  const abs = (u) => { try { return new URL(u, location.href).href; } catch(e) { return null; } };
  const nodes = Array.from(document.querySelectorAll('a, article, li, div, section'));
  const out = [];
  for (const el of nodes) {
    const txt = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!txt || !txt.includes('£')) continue;
    if (txt.length < 6 || txt.length > 700) continue;
    const a = el.closest('a') || el.querySelector('a[href]');
    const href = a && a.getAttribute('href') ? abs(a.getAttribute('href')) : null;
    out.push({ text: txt.slice(0, 700), href });
  }
  return out.slice(0, 1500);
}
""")


def is_contaminated(term, text, name):
    lower = f' {text.lower()} '
    lname = f' {name.lower()} '
    if any(bad in lower or bad in lname for bad in GLOBAL_EXCLUDE):
        return True
    if any(bad in lower or bad in lname for bad in TERM_EXCLUDE.get(term, [])):
        return True
    return False


def matches_term(term, text, name):
    lower = f' {text.lower()} '
    lname = f' {name.lower()} '
    required = TERM_REQUIRE.get(term, [term.lower()])
    return any(tok in lower or tok in lname for tok in required)


def extract_items(page, term):
    raw = extract_candidates(page)
    seen = {}
    for row in raw:
        text = clean(row.get('text'))
        price = parse_price(text)
        if price is None or price < 0.4:
            continue
        name = clean(re.split(r'£\s*\d', text, maxsplit=1)[0])
        name = normalise_name(name)
        if not name or len(name) < 4:
            continue
        if not matches_term(term, text, name):
            continue
        if is_contaminated(term, text, name):
            continue
        if any(bad in name.lower() for bad in ['add', 'remove', 'favourite', 'favorite', 'buy now', 'shop now', 'sign in']):
            continue
        size_m = SIZE_RE.search(text)
        size_raw = clean(size_m.group(1)) if size_m else ''
        direct_url = row.get('href') or page.url
        if 'lidl.co.uk' not in direct_url:
            continue
        item = {
            'item_name': name[:180],
            'price': price,
            'size_raw': size_raw[:60],
            'category': TERM_CATEGORY.get(term, ''),
            'direct_url': direct_url,
            'search_term': term,
        }
        key = (item['item_name'].lower(), item['price'], item['size_raw'])
        seen[key] = item
    items = list(seen.values())
    items.sort(key=lambda x: (x['price'], x['item_name']))
    return items


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
        'run': 'lidl_refined_search_run',
        'timestamp': datetime.now().isoformat(),
        'search_terms_used': SEARCH_TERMS,
        'items_found': 0,
        'items_ingested': 0,
        'blockers': [],
        'per_term': [],
        'clean_items': []
    }
    collected = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME, args=['--disable-http2'])
        page = browser.new_page(viewport={'width': 1440, 'height': 2400})
        page.set_default_timeout(20000)
        for idx, term in enumerate(SEARCH_TERMS):
            url = f'https://www.lidl.co.uk/q/search?q={urllib.parse.quote(term)}'
            term_info = {'term': term, 'url': url, 'found': 0, 'used': 0, 'sample': []}
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2800)
                dismiss(page)
                for _ in range(3):
                    page.mouse.wheel(0, 1700)
                    page.wait_for_timeout(900)
                items = extract_items(page, term)
                dedup_existing = {(x['item_name'].lower(), x['price'], x['size_raw']) for x in collected}
                usable = []
                for item in items:
                    key = (item['item_name'].lower(), item['price'], item['size_raw'])
                    if key in dedup_existing:
                        continue
                    usable.append(item)
                    dedup_existing.add(key)
                    if len(usable) >= MAX_PER_TERM:
                        break
                collected.extend(usable)
                term_info['found'] = len(items)
                term_info['used'] = len(usable)
                term_info['sample'] = usable[:3]
                if not items:
                    term_info['note'] = 'no_clean_results_extracted'
            except Exception as e:
                term_info['error'] = repr(e)
                report['blockers'].append(f'{term}: {e!r}')
            report['per_term'].append(term_info)
            if len(collected) >= MAX_TOTAL:
                collected = collected[:MAX_TOTAL]
                break
            if idx < len(SEARCH_TERMS) - 1:
                page.wait_for_timeout(600)
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
        report['blockers'].append('No clean Lidl grocery items extracted from refined search terms')

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f'lidl_refined_search_run_{ts}.json'
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({
        'report_path': str(out),
        'search_terms_used': report['search_terms_used'],
        'items_found': report['items_found'],
        'items_ingested': report['items_ingested'],
        'blockers': report['blockers'],
        'clean_items': report['clean_items'][:10]
    }, indent=2))

if __name__ == '__main__':
    main()
