#!/usr/bin/env python3
"""TrolleyRoast - Full Category Sweep (Phase 1)
Extracts prices from Trolley.co.uk across all major categories and ingests to database.
"""
import json
import re
import urllib.request
import urllib.parse
import time
import ssl
import os
import hashlib
from datetime import datetime
from collections import defaultdict

# Configuration
INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))

SUPERMARKETS = ['tesco', 'asda', 'sainsburys', 'morrisons', 'aldi', 'lidl', 'waitrose', 'co-op']

# Full category catalogue (expanded from baseline 100)
CATEGORY_CATALOGUE = {
    'eggs': [
        ('eggs_medium_6', 'Eggs Medium 6'),
        ('eggs_large_6', 'Eggs Large 6'),
        ('eggs_large_12', 'Eggs Large 12'),
        ('eggs_free_range_6', 'Free Range Eggs 6'),
        ('eggs_organic_6', 'Organic Eggs 6'),
    ],
    'dairy': [
        ('milk_semi_4pt', 'Semi Skimmed Milk 4pt'),
        ('milk_whole_4pt', 'Whole Milk 4pt'),
        ('milk_skimmed_4pt', 'Skimmed Milk 4pt'),
        ('milk_semi_2pt', 'Semi Skimmed Milk 2pt'),
        ('butter_salted_250g', 'Salted Butter 250g'),
        ('butter_unsalted_250g', 'Unsalted Butter 250g'),
        ('butter_spread_500g', 'Butter Spread 500g'),
        ('cheddar_mature_400g', 'Mature Cheddar 400g'),
        ('cheddar_mild_400g', 'Mild Cheddar 400g'),
        ('mozzarella_125g', 'Mozzarella 125g'),
        ('greek_yoghurt_500g', 'Greek Yoghurt 500g'),
        ('natural_yoghurt_500g', 'Natural Yoghurt 500g'),
        ('cream_cheese_180g', 'Cream Cheese 180g'),
        ('soured_cream_300ml', 'Soured Cream 300ml'),
        ('double_cream_300ml', 'Double Cream 300ml'),
        ('single_cream_284ml', 'Single Cream 284ml'),
        ('cottage_cheese_300g', 'Cottage Cheese 300g'),
    ],
    'bakery': [
        ('bread_white_800g', 'Medium White Sliced Bread 800g'),
        ('bread_wholemeal_800g', 'Wholemeal Sliced Bread 800g'),
        ('bread_seeded_800g', 'Seeded Bread 800g'),
        ('sourdough_400g', 'Sourdough 400g'),
        ('rolls_6pack', 'White Rolls 6 Pack'),
        ('crumpets_6pack', 'Crumpets 6 Pack'),
        ('bagels_5pack', 'Bagels 5 Pack'),
        ('pitta_6pack', 'Pitta Bread 6 Pack'),
        ('croissants_4pack', 'Croissants 4 Pack'),
        ('naan_bread_2pack', 'Naan Bread 2 Pack'),
        ('wraps_6pack', 'Wraps 6 Pack'),
        ('pancakes_6pack', 'Pancakes 6 Pack'),
    ],
    'meat_fish': [
        ('chicken_breast_500g', 'Chicken Breast 500g'),
        ('chicken_breast_1kg', 'Chicken Breast 1kg'),
        ('chicken_thighs_1kg', 'Chicken Thighs 1kg'),
        ('chicken_wings_1kg', 'Chicken Wings 1kg'),
        ('beef_mince_500g', 'Beef Mince 500g 5% Fat'),
        ('beef_mince_1kg', 'Beef Mince 1kg'),
        ('beef_steaks_2pack', 'Beef Steaks 2 Pack'),
        ('pork_chops_4pack', 'Pork Chops 4 Pack'),
        ('sausages_8pack', 'Pork Sausages 8 Pack'),
        ('sausages_16pack', 'Pork Sausages 16 Pack'),
        ('bacon_smoked_8pack', 'Smoked Bacon 8 Pack'),
        ('gammon_joint_1kg', 'Gammon Joint 1kg'),
        ('salmon_fillets_2pack', 'Salmon Fillets 2 Pack'),
        ('cod_fillets_2pack', 'Cod Fillets 2 Pack'),
        ('prawns_raw_200g', 'Raw Prawns 200g'),
        ('tuna_steaks_2pack', 'Tuna Steaks 2 Pack'),
        ('ham_sliced_120g', 'Sliced Ham 120g'),
        ('turkey_breast_500g', 'Turkey Breast 500g'),
        ('lamb_chops_4pack', 'Lamb Chops 4 Pack'),
    ],
    'fruit_veg': [
        ('bananas_kg', 'Bananas per kg'),
        ('apples_6pack', 'Apples 6 Pack'),
        ('oranges_4pack', 'Oranges 4 Pack'),
        ('strawberries_400g', 'Strawberries 400g'),
        ('blueberries_150g', 'Blueberries 150g'),
        ('raspberries_150g', 'Raspberries 150g'),
        ('grapes_500g', 'Grapes 500g'),
        ('lemons_3pack', 'Lemons 3 Pack'),
        ('limes_3pack', 'Limes 3 Pack'),
        ('bananas_fairtrade_5pack', 'Fairtrade Bananas 5 Pack'),
        ('pears_4pack', 'Pears 4 Pack'),
        ('broccoli_each', 'Broccoli Each'),
        ('carrots_1kg', 'Carrots 1kg'),
        ('potatoes_2_5kg', 'Potatoes 2.5kg'),
        ('onions_1kg', 'Onions 1kg'),
        ('cherry_tomatoes_250g', 'Cherry Tomatoes 250g'),
        ('tomatoes_6pack', 'Tomatoes 6 Pack'),
        ('cucumber_each', 'Cucumber Each'),
        ('lettuce_iceberg', 'Iceberg Lettuce'),
        ('lettuce_little_gem_2pack', 'Little Gem Lettuce 2 Pack'),
        ('spinach_200g', 'Spinach 200g'),
        ('peppers_3pack', 'Mixed Peppers 3 Pack'),
        ('avocado_each', 'Avocado Each'),
        ('avocado_2pack', 'Avocado 2 Pack'),
        ('garlic_bulb', 'Garlic Bulb'),
        ('sweet_potato_each', 'Sweet Potato Each'),
        ('mushrooms_400g', 'Mushrooms 400g'),
        ('courgette_2pack', 'Courgette 2 Pack'),
        ('aubergine_each', 'Aubergine Each'),
        ('cauliflower_each', 'Cauliflower Each'),
        ('cabbage_each', 'Cabbage Each'),
        ('leeks_500g', 'Leeks 500g'),
        ('celery_each', 'Celery Each'),
    ],
    'pantry': [
        ('pasta_penne_500g', 'Penne Pasta 500g'),
        ('pasta_spaghetti_500g', 'Spaghetti 500g'),
        ('pasta_fusilli_500g', 'Fusilli Pasta 500g'),
        ('rice_long_grain_1kg', 'Long Grain Rice 1kg'),
        ('rice_basmati_1kg', 'Basmati Rice 1kg'),
        ('tinned_tomatoes_400g', 'Tinned Tomatoes 400g'),
        ('baked_beans_4pack', 'Baked Beans 4 Pack'),
        ('chickpeas_400g', 'Chickpeas 400g Tin'),
        ('kidney_beans_400g', 'Kidney Beans 400g'),
        ('coconut_milk_400ml', 'Coconut Milk 400ml'),
        ('stock_cubes_10pack', 'Chicken Stock Cubes 10 Pack'),
        ('stock_cubes_beef_10pack', 'Beef Stock Cubes 10 Pack'),
        ('olive_oil_500ml', 'Olive Oil 500ml'),
        ('olive_oil_1l', 'Olive Oil 1L'),
        ('sunflower_oil_1l', 'Sunflower Oil 1L'),
        ('vegetable_oil_1l', 'Vegetable Oil 1L'),
        ('plain_flour_1_5kg', 'Plain Flour 1.5kg'),
        ('self_raising_flour_1_5kg', 'Self Raising Flour 1.5kg'),
        ('sugar_1kg', 'White Sugar 1kg'),
        ('brown_sugar_500g', 'Brown Sugar 500g'),
        ('salt_750g', 'Salt 750g'),
        ('pepper_black_50g', 'Black Pepper 50g'),
        ('vinegar_malt_568ml', 'Malt Vinegar 568ml'),
        ('cornflour_500g', 'Cornflour 500g'),
        ('cornflakes_500g', 'Cornflakes 500g'),
        ('porridge_oats_1kg', 'Porridge Oats 1kg'),
        ('granola_500g', 'Granola 500g'),
        ('peanut_butter_340g', 'Peanut Butter Smooth 340g'),
        ('jam_strawberry_340g', 'Strawberry Jam 340g'),
        ('honey_340g', 'Honey 340g'),
        ('ketchup_570g', 'Tomato Ketchup 570g'),
        ('mayonnaise_400g', 'Mayonnaise 400g'),
        ('soy_sauce_150ml', 'Soy Sauce 150ml'),
        ('pasta_sauce_500g', 'Tomato Pasta Sauce 500g'),
        ('tuna_chunks_4pack', 'Tuna Chunks 4 Pack'),
        ('sweetcorn_tinned_2pack', 'Tinned Sweetcorn 2 Pack'),
        ('soup_tinned_400g', 'Tinned Soup 400g'),
        ('noodles_instant_4pack', 'Instant Noodles 4 Pack'),
    ],
    'frozen': [
        ('peas_frozen_900g', 'Frozen Peas 900g'),
        ('sweetcorn_frozen_1kg', 'Frozen Sweetcorn 1kg'),
        ('chips_frozen_1kg', 'Frozen Chips 1kg'),
        ('fish_fingers_10pack', 'Fish Fingers 10 Pack'),
        ('chicken_nuggets_500g', 'Chicken Nuggets 500g'),
        ('ice_cream_vanilla_900ml', 'Vanilla Ice Cream 900ml'),
        ('ice_cream_chocolate_900ml', 'Chocolate Ice Cream 900ml'),
        ('pizza_margherita', 'Margherita Pizza Frozen'),
        ('pizza_pepperoni', 'Pepperoni Pizza Frozen'),
        ('frozen_veg_mix_1kg', 'Frozen Vegetable Mix 1kg'),
        ('berries_frozen_500g', 'Frozen Berries 500g'),
        ('garlic_bread_2pack', 'Garlic Bread 2 Pack'),
    ],
    'drinks': [
        ('orange_juice_1l', 'Orange Juice 1L'),
        ('apple_juice_1l', 'Apple Juice 1L'),
        ('orange_juice_2l', 'Orange Juice 2L'),
        ('cola_2l', 'Coca-Cola 2L'),
        ('pepsi_2l', 'Pepsi 2L'),
        ('cola_diet_2l', 'Diet Coke 2L'),
        ('sparkling_water_2l', 'Sparkling Water 2L'),
        ('still_water_2l', 'Still Water 2L'),
        ('water_6x500ml', 'Water 6x500ml'),
        ('tea_bags_80pack', 'Tea Bags 80 Pack'),
        ('tea_bags_160pack', 'Tea Bags 160 Pack'),
        ('instant_coffee_100g', 'Instant Coffee 100g'),
        ('instant_coffee_200g', 'Instant Coffee 200g'),
        ('ground_coffee_227g', 'Ground Coffee 227g'),
        ('energy_drink_1l', 'Energy Drink 1L'),
        ('squash_orange_1l', 'Orange Squash 1L'),
        ('squash_blackcurrant_1l', 'Blackcurrant Squash 1L'),
    ],
    'household': [
        ('washing_up_liquid_500ml', 'Washing Up Liquid 500ml'),
        ('laundry_tablets_30pack', 'Laundry Tablets 30 Pack'),
        ('laundry_liquid_2l', 'Laundry Liquid 2L'),
        ('laundry_capsules_24pack', 'Laundry Capsules 24 Pack'),
        ('fabric_conditioner_1_5l', 'Fabric Conditioner 1.5L'),
        ('toilet_roll_9pack', 'Toilet Roll 9 Pack'),
        ('toilet_roll_18pack', 'Toilet Roll 18 Pack'),
        ('kitchen_roll_2pack', 'Kitchen Roll 2 Pack'),
        ('bin_bags_30pack', 'Bin Bags 30 Pack'),
        ('bin_bags_10pack', 'Bin Bags 10 Pack'),
        ('surface_cleaner_500ml', 'Surface Cleaner 500ml'),
        ('floor_cleaner_1l', 'Floor Cleaner 1L'),
        ('bleach_750ml', 'Bleach 750ml'),
        ('dishwasher_tablets_30pack', 'Dishwasher Tablets 30 Pack'),
        ('sponges_3pack', 'Washing Up Sponges 3 Pack'),
    ],
    'personal_care': [
        ('toothpaste_100ml', 'Toothpaste 100ml'),
        ('toothpaste_75ml', 'Toothpaste 75ml'),
        ('toothbrush_2pack', 'Toothbrush 2 Pack'),
        ('shampoo_400ml', 'Shampoo 400ml'),
        ('conditioner_400ml', 'Conditioner 400ml'),
        ('shower_gel_500ml', 'Shower Gel 500ml'),
        ('body_wash_500ml', 'Body Wash 500ml'),
        ('deodorant_250ml', 'Deodorant 250ml'),
        ('soap_bar_4pack', 'Soap Bar 4 Pack'),
        ('hand_wash_500ml', 'Hand Wash 500ml'),
        ('tissues_4pack', 'Tissues 4 Pack'),
        ('cotton_wool_100g', 'Cotton Wool 100g'),
    ],
}

