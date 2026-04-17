#!/usr/bin/env python3
"""
TrolleyRoast Price Sweep v2
Scrapes trolley.co.uk for real UK supermarket prices, writes to Supabase,
and exports updated store index ratios that can replace engine.ts static values.

Usage:
  python3 price_sweep_v2.py              # full sweep (~20 min, 150 items)
  python3 price_sweep_v2.py --quick      # staples only (~3 min, 20 items)
  python3 price_sweep_v2.py --export     # write updated store_index.json only
"""

import json, re, time, os, sys, hashlib, ssl, urllib.request, urllib.parse
from datetime import datetime, timezone
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL", "https://oyqtywxocmqjtobkmoxj.supabase.co")
SUPABASE_KEY      = os.getenv("SUPABASE_SERVICE_KEY", "")
CRAWLER_ENDPOINT  = os.getenv("CRAWLER_ENDPOINT", "http://127.0.0.1:3000")
CRAWLER_API_KEY   = os.getenv("CRAWLER_API_KEY",  "")
RATE_LIMIT_SECS   = float(os.getenv("RATE_LIMIT_SECS", "2.5"))
TROLLEY_BASE      = "https://www.trolley.co.uk/search/?q="

QUICK_MODE  = "--quick"  in sys.argv
EXPORT_MODE = "--export" in sys.argv

if not SUPABASE_KEY and not EXPORT_MODE:
    raise SystemExit("SUPABASE_SERVICE_KEY is required")

if not CRAWLER_API_KEY and not EXPORT_MODE:
    raise SystemExit("CRAWLER_API_KEY is required")

# ── Item catalogue ─────────────────────────────────────────────────────────────
# Format: (canonical_key, search_term, category)
# These are the 20 staple items used in QUICK mode — they anchor the store indices
STAPLES = [
    ("milk_semi_4pt",         "Semi Skimmed Milk 4pt",           "dairy"),
    ("milk_whole_4pt",        "Whole Milk 4pt",                  "dairy"),
    ("butter_250g",           "Salted Butter 250g",              "dairy"),
    ("cheddar_400g",          "Mature Cheddar 400g",             "dairy"),
    ("eggs_medium_6",         "Eggs Medium 6",                   "eggs"),
    ("bread_white_800g",      "White Sliced Bread 800g",         "bakery"),
    ("bread_wholemeal_800g",  "Wholemeal Sliced Bread 800g",     "bakery"),
    ("chicken_breast_500g",   "Chicken Breast 500g",             "meat"),
    ("beef_mince_500g",       "Beef Mince 500g",                 "meat"),
    ("potatoes_2_5kg",        "Potatoes 2.5kg",                  "produce"),
    ("apples_6pack",          "Apples 6 Pack",                   "produce"),
    ("bananas_kg",            "Bananas per kg",                  "produce"),
    ("pasta_500g",            "Penne Pasta 500g",                "cupboard"),
    ("rice_1kg",              "Long Grain Rice 1kg",             "cupboard"),
    ("baked_beans_400g",      "Baked Beans 400g",                "cupboard"),
    ("chopped_tomatoes_400g", "Chopped Tomatoes 400g",           "cupboard"),
    ("washing_liquid_1l",     "Washing Up Liquid 1L",            "household"),
    ("toilet_rolls_9pk",      "Toilet Roll 9 Pack",              "household"),
    ("cornflakes_500g",       "Cornflakes 500g",                 "cereal"),
    ("orange_juice_1l",       "Orange Juice 1L Not From Concentrate", "drinks"),
]

