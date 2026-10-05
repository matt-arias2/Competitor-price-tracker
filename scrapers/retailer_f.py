"""Retailer F scraper — uses curl_cffi to bypass Cloudflare."""
import json, re
from playwright.sync_api import Page
from curl_cffi import requests as cffi_requests
from .base import BaseScraper


class RetailerFScraper(BaseScraper):
    name = "RETAILER F"
    use_http = True  # skip Playwright; use fetch_and_extract() instead

    def fetch_and_extract(self, url: str) -> dict:
        r = cffi_requests.get(url, impersonate="chrome110", timeout=20)
        r.raise_for_status()

        # JSON-LD Product block
        ld_matches = re.findall(
            r'application/ld\+json[^>]*>(.*?)</script>', r.text, re.S
        )
        active_price = None
        for block in ld_matches:
            try:
                data = json.loads(block)
                if data.get("@type") == "Product" and "offers" in data:
                    active_price = self.parse_price(
                        str(data["offers"].get("price", ""))
                    )
                    break
            except Exception:
                continue

        # Look for a separate was/regular price in the HTML.
        # Restrict search to the main product section only — carousels/featured items
        # further down the page can contain "Original Price" text for OTHER products,
        # which would falsely fire as a was-price for the main item.
        list_price = None
        search_html = r.text
        for marker in ['id="recommendation"', 'id="cross-sell"', 'id="upsell"',
                       'also-viewed', 'featured-products', 'carousel']:
            idx = search_html.find(marker)
            if 0 < idx < len(search_html) // 2:  # only truncate if found in second half
                search_html = search_html[:idx]
                break
        was_match = re.search(
            r'\b(?:was|regular[- ]price|original[- ]price)\b[^$]{0,60}\$([\d,]+\.?\d*)',
            search_html, re.I
        )
        if was_match:
            list_price = self.parse_price(was_match.group(1))

        if list_price and list_price != active_price:
            return {"comp_list_price": list_price, "comp_sale_price": active_price}

        return {"comp_list_price": active_price, "comp_sale_price": None}

    def extract(self, page: Page, url: str) -> dict:
        # Fallback if called via Playwright path (should not happen normally)
        return {"comp_list_price": None, "comp_sale_price": None}
