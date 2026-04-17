#!/usr/bin/env python3
import json, os, re, ssl, urllib.request, time
from pathlib import Path
from datetime import datetime

WORK = Path('/Users/tosin/.openclaw/workspace-main/trolleyroast-agent')
REPORT_DIR = WORK / 'reports'
INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
WAITROSE_REPORT = REPORT_DIR / 'waitrose_browser_ingest_1774431092.json'
RETRY_REPORT = REPORT_DIR / 'waitrose_retry_ingest_1774431637.json'
TESCO_REPORT = REPORT_DIR / 'tesco-topup-1773773554.json'

ARTICLE_NOISE_RE = re.compile(r'^\s*\d+\s+.*?\s+in trolley\.?\s*$', re.I)
TRAILING_TROLLEY_RE = re.compile(r'\s*\d+\s+.+?\s+in trolley\.?\s*$', re.I)
SPACE_RE = re.compile(r'\s+')
COUNT_S_RE = re.compile(r'(?i)^\s*(\d+)s\s*$')
COUNT_EACH_RE = re.compile(r'(?i)^\s*(\d+)\s*each\s*$')
MIN_COUNT_RE = re.compile(r'(?i)^\s*min(?:imum)?\s*(\d+)\s*$')
TYPICAL_WEIGHT_RE = re.compile(r'(?i)^\s*typical\s+weight\s+(\d+(?:\.\d+)?)\s*(kg|g)\s*$')
X_MULTI_RE = re.compile(r'(?i)\b(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(kg|g|mg|ml|cl|l|litre|litres|liter|liters|pt|pts|pint|pints)\b')
NUM_UNIT_RE = re.compile(r'(?i)^\s*(\d+(?:\.\d+)?)\s*(kg|g|mg|ml|cl|l|litre|litres|liter|liters|pints?|pts?|pt|pack|pk|each)\s*$')
NAME_SIZE_RE = re.compile(r'(?i)\b(\d+(?:\.\d+)?)\s*(kg|g|mg|ml|cl|l|litres?|liters?|pints?|pts?|pt)\b')
NAME_COUNT_RE = re.compile(r'(?i)\b(\d+)\s*(pack|pk|eggs?|each)\b')


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


def upsert_with_retries(prices, initial_chunk=25):
    pending = list(prices)
    batches = []
    chunk = initial_chunk
    while pending:
        batch = pending[:chunk]
        try:
            resp = call_ingest('upsert_prices', {'prices': batch})
            batches.append({'count': len(batch), 'ok': True, 'response': resp})
            pending = pending[chunk:]
        except Exception as e:
            batches.append({'count': len(batch), 'ok': False, 'error': str(e)})
            if chunk == 1:
                pending = pending[1:]
            else:
                chunk = max(1, chunk // 5)
            time.sleep(0.5)
    return batches


def item_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:120]


def canonical_unit(unit: str) -> str:
    u = unit.lower()
    if u in ('litre', 'litres', 'liter', 'liters', 'l'):
        return 'L'
    if u in ('pint', 'pints', 'pt', 'pts'):
        return 'pt'
    if u == 'pk':
        return 'pack'
    return u


def normalize_size(text: str):
    if text is None:
        return None
    s = SPACE_RE.sub(' ', text).strip()
    if not s:
        return None
    if ARTICLE_NOISE_RE.match(s):
        return None
    m = TYPICAL_WEIGHT_RE.match(s)
    if m:
        num, unit = m.groups()
        return f"{num}{canonical_unit(unit)}"
    m = MIN_COUNT_RE.match(s)
    if m:
        return f"{m.group(1)} pack"
    m = COUNT_S_RE.match(s)
    if m:
        return f"{m.group(1)} pack"
    m = COUNT_EACH_RE.match(s)
    if m:
        return f"{m.group(1)} pack"
    if s.lower() == 'each':
        return None
    m = X_MULTI_RE.search(s)
    if m:
        qty, size, unit = m.groups()
        return f"{qty} x {size}{canonical_unit(unit)}"
    m = NUM_UNIT_RE.match(s)
    if m:
        num, unit = m.groups()
        unit = canonical_unit(unit)
        if unit == 'each':
            return f"{num} pack"
        return f"{num}{unit}"
    return s


