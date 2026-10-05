"""Retailer I scraper — requires Firefox."""
import json, re
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerIScraper(BaseScraper):
    name = "RETAILER I"
    browser_type = "firefox"  # signal to runner to use Firefox

    def extract(self, page: Page, url: str) -> dict:
        # Sale/active price from JSON-LD
        sale_price = None
        ld_blocks = page.query_selector_all('script[type="application/ld+json"]')
        for el in ld_blocks:
            try:
                data = json.loads(el.inner_text())
                if "offers" in data:
                    p = self.parse_price(str(data["offers"].get("price", "")))
                    if p:
                        sale_price = p
                        break
            except Exception:
                continue

        # Fallback: [class*='sale'] element
        if sale_price is None:
            sale_el = page.query_selector("[class*='sale-price'], [class*='salePrice']")
            if sale_el:
                sale_price = self.parse_price(sale_el.inner_text())

        # Comp/list value: "Comp. Value $X,XXX.XX"
        list_price = None
        msrp_el = page.query_selector("[class*='msrp'], [class*='comp-value'], [class*='compValue']")
        if msrp_el:
            match = re.search(r'\$([\d,]+\.?\d*)', msrp_el.inner_text())
            if match:
                list_price = self.parse_price(match.group(1))

        # Also scan body text for "Comp. Value $X"
        if list_price is None:
            body_text = page.inner_text("body")
            match = re.search(r'Comp\.?\s*Value\s+\$([\d,]+\.?\d*)', body_text, re.IGNORECASE)
            if match:
                list_price = self.parse_price(match.group(1))

        if list_price is None:
            list_price = sale_price
            sale_price = None

        return {"comp_list_price": list_price, "comp_sale_price": sale_price}
