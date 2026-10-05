"""Retailer J scraper."""
import json, re
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerJScraper(BaseScraper):
    name = "RETAILER J"

    def extract(self, page: Page, url: str) -> dict:
        # Current selling price from JSON-LD.
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

        # Was/original price shown on-page when the item is marked down.
        # Element class contains "OriginalValueLabel"; text is formatted "was$X,XXX.XX".
        was_price = None
        for el in page.query_selector_all('[class*=OriginalValueLabel]'):
            try:
                text = el.text_content().strip()
                p = self.parse_price(re.sub(r'^was', '', text, flags=re.I).strip())
                if p and active_price and p > active_price:
                    was_price = p
                    break
            except Exception:
                continue

        if was_price:
            return {"comp_list_price": was_price, "comp_sale_price": active_price}

        return {"comp_list_price": active_price, "comp_sale_price": None}
