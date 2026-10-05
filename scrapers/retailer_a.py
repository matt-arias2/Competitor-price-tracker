"""Retailer A scraper."""
import json, re
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerAScraper(BaseScraper):
    name = "RETAILER A"

    def extract(self, page: Page, url: str) -> dict:
        # JSON-LD is most reliable
        ld_blocks = page.query_selector_all('script[type="application/ld+json"]')
        for el in ld_blocks:
            try:
                data = json.loads(el.inner_text())
                if "offers" in data:
                    active = self.parse_price(str(data["offers"].get("price", "")))
                    if active:
                        # Retailer A typically shows one price; check for a sale element
                        sale_el = page.query_selector("[class*='sale-price'], [class*='special-price']")
                        if sale_el:
                            sale = self.parse_price(sale_el.inner_text())
                            return {"comp_list_price": active, "comp_sale_price": sale}
                        return {"comp_list_price": active, "comp_sale_price": None}
            except Exception:
                continue

        # Fallback: product-price element
        el = page.query_selector("[class*='product-price']")
        price = self.parse_price(el.inner_text()) if el else None
        return {"comp_list_price": price, "comp_sale_price": None}
