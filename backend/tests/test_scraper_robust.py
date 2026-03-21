import asyncio
import sys
import os
import logging

# Enable logging to see scraper stages
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Add backend to path so we can import utils
sys.path.append(os.getcwd())

from utils.scraper import scrape_url

async def test_scraper(url):
    print(f"\n--- Testing URL: {url} ---")
    try:
        result = await scrape_url(url)
        print(f"Status: SUCCESS")
        print(f"Title: {result.get('title')}")
        print(f"Word Count: {len(result.get('text', '').split())}")
        print(f"Images Found: {len(result.get('images', []))}")
        # print(f"Preview: {result.get('text')[:200]}...")
    except Exception as e:
        print(f"Status: FAILED")
        print(f"Error: {e}")

async def main():
    urls = [
        "https://example.com",
        "https://www.wikipedia.org",
        # Add a JS-heavy or problematic URL if possible
        # "https://www.bloomberg.com/search?query=AI" 
    ]
    if len(sys.argv) > 1:
        urls = sys.argv[1:]
        
    for url in urls:
        await test_scraper(url)

if __name__ == "__main__":
    asyncio.run(main())
