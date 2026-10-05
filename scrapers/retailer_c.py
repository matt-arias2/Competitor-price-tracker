"""Retailer C scraper."""
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerCScraper(BaseScraper):
    name = "RETAILER C"

    def extract(self, page: Page, url: str) -> dict:
        # On sale: sale-price (active) + list-price-sale (original, strikethrough)
        sale_el = page.query_selector('[data-testid="q-price__sale-price"]')
        if sale_el:
            sale_price = self.parse_price(sale_el.inner_text())
            list_el = page.query_selector('[data-testid="q-price__list-price-sale"]')
            list_price = self.parse_price(list_el.inner_text()) if list_el else None
            return {"comp_list_price": list_price, "comp_sale_price": sale_price}

        # Not on sale: single list-price element, no strikethrough
        list_el = page.query_selector('[data-testid="q-price__list-price"]')
        if list_el:
            list_price = self.parse_price(list_el.inner_text())
            return {"comp_list_price": list_price, "comp_sale_price": None}

        return {"comp_list_price": None, "comp_sale_price": None}
