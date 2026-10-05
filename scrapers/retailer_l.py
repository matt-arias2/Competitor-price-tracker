"""Retailer L scraper — requires Firefox."""
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerLScraper(BaseScraper):
    name = "RETAILER L"
    browser_type = "firefox"  # signal to runner to use Firefox

    def extract(self, page: Page, url: str) -> dict:
        # Sale price: bpc-price-label with sale-color class
        sale_price = None
        sale_el = page.query_selector("bpc-price-label.sale-color .price-label")
        if sale_el:
            sale_price = self.parse_price(sale_el.inner_text())

        # List price: bpc-price-label with line-through class
        list_price = None
        list_el = page.query_selector("bpc-price-label.line-through .price-label")
        if list_el:
            list_price = self.parse_price(list_el.inner_text())

        # Fallback: generic price element
        if sale_price is None:
            el = page.query_selector("[class*='sale-price'] .price-label, [class*='price'] .price-label")
            if el:
                sale_price = self.parse_price(el.inner_text())

        if list_price is None:
            list_price = sale_price
            sale_price = None

        return {"comp_list_price": list_price, "comp_sale_price": sale_price}