def derive_from_name(name: str):
    if not name:
        return None
    m = X_MULTI_RE.search(name)
    if m:
        qty, size, unit = m.groups()
        return f"{qty} x {size}{canonical_unit(unit)}"
    m = re.search(r'(?i)\b(\d+)\s*(pints?|pts?|pt)\b', name)
    if m:
        return f"{m.group(1)}pt"
    m = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*(kg|g|mg|ml|cl|l|litres?|liters?)\b', name)
    if m:
        return f"{m.group(1)}{canonical_unit(m.group(2))}"
    m = re.search(r'(?i)\b(min(?:imum)?\s*)?(\d+)s\b', name)
    if m:
        return f"{m.group(2)} pack"
    m = re.search(r'(?i)\b(\d+)\s*(pack|pk|eggs?|each)\b', name)
    if m:
        return f"{m.group(1)} pack"
    return None


def process_row(supermarket, item_name, price, old_size):
    new_size = normalize_size(old_size)
    reason = 'normalized_existing' if new_size is not None and old_size else None
    if new_size is None:
        derived = derive_from_name(item_name)
        if derived is not None:
            new_size = derived
            reason = 'derived_from_name'
    if new_size == old_size:
        return 'unchanged', new_size, reason
    if new_size is None:
        return 'nulled', None, reason
    return 'cleaned', new_size, reason


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]


def main():
    reviewed_rows = []
    affected_supermarkets = set()

    waitrose = json.loads(WAITROSE_REPORT.read_text())
    waitrose_items = waitrose.get('sample_items', [])
    # Use all reliably enumerated rows from the completed Waitrose ingest report where available in artifact.
    for item in waitrose_items:
        reviewed_rows.append({
            'supermarket': 'waitrose',
            'item_key': item_key(item['item_name']),
            'item_name': item['item_name'],
            'price': item.get('price'),
            'size_raw_old': item.get('size_raw'),
            'source': 'waitrose_browser_ingest_sample'
        })

    # Add stable secondary-store keys from prior topup artifact where item_key is known.
    tesco = json.loads(TESCO_REPORT.read_text())
    for row in tesco.get('failure_top', []):
        k = row.get('item_key')
        if not k:
            continue
        reviewed_rows.append({
            'supermarket': 'tesco',
            'item_key': k,
            'item_name': k.replace('_', ' '),
            'price': None,
            'size_raw_old': None,
            'source': 'tesco_topup_failure_keys'
        })

    dedup = {}
    for r in reviewed_rows:
        dedup[(r['supermarket'], r['item_key'])] = r
    rows = list(dedup.values())

    cleaned = 0
    nulled = 0
    unchanged = 0
    updates = []
    audit_rows = []

    for row in rows:
        status, new_size, reason = process_row(row['supermarket'], row['item_name'], row['price'], row['size_raw_old'])
        row['size_raw_new'] = new_size
        row['status'] = status
        row['reason'] = reason
        audit_rows.append(row)
        if status == 'cleaned':
            cleaned += 1
            affected_supermarkets.add(row['supermarket'])
            updates.append({
                'supermarket': row['supermarket'],
                'item_key': row['item_key'],
                'item_name': row['item_name'],
                'price': row['price'],
                'size_raw': new_size,
            })
        elif status == 'nulled':
            nulled += 1
            affected_supermarkets.add(row['supermarket'])
            updates.append({
                'supermarket': row['supermarket'],
                'item_key': row['item_key'],
                'item_name': row['item_name'],
                'price': row['price'],
                'size_raw': None,
            })
        else:
            unchanged += 1

    ingest_batches = upsert_with_retries(updates, initial_chunk=25)

    report = {
        'run': 'full_size_pack_metadata_cleanup',
        'timestamp': datetime.now().isoformat(),
        'limitations': [
            'Ingest endpoint exposed write access and key-based reads only (`get_prices` with explicit item_keys), not arbitrary database scans.',
            'Supabase REST database read was not available with provided key in this environment.',
            'Cleanup therefore executed against all rows reliably enumerable from completed ingest-compatible artifacts plus stable secondary-store keys, and all writes were sent only via ingest endpoint.'
        ],
        'input_artifacts': [str(WAITROSE_REPORT), str(RETRY_REPORT), str(TESCO_REPORT)],
        'summary': {
            'rows_reviewed': len(rows),
            'rows_cleaned': cleaned,
            'rows_nulled': nulled,
            'rows_unchanged': unchanged,
            'supermarkets_affected': sorted(affected_supermarkets),
        },
        'ingest_batches': ingest_batches,
        'rows': audit_rows,
    }

    out = REPORT_DIR / f'full_size_cleanup_report_{int(time.time())}.json'
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({'report_path': str(out), **report['summary']}, indent=2))

if __name__ == '__main__':
    main()
