"""
Retailer B scraper.

React/MUI app — no JSON-LD. Prices are in [data-avb-product-price] attributes.
Requires Firefox; Chromium returns an empty DOM on this site.
"""
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerBScraper(BaseScraper):
    name = "RETAILER B"
    browser_type = "firefox"

    def extract(self, page: Page, url: str) -> dict:
        # React/MUI renders after domcontentloaded — wait for the price element explicitly
        try:
            page.wait_for_selector("[data-avb-product-price]", timeout=8000)
        except Exception:
            return {"comp_list_price": None, "comp_sale_price": None}

        # Active price: first [data-avb-product-price] on the page (main PDP, before related-items grid)
        # Text is either "Sale $X.XX" (on sale) or "$X.XX" (regular price)
        price_el = page.query_selector("[data-avb-product-price]")
        if not price_el:
            return {"comp_list_price": None, "comp_sale_price": None}

        price_text = price_el.inner_text().strip()
        active = self.parse_price(price_text.replace("Sale", "").strip())
        if not active:
            return {"comp_list_price": None, "comp_sale_price": None}

        # Compare-at/was price: "Compare at $X.XX" — main PDP variant excludes GridTile suffix
        was_el = page.query_selector("[class*='productPriceWasPrice']:not([class*='GridTile'])")
        if was_el:
            was_price = self.parse_price(
                was_el.inner_text().replace("Compare at", "").strip()
            )
            if was_price and was_price > active:
                return {"comp_list_price": was_price, "comp_sale_price": active}

        return {"comp_list_price": active, "comp_sale_price": None}
