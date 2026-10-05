"""Retailer K scraper — uses curl_cffi HTTP with JSON-LD + inline JS price data."""
import json, re, time
from curl_cffi import requests as cffi_requests
from playwright.sync_api import Page
from .base import BaseScraper

_RETRY_DELAY = 4   # seconds to wait before retrying after a timeout
_MAX_RETRIES = 2


class RetailerKScraper(BaseScraper):
    name = "RETAILER K"
    use_http = True  # skip Playwright; use fetch_and_extract() instead

    def fetch_and_extract(self, url: str) -> dict:
        last_exc = None
        for attempt in range(_MAX_RETRIES):
            try:
                r = cffi_requests.get(url, impersonate="chrome120", timeout=30)
                break
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
        else:
            raise last_exc
        r.raise_for_status()

        # Active/sale price from inline JS: specialPrice: 699.99
        # Regular price from inline JS:    price: 799.99
        # These appear as JS object literals in the page source.
        special_match = re.search(r'\bspecialPrice:\s*([\d.]+)', r.text)
        price_match   = re.search(r'\bprice:\s*([\d.]+),', r.text)

        if special_match and price_match:
            sale_price = self.parse_price(special_match.group(1))
            list_price = self.parse_price(price_match.group(1))
            # specialPrice: 0 means no sale — explicitly guard against it
            if list_price and sale_price and sale_price > 0 and sale_price < list_price:
                return {"comp_list_price": list_price, "comp_sale_price": sale_price}
            # No active sale (specialPrice 0 or missing) — regular price still applies
            if list_price:
                return {"comp_list_price": list_price, "comp_sale_price": None}

        # Fallback: JSON-LD Product offer price (regular price)
        ld_blocks = re.findall(r'application/ld\+json[^>]*>(.*?)</script>', r.text, re.S)
        for block in ld_blocks:
            try:
                data = json.loads(block)
                if data.get("@type") == "Product" and "offers" in data:
                    offers = data["offers"]
                    if isinstance(offers, list):
                        offers = offers[0]
                    active = self.parse_price(str(offers.get("price", "")))
                    if active:
                        return {"comp_list_price": active, "comp_sale_price": None}
            except Exception:
                continue

        return {"comp_list_price": None, "comp_sale_price": None}

    def extract(self, page: Page, url: str) -> dict:
        return {"comp_list_price": None, "comp_sale_price": None}
