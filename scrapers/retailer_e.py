"""Retailer E scraper."""
import re
from playwright.sync_api import Page
from .base import BaseScraper


class RetailerEScraper(BaseScraper):
    name = "RETAILER E"

    def extract(self, page: Page, url: str) -> dict:
        # Sale/active price: try itemprop="price" then itemprop="lowPrice" (used on sale pages)
        sale_price = None
        for attr in ("price", "lowPrice"):
            el = page.query_selector(f'[itemprop="{attr}"]')
            if el:
                sale_price = self.parse_price(el.get_attribute("content"))
                if sale_price:
                    break

        # Explicit "Event/Final" price element (overrides itemprop when present)
        event_el = page.query_selector(".PriceRow__price--Event .price")
        if event_el:
            p = self._parse_hom_price(event_el.inner_html())
            if p:
                sale_price = p

        # List/regular price: strikethrough "Reg" element
        list_price = None
        reg_el = page.query_selector(".PriceRow__price--strikeThrough .price")
        if reg_el:
            list_price = self._parse_hom_price(reg_el.inner_html())

        # If there's no strikethrough, not on sale — active price is the list price
        if list_price is None:
            list_price = sale_price
            sale_price = None
        elif sale_price is None:
            # Strikethrough found but no active price — shouldn't happen, but fallback
            sale_price = list_price
            list_price = None

        return {"comp_list_price": list_price, "comp_sale_price": sale_price}

    @staticmethod
    def _parse_hom_price(html: str) -> float | None:
        """
        Parse Retailer E's split price format:
          <sup>$</sup>339<sup>99</sup>       → 339.99
          <sup>$</sup>1,499<sup>99</sup>     → 1499.99  (comma in main number)
        Strategy: extract cents from last <sup>NN</sup>, then extract main dollar
        digits from remaining text (strip commas/tags).
        """
        # Cents: last <sup> with exactly 2 digits
        cents_match = re.search(r'<sup>(\d{2})</sup>', html)
        if not cents_match:
            # Fallback: strip tags, parse plain text
            return BaseScraper.parse_price(re.sub(r'<[^>]+>', '', html))

        cents = cents_match.group(1)

        # Strip all tags to get raw text, then remove non-numeric chars except dot
        text = re.sub(r'<[^>]+>', '', html)          # e.g. "$1,49999" or "$33999"
        text = re.sub(r'[^0-9]', '', text)            # e.g. "149999" or "33999"

        # Remove the cents digits from the end to get the main dollar amount
        if text.endswith(cents):
            main = text[:-len(cents)]                  # "1499" or "339"
            if main:
                try:
                    return float(f"{main}.{cents}")
                except ValueError:
                    pass

        # Fallback: treat entire stripped text as the price (e.g., no cents)
        return BaseScraper.parse_price(text) if text else None
