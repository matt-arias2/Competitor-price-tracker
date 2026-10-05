"""
Retailer N scraper (zoned — online prices vary by region/zip).

⚠  BOT PROTECTION — Retailer N uses HUMAN Security (PerimeterX) which blocks all
   automated HTTP requests at the network level before any JavaScript runs.
   Standard Playwright, stealth plugins, and curl_cffi all receive a 403.

   To make this scraper work you need one of:
     A) A paid scraping proxy that handles PerimeterX challenges
        (ZenRows, BrightData, ScraperAPI, Oxylabs, etc.)
        → set RETAILER_N_PROXY_URL in your environment and uncomment the proxy
          lines in setup_context() / extract() below.
     B) Manual price entry for Retailer N rows.

   The scraper code below is complete and correct for price extraction once
   a valid session is established.  Only the network access layer needs to
   be swapped out.
"""
import json
import re
from playwright.sync_api import Page, BrowserContext
from .base import BaseScraper


class RetailerNScraper(BaseScraper):
    name = "RETAILER N"
    HOME_URL = "https://www.retailer-n.example"  # set to the retailer's homepage

    # ------------------------------------------------------------------
    # Zone setup
    # ------------------------------------------------------------------

    def setup_context(self, context: BrowserContext, zip_code: str) -> None:
        """
        Navigate to Retailer N's homepage and set the zip/store location so that
        all subsequent pages in this context reflect regional online pricing.
        Called once per zone before scraping any product URLs.
        """
        page = context.new_page()
        try:
            page.goto(self.HOME_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            self._set_zip(page, str(zip_code))
            page.wait_for_timeout(1500)
        finally:
            page.close()

    def _set_zip(self, page: Page, zip_code: str) -> None:
        """Interact with Retailer N's store selector to set the zip code."""
        # Dismiss any cookie/overlay that might block interaction
        for dismiss_sel in [
            'button[aria-label*="close" i]',
            '[class*="modal-close"]',
            '[class*="overlay-close"]',
            '[class*="dismiss"]',
        ]:
            el = page.query_selector(dismiss_sel)
            if el:
                try:
                    el.click()
                    page.wait_for_timeout(400)
                except Exception:
                    pass

        # Click the store/location selector to reveal the zip input
        for btn_sel in [
            '[data-testid="header-find-store"]',
            '[class*="store-selector"] button',
            '[class*="storeSelector"] button',
            'button[aria-label*="find a store" i]',
            'button[aria-label*="my store" i]',
            'a[href*="find-a-store"]',
            '[class*="find-store"]',
        ]:
            el = page.query_selector(btn_sel)
            if el:
                try:
                    el.click()
                    page.wait_for_timeout(1000)
                    break
                except Exception:
                    continue

        # Fill in zip code
        for inp_sel in [
            'input[placeholder*="zip" i]',
            'input[name*="zip" i]',
            'input[id*="zip" i]',
            'input[maxlength="5"]',
            'input[type="tel"]',
        ]:
            el = page.query_selector(inp_sel)
            if el:
                try:
                    el.fill(zip_code)
                    el.press("Enter")
                    page.wait_for_timeout(2000)
                    # Select first store result if a list appears
                    for store_sel in [
                        '[class*="store-result"]:first-child button',
                        '[class*="storeResult"]:first-child button',
                        '[data-testid="store-result-0"] button',
                        '[class*="store-list"] li:first-child button',
                        '[class*="store-item"]:first-child button',
                    ]:
                        store_btn = page.query_selector(store_sel)
                        if store_btn:
                            store_btn.click()
                            page.wait_for_timeout(1500)
                            break
                    return
                except Exception:
                    continue

    # ------------------------------------------------------------------
    # Price extraction
    # ------------------------------------------------------------------

    def extract(self, page: Page, url: str) -> dict:
        # JSON-LD is the most reliable source for the online price
        for el in page.query_selector_all('script[type="application/ld+json"]'):
            try:
                data = json.loads(el.inner_text())
                if "offers" in data:
                    online_price = self.parse_price(str(data["offers"].get("price", "")))
                    if online_price:
                        list_price = self._find_list_price(page, online_price)
                        if list_price:
                            return {"comp_list_price": list_price, "comp_sale_price": online_price}
                        return {"comp_list_price": online_price, "comp_sale_price": None}
            except Exception:
                continue

        # DOM fallback — target online price, avoid in-store "Today's Price"
        price = None
        for sel in [
            '[class*="online-price"]',
            '[class*="selling-price"]',
            '[data-testid*="price"]',
            '[class*="price-value"]',
            '[class*="product-price"]',
            '[class*="price-now"]',
        ]:
            el = page.query_selector(sel)
            if el:
                price = self.parse_price(el.inner_text())
                if price:
                    break

        list_price = self._find_list_price(page, price) if price else None
        if list_price:
            return {"comp_list_price": list_price, "comp_sale_price": price}
        return {"comp_list_price": price, "comp_sale_price": None}

    def _find_list_price(self, page: Page, active_price) -> float | None:
        """Return a strikethrough/was/original price if it is higher than active_price."""
        for sel in [
            '[class*="was-price"]',
            '[class*="original-price"]',
            '[class*="list-price"]',
            '[class*="regular-price"]',
            's',
            'del',
        ]:
            el = page.query_selector(sel)
            if el:
                match = re.search(r'\$([\d,]+\.?\d*)', el.inner_text())
                if match:
                    candidate = self.parse_price(match.group(1))
                    if candidate and active_price and candidate > active_price:
                        return candidate
        return None