def fetch_page(url, retries=3):
    """Fetch page content with SSL handling and retries"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=20, context=ctx) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            continue
    return None

def validate_price(price_value, item_key, item_name):
    """Validate price to reject unit-price contamination"""
    reject_reason = None
    
    # Reject very low prices (< £0.10) - likely unit prices
    if price_value < 0.10:
        reject_reason = 'rejected_low_value'
    
    # Reject very high prices (> £50) for standard items
    if price_value > 50:
        reject_reason = 'rejected_high_value'
    
    # Check for per-unit pricing patterns in item name
    if reject_reason is None:
        name_lower = item_name.lower()
        # Items sold by weight shouldn't have suspiciously low prices
        if any(x in name_lower for x in ['per kg', '/kg', 'per lb']):
            if price_value < 0.50:
                reject_reason = 'rejected_unit_price_contamination'
    
    return reject_reason is None, reject_reason

def extract_prices(html, item_key, item_name):
    """Extract prices from Trolley.co.uk HTML with validation"""
    prices = {}
    rejects = []
    
    # Pattern to match supermarket and price
    patterns = {
        'tesco': r'Tesco[^£]*£(\d+\.\d{2})',
        'asda': r'ASDA[^£]*£(\d+\.\d{2})',
        'sainsburys': r"Sainsbury's[^£]*£(\d+\.\d{2})",
        'morrisons': r'Morrisons[^£]*£(\d+\.\d{2})',
        'aldi': r'Aldi[^£]*£(\d+\.\d{2})',
        'lidl': r'Lidl[^£]*£(\d+\.\d{2})',
        'waitrose': r'Waitrose[^£]*£(\d+\.\d{2})',
        'co-op': r'Co-?op[^£]*£(\d+\.\d{2})',
    }
    
    for supermarket, pattern in patterns.items():
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            price_value = float(match.group(1))
            is_valid, reject_reason = validate_price(price_value, item_key, item_name)
            
            if is_valid:
                prices[supermarket] = price_value
            else:
                rejects.append({
                    'item_key': item_key,
                    'store': supermarket,
                    'reason': reject_reason,
                    'price': price_value
                })
    
    return prices, rejects

def scrape_item(item_key, search_term):
    """Scrape prices for a single item"""
    encoded_term = urllib.parse.quote(search_term)
    url = f"https://www.trolley.co.uk/search/?q={encoded_term}"
    
    html = fetch_page(url, retries=3)
    if not html:
        return None, None, 'page_fetch_failed'
    
    prices, rejects = extract_prices(html, item_key, search_term)
    
    if not prices:
        return None, rejects, 'no_valid_prices'
    
    return {
        'item_key': item_key,
        'item_name': search_term,
        'prices': prices
    }, rejects, None

def call_ingest(action, payload, batch_size=None):
    """Call the ingest endpoint with optional batching"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    data = json.dumps({'action': action, 'payload': payload}).encode('utf-8')
    req = urllib.request.Request(INGEST_URL, data=data, headers={
        'Content-Type': 'application/json',
        'x-agent-key': AGENT_KEY
    })
    
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}

