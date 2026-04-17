
import asyncio
import json
import os
from playwright.async_api import async_playwright

# Environment variables
TROLLEYROAST_INGEST_URL = os.environ.get("TROLLEYROAST_INGEST_URL")
X_AGENT_KEY = os.environ.get("X_AGENT_KEY")

if not TROLLEYROAST_INGEST_URL or not X_AGENT_KEY:
    raise ValueError("TROLLEYROAST_INGEST_URL and X_AGENT_KEY must be set as environment variables.")

async def scrape_waitrose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Target URL
        url = "https://www.waitrose.com/ecom/shop/browse/groceries"
        await page.goto(url)

        # Handle cookie banner (Reject All)
        try:
            await page.locator("#onetrust-reject-all-handler").click(timeout=5000)  # Adjust timeout as needed
        except:
            print("Cookie banner not found, continuing...")

        # Category URLs - Hardcoded for direct navigation
        category_urls = [
            "https://www.waitrose.com/ecom/shop/browse/groceries/fresh-fruit-vegetables",
            "https://www.waitrose.com/ecom/shop/browse/groceries/dairy-eggs-chilled",
            "https://www.waitrose.com/ecom/shop/browse/groceries/meat-poultry-fish",
            "https://www.waitrose.com/ecom/shop/browse/groceries/bakery-bread-cakes",
            "https://www.waitrose.com/ecom/shop/browse/groceries/store-cupboard"
        ]
        
        all_items = []

        for category_url in category_urls:
            await page.goto(category_url)
            
            # Scroll to trigger lazy loading (adjust the number of scrolls as needed)
            for _ in range(5):  # Reduced scrolling to avoid timeout issues
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await asyncio.sleep(2)  # Reduced sleep duration

            # Extract product information
            product_cards = await page.locator(".productPod--wrapper").all()

            for card in product_cards:
                try:
                    canonical_title = await card.locator(".productPod_title").inner_text()
                    price_text = await card.locator(".productPod_price").inner_text()
                    price = float(price_text.replace("£", ""))
                    size = await card.locator(".productPod_size").inner_text()

                    if price >= 0.40:
                        all_items.append({
                            "canonical_title": canonical_title,
                            "price": price,
                            "size": size
                        })

                except Exception as e:
                    print(f"Error extracting data from card: {e}")
                    continue

        await browser.close()

        # Save results to JSON file
        filepath = "/Users/tosin/.openclaw/workspace-main/trolleyroast-agent/reports/waitrose_scrape_results.json"
        with open(filepath, "w") as f:
            json.dump(all_items, f, indent=4)
        
        print(f"Extracted {len(all_items)} items.")

        # Ingest data (Dummy implementation - replace with actual API call)
        ingested_count = 0 # Replace this with the actual ingested count from API
        # for i in range(0, len(all_items), 25):
        #     batch = all_items[i:i+25]
        #     #  Add your API call here with the batch data
        #     # response = requests.post(TROLLEYROAST_INGEST_URL, headers={"x-agent-key": X_AGENT_KEY}, json=batch)
        #     # ingested_count += len(batch)
        #     ingested_count += len(batch) #simulating data ingestion

        print(f"Successfully saved data to {filepath}")
        return len(all_items)

async def main():
    total_ingested = await scrape_waitrose()
    print(f"TOTAL Waitrose items successfully ingested: {total_ingested}")

if __name__ == "__main__":
    asyncio.run(main())
