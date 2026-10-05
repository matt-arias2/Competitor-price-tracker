"""
Base scraper class. Each retailer module subclasses this and implements extract().
"""
from abc import ABC, abstractmethod
from playwright.sync_api import Page


class BaseScraper(ABC):
    """
    Subclass this for each retailer.
    Implement extract(page, url) → dict with keys:
        comp_list_price: float | None
        comp_sale_price: float | None
    """

    # Retailer name — set in each subclass
    name: str = ""

    @abstractmethod
    def extract(self, page: Page, url: str) -> dict:
        """
        Given a loaded Playwright page, return a dict:
        {
            "comp_list_price": float | None,
            "comp_sale_price": float | None,
        }
        Return None values when a price cannot be found.
        Raise an exception to signal a scrape failure.
        """
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_price(text: str | None) -> float | None:
        """Strip currency symbols/commas and convert to float."""
        if not text:
            return None
        cleaned = text.strip().replace("$", "").replace(",", "").replace("\xa0", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