EXTENDED = STAPLES + [
    # Dairy
    ("greek_yoghurt_500g",    "Greek Yoghurt 500g",              "dairy"),
    ("natural_yoghurt_500g",  "Natural Yoghurt 500g",            "dairy"),
    ("double_cream_300ml",    "Double Cream 300ml",              "dairy"),
    ("milk_semi_2pt",         "Semi Skimmed Milk 2pt",           "dairy"),
    # Bakery
    ("sourdough_400g",        "Sourdough Loaf",                  "bakery"),
    ("rolls_6pack",           "White Rolls 6 Pack",              "bakery"),
    ("crumpets_6pack",        "Crumpets 6 Pack",                 "bakery"),
    # Meat
    ("sausages_400g",         "Pork Sausages 400g",              "meat"),
    ("bacon_streaky_250g",    "Streaky Bacon 250g",              "meat"),
    ("salmon_fillet_2pack",   "Salmon Fillets 2 Pack",           "fish"),
    ("cod_fillet_2pack",      "Cod Fillets 2 Pack",              "fish"),
    # Produce
    ("carrots_1kg",           "Carrots 1kg",                     "produce"),
    ("broccoli_head",         "Broccoli",                        "produce"),
    ("onions_1kg",            "Onions 1kg",                      "produce"),
    ("baby_spinach_200g",     "Baby Spinach 200g",               "produce"),
    ("cherry_tomatoes_250g",  "Cherry Tomatoes 250g",            "produce"),
    # Cupboard
    ("olive_oil_500ml",       "Olive Oil 500ml",                 "cupboard"),
    ("sunflower_oil_1l",      "Sunflower Oil 1L",                "cupboard"),
    ("plain_flour_1_5kg",     "Plain Flour 1.5kg",               "cupboard"),
    ("sugar_1kg",             "Granulated Sugar 1kg",            "cupboard"),
    ("chicken_stock_cubes",   "Chicken Stock Cubes 10 Pack",     "cupboard"),
    ("spaghetti_500g",        "Spaghetti 500g",                  "cupboard"),
    ("tuna_chunks_145g",      "Tuna Chunks in Brine 145g",       "cupboard"),
    # Drinks
    ("cola_2l",               "Cola 2L",                         "drinks"),
    ("still_water_6x500ml",   "Still Water 6 x 500ml",          "drinks"),
    ("tea_bags_80",           "Tea Bags 80 Pack",                "drinks"),
    ("instant_coffee_100g",   "Instant Coffee 100g",             "drinks"),
    # Household
    ("washing_powder_1_5kg",  "Washing Powder 1.5kg",            "household"),
    ("bin_bags_50pk",         "Bin Bags 50 Pack",                "household"),
    ("kitchen_roll_2pk",      "Kitchen Roll 2 Pack",             "household"),
    # Baby & Toiletries
    ("nappies_size3_56pk",    "Nappies Size 3 56 Pack",          "baby"),
    ("shampoo_400ml",         "Shampoo 400ml",                   "toiletries"),
    ("shower_gel_500ml",      "Shower Gel 500ml",                "toiletries"),
    # Frozen
    ("frozen_peas_900g",      "Frozen Peas 900g",                "frozen"),
    ("frozen_chips_1kg",      "Frozen Chips 1kg",                "frozen"),
    ("fish_fingers_10pk",     "Fish Fingers 10 Pack",            "frozen"),
    # Snacks
    ("crisps_6pack",          "Ready Salted Crisps 6 Pack",      "snacks"),
    ("digestive_biscuits",    "Digestive Biscuits 400g",         "snacks"),
]

CATALOGUE = STAPLES if QUICK_MODE else EXTENDED

STORES = ["tesco", "asda", "sainsburys", "morrisons", "aldi", "lidl", "waitrose", "co-op"]

# ── FastCRW client ─────────────────────────────────────────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

