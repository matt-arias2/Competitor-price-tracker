"""Retailer H scraper — Shopify store.

Retailer H embeds a per-store pricing JSON object in the server-rendered HTML. Each store
entry has a `webPrice` field (the actual selling price) which may differ from the
Shopify product JSON API `price` (which returns the region MSRP, not the web price).

We fetch the product page via HTTP, parse the store JSON with raw_decode(), and
take the minimum `webPrice` across all stores — this matches the promotional price
shown to customers in the majority of Retailer H's markets.
"""
import json
import re
import time
from curl_cffi import requests as cffi_requests
from playwright.sync_api import Page
from .base import BaseScraper

_decoder = json.JSONDecoder()


class RetailerHScraper(BaseScraper):
    name = "RETAILER H"
    use_http = True

    def fetch_and_extract(self, url: str) -> dict:
        # Retailer H's Shopify store rate-limits aggressively on sequential requests
        # from the same IP — retry with backoff on 429 before giving up.
        r = None
        for attempt, backoff in enumerate((0, 5, 15, 30)):
            if backoff:
                time.sleep(backoff)
            r = cffi_requests.get(url, impersonate="chrome120", timeout=20)
            if r.status_code != 429:
                break
        r.raise_for_status()

        # Locate the store pricing JSON embedded in the page HTML.
        # Format: {"AA": {"webPrice": X, "regionPrice": Y, "onSale": "Y"/"N", ...}, ...}
        m = re.search(r'\{"[A-Z0-9]{2}":\{', r.text)
        if m:
            try:
                stores, _ = _decoder.raw_decode(r.text, m.start())
                web_prices = [
                    v["webPrice"] for v in stores.values()
                    if isinstance(v, dict) and v.get("webPrice")
                ]
                if web_prices:
                    price = self.parse_price(str(min(web_prices)))
                    return {"comp_list_price": price, "comp_sale_price": None}
            except Exception:
                pass

        return {"comp_list_price": None, "comp_sale_price": None}

    def extract(self, page: Page, url: str) -> dict:
        return {"comp_list_price": None, "comp_sale_price": None}
