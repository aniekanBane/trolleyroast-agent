#!/usr/bin/env python3
"""TrolleyPriceBot - Nightly Price Scraper"""
import json
import re
import time
import os
from crawler_utils import crawl

# Load environment
INGEST_URL = os.getenv('TROLLEYROAST_INGEST_URL', 'https://czmvyblgviwgczfzxhsr.supabase.co/functions/v1/agent-ingest')
AGENT_KEY = os.getenv('TROLLEYROAST_AGENT_KEY', os.getenv('TROLLEYROAST_AGENT', ''))

MONITORED_ITEMS = [
    ("milk_semi_4pt", "Semi Skimmed Milk 4pt"),
    ("milk_whole_4pt", "Whole Milk 4pt"),
    ("butter_salted_250g", "Salted Butter 250g"),
    ("bread_white_800g", "Medium White Sliced Bread 800g"),
    ("chicken_breast_500g", "Chicken Breast 500g"),
    ("eggs_medium_6", "Eggs Medium 6"),
    ("eggs_large_12", "Eggs Large 12"),
    ("bananas_kg", "Bananas per kg"),
    ("apples_6pack", "Apples 6 Pack"),
    ("potatoes_2_5kg", "Potatoes 2.5kg"),
]

def fetch_page(url):
    """Fetch page content using fastCRW"""
    result = crawl(url, render=True)
    if 'error' in result:
        print(f"Crawler error: {result['error']}")
        return None
    return result.get('content', '')

def extract_prices(html, item_name):
    """Extract prices from Trolley.co.uk HTML"""
    prices = {}
    patterns = {
        'tesco': r'Tesco[^£]*£(\d+\.\d{2})',
        'asda': r'ASDA[^£]*£(\d+\.\d{2})',
        'sainsburys': r"Sainsbury's[^£]*£(\d+\.\d{2})",
        'morrisons': r'Morrisons[^£]*£(\d+\.\d{2})',
        'aldi': r'Aldi[^£]*£(\d+\.\d{2})',
        'lidl': r'Lidl[^£]*£(\d+\.\d{2})',
    }
    
    for supermarket, pattern in patterns.items():
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            prices[supermarket] = float(match.group(1))
    
    return prices

def scrape_item(item_key, search_term):
    """Scrape prices for a single item"""
    import urllib.parse
    encoded_term = urllib.parse.quote(search_term)
    url = f"https://www.trolley.co.uk/search/?q={encoded_term}"
    
    html = fetch_page(url)
    if not html:
        return None
    
    prices = extract_prices(html, search_term)
    return {
        'item_key': item_key,
        'item_name': search_term,
        'prices': prices
    }

def main():
    print("TrolleyPriceBot - Nightly Price Update (via fastCRW)")
    
    for item_key, item_name in MONITORED_ITEMS:
        print(f"Scraping {item_name}...")
        res = scrape_item(item_key, item_name)
        print(f"Results: {res}")
        time.sleep(2)

if __name__ == "__main__":
    main()
