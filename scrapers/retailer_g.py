"""Retailer G scraper."""
import json, re
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerGScraper(BaseScraper):
    name = "RETAILER G"

    def extract(self, page: Page, url: str) -> dict:
        # Active price from JSON-LD (most reliable)
        active_price = None
        for el in page.query_selector_all('script[type="application/ld+json"]'):
            try:
                data = json.loads(el.inner_text())
                if "offers" in data:
                    p = self.parse_price(str(data["offers"].get("price", "")))
                    if p:
                        active_price = p
                        break
            except Exception:
                continue

        # List price: was-price elements that are GREATER than active price.
        # Recommendation widgets also use was-price but with lower values — filter those out.
        list_price = None
        for el in page.query_selector_all(".was-price"):
            match = re.search(r'\$([\d,]+\.?\d*)', el.inner_text())
            if match:
                candidate = self.parse_price(match.group(1))
                if candidate and active_price and candidate > active_price:
                    list_price = candidate
                    break

        if list_price:
            return {"comp_list_price": list_price, "comp_sale_price": active_price}

        # No valid was-price: not on sale
        return {"comp_list_price": active_price, "comp_sale_price": None}