def scrape(url: str) -> dict:
    payload = json.dumps({"url": url, "formats": ["markdown"]}).encode()
    req = urllib.request.Request(
        f"{CRAWLER_ENDPOINT}/v1/scrape",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {CRAWLER_API_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx) as r:
            body = json.loads(r.read().decode())
            md = body.get("data", {}).get("markdown", "")
            return {"content": md} if md else {"error": "empty markdown"}
    except Exception as e:
        return {"error": str(e)}

# ── Price parser ───────────────────────────────────────────────────────────────
# Trolley.co.uk markdown format: StoreName appears as a standalone line,
# followed within a few lines by £price.
STORE_ALIASES = {
    "tesco":      ["Tesco"],
    "asda":       ["ASDA", "Asda"],
    "sainsburys": ["Sainsbury's", "Sainsburys"],
    "morrisons":  ["Morrisons"],
    "aldi":       ["Aldi"],
    "lidl":       ["Lidl"],
    "waitrose":   ["Waitrose Ltd", "Waitrose"],
    "co-op":      ["Co-op", "Coop"],
}

def parse_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    lines = [l.strip() for l in text.split("\n")]
    for i, line in enumerate(lines):
        for store_key, aliases in STORE_ALIASES.items():
            for alias in aliases:
                if line == alias or line.startswith(alias + " "):
                    # Search next 6 lines for the first standalone £X.XX price
                    for j in range(i + 1, min(i + 7, len(lines))):
                        m = re.fullmatch(r"£(\d+\.\d{2})", lines[j])
                        if m:
                            price = float(m.group(1))
                            # Keep the lowest price seen for this store
                            if store_key not in prices or price < prices[store_key]:
                                prices[store_key] = price
                            break
                    break
    return prices

# ── Supabase helpers ───────────────────────────────────────────────────────────
def _supa_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

def upsert_price(item_key: str, item_name: str, category: str, store: str, price: float) -> bool:
    now = datetime.now(timezone.utc)
    row = {
        "item_key": item_key,
        "item_name": item_name,
        "category": category,
        "store": store,
        "price_gbp": round(price, 2),
        "snapshot_date": now.date().isoformat(),
        "observed_at": now.isoformat(),
    }
    payload = json.dumps([row]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/price_snapshots?on_conflict=item_key,store,snapshot_date",
        data=payload,
        headers=_supa_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as r:
            return r.status in (200, 201, 204)
    except Exception as e:
        print(f"    [DB error] {e}")
        return False

# ── Store index calculator ─────────────────────────────────────────────────────
def compute_store_index(all_prices: dict) -> dict[str, float]:
    """
    Given {item_key: {store: price}}, compute a relative store index
    where sainsburys = 1.0 (matching the engine.ts convention).
    Only items where >= 4 stores have prices are used as anchors.
    """
    store_ratios: dict[str, list[float]] = defaultdict(list)
    baseline = "sainsburys"

    for item_key, store_prices in all_prices.items():
        if baseline not in store_prices or len(store_prices) < 4:
            continue
        base_price = store_prices[baseline]
        if base_price <= 0:
            continue
        for store, price in store_prices.items():
            ratio = price / base_price
            # Sanity-check: reject ratios outside 0.3–2.5 (likely parse errors)
            if 0.3 <= ratio <= 2.5:
                store_ratios[store].append(ratio)

    index = {}
    for store, ratios in store_ratios.items():
        if len(ratios) >= 3:
            # Trimmed mean (drop top/bottom 10%)
            ratios_sorted = sorted(ratios)
            trim = max(1, len(ratios_sorted) // 10)
            trimmed = ratios_sorted[trim:-trim] if trim else ratios_sorted
            index[store] = round(sum(trimmed) / len(trimmed), 4)

    return dict(sorted(index.items(), key=lambda x: x[1]))

# ── Main sweep ────────────────────────────────────────────────────────────────
def main():
    mode = "QUICK" if QUICK_MODE else "FULL"
    print(f"\n{'='*60}")
    print(f"  TrolleyRoast Price Sweep v2 — {mode} MODE")
    print(f"  {len(CATALOGUE)} items · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    all_prices: dict[str, dict[str, float]] = {}
    success_count = 0
    fail_count = 0

    for item_key, item_name, category in CATALOGUE:
        url = TROLLEY_BASE + urllib.parse.quote(item_name)
        print(f"  ↳ {item_name}")

        result = scrape(url)
        if "error" in result:
            print(f"    [SKIP] Crawler error: {result['error']}")
            fail_count += 1
            time.sleep(RATE_LIMIT_SECS)
            continue

        prices = parse_prices(result.get("content", ""))

        if not prices:
            print(f"    [SKIP] No prices parsed")
            fail_count += 1
            time.sleep(RATE_LIMIT_SECS)
            continue

        all_prices[item_key] = prices
        stores_found = ", ".join(f"{s}=£{p:.2f}" for s, p in sorted(prices.items()))
        print(f"    {stores_found}")

        for store, price in prices.items():
            upsert_price(item_key, item_name, category, store, price)

        success_count += 1
        time.sleep(RATE_LIMIT_SECS)

    # ── Compute and save updated store index ──────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Sweep complete: {success_count} ok / {fail_count} failed")
    print(f"{'='*60}\n")

    if all_prices:
        store_index = compute_store_index(all_prices)
        print("  Updated store indices (sainsburys = 1.0):")
        for store, idx in store_index.items():
            current = {"aldi":0.79,"lidl":0.81,"asda":0.88,"tesco":0.93,"morrisons":0.95,"sainsburys":1.0,"waitrose":1.13,"co-op":1.09}
            diff = idx - current.get(store, 1.0)
            arrow = "↑" if diff > 0.01 else ("↓" if diff < -0.01 else "→")
            print(f"    {store:<14} {idx:.4f}  {arrow} (was {current.get(store,'?')})")

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "item_count": success_count,
            "store_index": store_index,
            "note": "Replace STORE_INDEX in src/lib/calculators/engine.ts with these values",
        }
        out_path = os.path.join(os.path.dirname(__file__), "store_index_live.json")
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  ✅ Saved to {out_path}")
        print("  Copy store_index values into engine.ts STORE_INDEX to use live data.\n")
    else:
        print("  ⚠️  No prices collected — check FastCRW is running (localhost:3000)\n")

if __name__ == "__main__":
    main()
