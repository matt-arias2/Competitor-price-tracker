"""Retailer D scraper."""
import json, re
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerDScraper(BaseScraper):
    name = "RETAILER D"

    def extract(self, page: Page, url: str) -> dict:
        # Collect all prices from JSON-LD offers blocks.
        # Package/sale pages emit two blocks: one for the regular price (no expiry)
        # and one for the current sale price (with priceValidUntil). We want both.
        prices = []
        for el in page.query_selector_all('script[type="application/ld+json"]'):
            try:
                data = json.loads(el.inner_text())
                if "offers" in data:
                    p = self.parse_price(str(data["offers"].get("price", "")))
                    if p:
                        prices.append(p)
            except Exception:
                continue

        if not prices:
            return {"comp_list_price": None, "comp_sale_price": None}

        if len(prices) >= 2:
            # Two blocks = regular price + sale price; highest is list, lowest is sale.
            return {"comp_list_price": max(prices), "comp_sale_price": min(prices)}

        # Single price — also check the page's CompareAtPrice (market reference Retailer D
        # displays as "Competition $X"), which can serve as a meaningful list benchmark.
        active_price = prices[0]
        compare_at = None
        try:
            content = page.content()
            m = re.search(r'"CompareAtPrice"\s*:\s*"?([\d.]+)"?', content)
            if m:
                compare_at = self.parse_price(m.group(1))
        except Exception:
            pass

        if compare_at and compare_at > active_price:
            return {"comp_list_price": compare_at, "comp_sale_price": active_price}

        return {"comp_list_price": active_price, "comp_sale_price": None}
