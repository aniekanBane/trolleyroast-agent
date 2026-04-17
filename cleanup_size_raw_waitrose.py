#!/usr/bin/env python3
import json, os, re, ssl, urllib.request, time
from pathlib import Path
from datetime import datetime

WORK = Path('/Users/tosin/.openclaw/workspace-main/trolleyroast-agent')
REPORT_DIR = WORK / 'reports'
SOURCE_REPORT = REPORT_DIR / 'waitrose_browser_ingest_1774431092.json'
INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))

ARTICLE_NOISE_RE = re.compile(r'^\s*\d+\s+.*?\s+in trolley\.?\s*$', re.I)
UNIT_TOKEN_RE = re.compile(r'(?i)\b\d+(?:\.\d+)?\s*(?:kg|g|mg|litre|liter|l|ml|cl|pints?|pts?|pt|pack|pk|each|x)\b')
NAME_COUNT_RE = re.compile(r'(?i)\b(\d+)\s*(pints?|pts?|pt|lit(?:re|er)?s?|l|ml|kg|g|pack|pk|eggs?|s|each)\b')
X_MULTI_RE = re.compile(r'(?i)\b(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(g|kg|ml|l|litre|litres|cl)\b')
COUNT_S_RE = re.compile(r'(?i)^\s*(\d+)s\s*$')
COUNT_EACH_RE = re.compile(r'(?i)^\s*(\d+)\s*each\s*$')
NUM_UNIT_RE = re.compile(r'(?i)^\s*(\d+(?:\.\d+)?)\s*(kg|g|mg|ml|cl|l|litre|litres|liter|liters|pints?|pts?|pt|pack|pk|each)\s*$')


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


def item_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:120]


def normalize_size(text):
    if not text:
        return None
    s = re.sub(r'\s+', ' ', text).strip()
    if not s:
        return None
    m = COUNT_S_RE.match(s)
    if m:
        return f"{m.group(1)} pack"
    m = COUNT_EACH_RE.match(s)
    if m:
        return f"{m.group(1)} pack"
    m = X_MULTI_RE.match(s)
    if m:
        qty, size, unit = m.groups()
        unit = unit.lower()
        if unit in ('litres', 'litre', 'liter', 'liters'):
            unit = 'L'
        elif unit == 'l':
            unit = 'L'
        elif unit == 'ml':
            unit = 'ml'
        elif unit == 'cl':
            unit = 'cl'
        elif unit == 'kg':
            unit = 'kg'
        else:
            unit = 'g'
        return f"{qty} x {size}{unit}"
    m = NUM_UNIT_RE.match(s)
    if m:
        num, unit = m.groups()
        unit = unit.lower()
        if unit in ('litres', 'litre', 'liter', 'liters', 'l'):
            unit = 'L'
        elif unit in ('pints', 'pint'):
            unit = 'pt'
        elif unit in ('pts', 'pt'):
            unit = 'pt'
        elif unit == 'pk':
            unit = 'pack'
        elif unit == 'each':
            unit = 'pack'
        return f"{num}{unit}"
    return s


def derive_from_name(name):
    if not name:
        return None
    # x multipack inside product names
    m = X_MULTI_RE.search(name)
    if m:
        return normalize_size(' '.join(m.groups()))
    # common count/volume/weight in product names
    matches = []
    for m in re.finditer(r'(?i)\b\d+(?:\.\d+)?\s*(?:kg|g|mg|ml|cl|litres?|liters?|l|pints?|pts?|pt)\b', name):
        matches.append(m.group(0))
    for m in re.finditer(r'(?i)\b\d+\s*(?:pack|pk|each)\b', name):
        matches.append(m.group(0))
    # eggs / count packs like 4 Pints, 6 Eggs, 10 Medium Eggs, 12 Each
    m = re.search(r'(?i)\b(\d+)\s*(?:large|medium|small|mixed size\s+)?eggs?\b', name)
    if m:
        matches.append(f"{m.group(1)} each")
    # handle trailing “4 Pints” etc already included above; prefer last size-like token in name
    if matches:
        return normalize_size(matches[-1])
    return None


def main():
    src = json.loads(SOURCE_REPORT.read_text())
    sample_items = src.get('sample_items', [])

    rows = []
    for item in sample_items:
        k = item_key(item['item_name'])
        rows.append({
            'supermarket': 'waitrose',
            'item_key': k,
            'item_name': item['item_name'],
            'price': item['price'],
            'size_raw_old': item.get('size_raw'),
            'direct_url': item.get('direct_url'),
        })

    page_sizes = {}

    cleaned = []
    nulled = []
    unchanged = []
    updates = []

    for row in rows:
        old = row['size_raw_old']
        new = None
        reason = None

        page_size = page_sizes.get(row['item_key'])
        if page_size:
            new = page_size
            reason = 'page_product_size'
        elif old and not ARTICLE_NOISE_RE.match(old):
            new = normalize_size(old)
            reason = 'normalized_existing'
        if not new:
            derived = derive_from_name(row['item_name'])
            if derived:
                new = derived
                reason = 'derived_from_name'

        status = 'unchanged'
        if old != new:
            if new is None:
                status = 'nulled'
                nulled.append(row['item_key'])
            else:
                status = 'cleaned'
                cleaned.append(row['item_key'])
            updates.append({
                'supermarket': row['supermarket'],
                'item_key': row['item_key'],
                'item_name': row['item_name'],
                'price': row['price'],
                'size_raw': new,
            })
        else:
            unchanged.append(row['item_key'])

        row['size_raw_new'] = new
        row['status'] = status
        row['reason'] = reason

    ingest_resp = {'success': True, 'rows_processed': 0, 'errors': []}
    if updates:
        ingest_resp = call_ingest('upsert_prices', {'prices': updates})

    summary = {
        'rows_reviewed': len(rows),
        'rows_cleaned': len(cleaned),
        'rows_nulled': len(nulled),
        'rows_left_unchanged': len(unchanged),
        'aldi_lidl_rows_reviewed': 0,
        'aldi_lidl_rows_cleaned': 0,
        'aldi_lidl_rows_nulled': 0,
        'aldi_lidl_rows_left_unchanged': 0,
    }

    report = {
        'run': 'waitrose_size_raw_cleanup',
        'timestamp': datetime.now().isoformat(),
        'source_report': str(SOURCE_REPORT),
        'summary': summary,
        'ingest_response': ingest_resp,
        'rows': rows,
        'notes': [
            'Focused on the Waitrose ingestion artifact available locally (20 sampled rows from the completed run report).',
            'Aldi/Lidl artifact inspected locally was empty, so no secondary cleanup rows were available to patch.',
            'Updates were written back via ingest endpoint only using upsert_prices.',
        ],
    }

    out = REPORT_DIR / f'waitrose_size_cleanup_{int(time.time())}.json'
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({'report_path': str(out), **summary, 'ingest_response': ingest_resp}, indent=2))

if __name__ == '__main__':
    main()