def upsert_batch(prices_batch):
    """Upsert a batch of prices"""
    result = call_ingest('upsert_prices', {'prices': prices_batch})
    return result

def main():
    import sys
    # Force unbuffered output
    sys.stdout = sys.stderr
    
    print("=" * 60, flush=True)
    print("TrolleyRoast - Full Category Sweep (Phase 1)", flush=True)
    print(f"Started: {datetime.now().isoformat()}", flush=True)
    print("=" * 60, flush=True)
    
    # Phase 1: Health check
    print("\n[1/5] Health check...")
    health = call_ingest('health_check', {})
    if health.get('status') != 'ok':
        print(f"✗ ERROR: Health check failed: {health}")
        return {'status': 'failed', 'reason': 'health_check_failed'}
    print(f"✓ Health check passed")
    
    # Phase 2: Build full item list
    print("\n[2/5] Building category query list...")
    all_items = []
    category_counts = {}
    
    for category, items in CATEGORY_CATALOGUE.items():
        category_counts[category] = len(items)
        for item_key, item_name in items:
            all_items.append((item_key, item_name, category))
    
    print(f"✓ Built {len(all_items)} items across {len(CATEGORY_CATALOGUE)} categories")
    for cat, count in category_counts.items():
        print(f"    - {cat}: {count} items")
    
    # Phase 3: Scrape all items with safe pacing
    print(f"\n[3/5] Scraping {len(all_items)} items from Trolley.co.uk...")
    
    scraped_data = []
    all_rejects = []
    errors = []
    stats_by_store = defaultdict(int)
    stats_by_category = defaultdict(lambda: {'attempted': 0, 'valid': 0, 'rejected': 0})
    
    BATCH_SIZE = 10  # Upsert every 10 items
    batch_prices = []
    
    for i, (item_key, item_name, category) in enumerate(all_items):
        progress = f"[{i+1}/{len(all_items)}]"
        print(f"  {progress} {item_name}...", end=' ')
        
        stats_by_category[category]['attempted'] += 1
        
        result, rejects, error = scrape_item(item_key, item_name)
        
        if error:
            print(f"✗ {error}")
            errors.append({'item_key': item_key, 'error': error})
            stats_by_category[category]['rejected'] += 1
        else:
            if result and result['prices']:
                scraped_data.append(result)
                stats_by_category[category]['valid'] += 1
                
                for supermarket, price in result['prices'].items():
                    batch_prices.append({
                        'supermarket': supermarket,
                        'item_key': item_key,
                        'item_name': item_name,
                        'price': price
                    })
                    stats_by_store[supermarket] += 1
                
                print(f"✓ {len(result['prices'])} stores")
            else:
                print("✗ no prices")
            
            if rejects:
                all_rejects.extend(rejects)
        
        # Upsert in batches
        if len(batch_prices) >= BATCH_SIZE:
            print(f"  → Upserting batch of {len(batch_prices)} prices...")
            upsert_result = upsert_batch(batch_prices)
            if 'error' in upsert_result:
                print(f"    ✗ Batch upsert error: {upsert_result['error']}")
            batch_prices = []
        
        # Rate limiting (2 seconds between requests)
        if i < len(all_items) - 1:
            time.sleep(2)
    
    # Final batch upsert
    if batch_prices:
        print(f"  → Upserting final batch of {len(batch_prices)} prices...")
        upsert_result = upsert_batch(batch_prices)
        if 'error' in upsert_result:
            print(f"    ✗ Final batch upsert error: {upsert_result['error']}")
    
    # Phase 4: Compile run report
    print("\n[4/5] Compiling run report...")
    
    # Calculate coverage gaps
    coverage_gaps = []
    for category, stats in stats_by_category.items():
        if stats['valid'] == 0:
            coverage_gaps.append({'category': category, 'reason': 'no_valid_data'})
    
    for store in SUPERMARKETS:
        if stats_by_store[store] == 0:
            coverage_gaps.append({'store': store, 'reason': 'no_prices_found'})
    
    # Aggregate reject reasons
    reject_reasons = defaultdict(int)
    for reject in all_rejects:
        reject_reasons[reject['reason']] += 1
    
    # Create report
    timestamp = datetime.now()
    report = {
        'run': 'full_category_sweep_phase1',
        'timestamp': timestamp.isoformat(),
        'health_status': 200,
        'summary': {
            'total_items_attempted': len(all_items),
            'successful_scrapes': len(scraped_data),
            'total_errors': len(errors),
            'total_valid_rows': sum(stats_by_store.values()),
            'total_rejects': len(all_rejects),
        },
        'by_category': dict(stats_by_category),
        'by_store': dict(stats_by_store),
        'reject_summary': {
            'total': len(all_rejects),
            'top_reasons': [{'reason': k, 'count': v} for k, v in sorted(reject_reasons.items(), key=lambda x: x[1], reverse=True)][:5],
            'sample_rejects': all_rejects[:10]  # First 10 for reference
        },
        'coverage_gaps': coverage_gaps,
        'errors_sample': errors[:10],  # First 10 errors
    }
    
    # Phase 5: Save report
    print("\n[5/5] Saving run report...")
    report_filename = f"phase1_sweep_{int(timestamp.timestamp())}.json"
    report_path = f"/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports/{report_filename}"
    
    try:
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"✓ Report saved to {report_path}")
    except Exception as e:
        print(f"✗ Failed to save report: {e}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"Items attempted: {report['summary']['total_items_attempted']}")
    print(f"Successful scrapes: {report['summary']['successful_scrapes']}")
    print(f"Valid rows written: {report['summary']['total_valid_rows']}")
    print(f"Rejects: {report['summary']['total_rejects']}")
    print(f"Errors: {report['summary']['total_errors']}")
    
    print("\n📊 By Store:")
    for store in SUPERMARKETS:
        count = stats_by_store.get(store, 0)
        print(f"    {store}: {count} rows")
    
    print("\n📊 Top Reject Reasons:")
    for reason in report['reject_summary']['top_reasons']:
        print(f"    {reason['reason']}: {reason['count']}")
    
    if coverage_gaps:
        print(f"\n⚠️ Coverage Gaps: {len(coverage_gaps)}")
        for gap in coverage_gaps[:5]:
            print(f"    {gap}")
    
    print("\n" + "=" * 60)
    print(f"Completed: {datetime.now().isoformat()}")
    print("=" * 60)
    
    return report

if __name__ == '__main__':
    main()
