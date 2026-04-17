#!/usr/bin/env python3
import json, os, re, ssl, time, urllib.request
from datetime import datetime

INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))
BASE = '/Users/tosin/.openclaw/workspace-main/trolleyroast-agent'
SOURCE_REPORT = os.path.join(BASE, 'reports', 'aldi_dairy_short_run_1774449807.json')
REPORT_DIR = os.path.join(BASE, 'reports')
CHUNK_SIZE = 3

EXACT_ITEMS = [
  {'supermarket':'aldi','item_name':'COWBELLE UHT Semi Skimmed Milk','price':0.99,'size_raw':'1 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE UHT Red Skimmed Milk','price':0.99,'size_raw':'1 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Semi Skimmed Milk 1.7% Fat','price':2.40,'size_raw':'3.408 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Semi Skimmed Milk 1.7% Fat','price':1.65,'size_raw':'2.272 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Whole Milk 3.6% Fat','price':1.65,'size_raw':'2.272 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Skimmed Milk <0.5% Fat','price':1.65,'size_raw':'2.272 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Filtered British Semi Skimmed Milk','price':1.75,'size_raw':'2 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Lactose Free Milk','price':0.99,'size_raw':'1 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Filtered British Whole Milk','price':1.75,'size_raw':'2 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Organic Semi Skimmed Milk 1.7% Fat','price':2.09,'size_raw':'2.272 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Organic Whole Milk 3.8% Fat','price':2.09,'size_raw':'2.272 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Filtered British Skimmed Milk','price':1.75,'size_raw':'2 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Whole Milk 3.6% Fat','price':2.40,'size_raw':'3.408 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE Skimmed Milk <0.5% Fat','price':2.40,'size_raw':'3.408 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'},
  {'supermarket':'aldi','item_name':'COWBELLE UHT Whole Milk','price':0.99,'size_raw':'1 L','category':'dairy','direct_url':'https://www.aldi.co.uk/products/chilled-food/milk/k/1588161416978051001'}
]

def item_key(name, size_raw=None):
    base = name.lower()
    if size_raw:
        base += '_' + size_raw.lower()
    return re.sub(r'[^a-z0-9]+', '_', base).strip('_')[:120]

def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def call_ingest(action, payload):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={'Content-Type': 'application/json', 'x-agent-key': AGENT_KEY})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        body = r.read().decode('utf-8')
        return json.loads(body) if body else {}

def load_source_items():
    with open(SOURCE_REPORT, 'r') as f:
        prior = json.load(f)
    sample = prior.get('sample_items') or []
    if len(sample) >= 15:
        return sample[:15], prior
    return EXACT_ITEMS, prior

def main():
    ts = int(time.time())
    items, prior = load_source_items()
    retry_report = {
        'run': 'aldi_dairy_retry_ingest',
        'timestamp': datetime.now().isoformat(),
        'source_report': SOURCE_REPORT,
        'supermarket': 'aldi',
        'category': 'dairy',
        'retry_only': True,
        'chunk_size': CHUNK_SIZE,
        'items_retried': len(items),
        'items_ingested': 0,
        'remaining_failures': 0,
        'failed_items': [],
        'chunk_results': [],
        'prior_blockers': prior.get('blockers', []),
        'sample_items': items[:10],
    }

    for idx, batch in enumerate(chunked(items, CHUNK_SIZE), start=1):
        payload = {
            'prices': [
                {
                    'supermarket': x['supermarket'],
                    'item_key': item_key(x['item_name'], x.get('size_raw')),
                    'item_name': x['item_name'],
                    'price': x['price'],
                }
                for x in batch
            ]
        }
        try:
            res = call_ingest('upsert_prices', payload)
            err = res.get('error') if isinstance(res, dict) else None
            if err:
                retry_report['chunk_results'].append({'chunk': idx, 'attempted': len(batch), 'ingested': 0, 'status': 'error', 'error': err})
                retry_report['failed_items'].extend(batch)
            else:
                retry_report['chunk_results'].append({'chunk': idx, 'attempted': len(batch), 'ingested': len(batch), 'status': 'ok', 'response': res})
                retry_report['items_ingested'] += len(batch)
        except Exception as e:
            retry_report['chunk_results'].append({'chunk': idx, 'attempted': len(batch), 'ingested': 0, 'status': 'exception', 'error': repr(e)})
            retry_report['failed_items'].extend(batch)

    retry_report['remaining_failures'] = len(retry_report['failed_items'])
    out = os.path.join(REPORT_DIR, f'aldi_dairy_retry_ingest_{ts}.json')
    with open(out, 'w') as f:
        json.dump(retry_report, f, indent=2)
    print(json.dumps({'report_path': out, 'items_retried': retry_report['items_retried'], 'items_ingested': retry_report['items_ingested'], 'remaining_failures': retry_report['remaining_failures']}))

if __name__ == '__main__':
    main()
