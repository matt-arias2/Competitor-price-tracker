"""
Retailer M scraper (zoned — prices vary by region/zip).

Price format note: Retailer M renders prices as e.g. <sup>$</sup>899<sup>99</sup>
so inner_text() gives '$89999'. We parse via JavaScript to split dollars
and cents correctly from the DOM structure.

List price: Retailer M does not show a "was" price explicitly. When a sale is active,
a [data-testid="you-save-price"] element shows the savings amount. We compute:
    list_price = active_price + savings
If no savings are shown the item is at regular price and comp_sale_price = None.
"""
from playwright.sync_api import Page, BrowserContext
from .base import BaseScraper

# JavaScript run inside the browser to extract prices from Retailer M's DOM.
_PRICE_JS = """
() => {
    // Parse an element whose structure is: <sup>$</sup>DOLLARS<sup>CENTS</sup>
    // Works for both <span> and <div> containers.
    function parseSplitPriceEl(el) {
        if (!el) return null;
        // Walk direct children: text nodes = dollars, last <sup> with digits = cents
        let dollars = '';
        let centsEl  = null;
        for (const node of el.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                dollars += node.textContent;
            } else if (node.nodeName === 'SUP') {
                const t = node.textContent.replace(/[^0-9]/g, '');
                if (t) centsEl = t;   // keep updating; last numeric sup = cents
            }
        }
        dollars = dollars.replace(/[^0-9]/g, '');
        if (!dollars) return null;
        const cents = centsEl || '00';
        return parseFloat(dollars + '.' + cents.padStart(2, '0'));
    }

    // 1. Active/sale price from the sticky right-rail bar
    const activeEl = document.querySelector(
        '[data-testid="product-price-right-rail-sticky-desktop"] span'
    );
    const activePrice = parseSplitPriceEl(activeEl);

    // 2. Savings amount from "You Save" element (present only during a sale)
    //    Structure: <span data-testid="you-save-price">...<div>$XX<sup>xx</sup></div></span>
    //    We want the last div/span inside it that has a numeric amount.
    let savePrice = null;
    const saveEl = document.querySelector('[data-testid="you-save-price"]');
    if (saveEl) {
        // Find all div/span children that contain price digits
        const candidates = saveEl.querySelectorAll('div, span');
        for (const c of candidates) {
            const candidate = parseSplitPriceEl(c);
            if (candidate && candidate > 0) savePrice = candidate;
        }
    }

    // 3. Compute list price
    let listPrice = null;
    if (activePrice && savePrice) {
        listPrice = Math.round((activePrice + savePrice) * 100) / 100;
    }

    return {
        activePrice: activePrice,
        salePrice:   (listPrice !== null) ? activePrice : null,
        listPrice:   listPrice || activePrice,
    };
}
"""


class RetailerMScraper(BaseScraper):
    name = "RETAILER M"
    HOME_URL = "https://www.retailer-m.example"  # set to the retailer's homepage

    # ------------------------------------------------------------------
    # Zone setup
    # ------------------------------------------------------------------

    def setup_context(self, context: BrowserContext, zip_code: str) -> None:
        """
        Navigate to Retailer M's homepage and set the delivery zip so that all
        subsequent pages in this context reflect regional pricing.
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
        """Set the delivery/location zip code on Retailer M's homepage."""
        # Retailer M shows a location modal on first visit with an MUI text input
        zip_input_sels = [
            'input[id*="zip" i]',           # MuiInputBase — confirmed on homepage
            'input[placeholder*="zip" i]',
            'input[name*="zip" i]',
            'input[placeholder*="postal" i]',
        ]

        for inp_sel in zip_input_sels:
            el = page.query_selector(inp_sel)
            if el:
                try:
                    el.fill(zip_code)
                    el.press("Enter")
                    page.wait_for_timeout(2000)
                    # Confirm / submit if a button appears
                    for confirm_sel in [
                        'button[type="submit"]',
                        'button[class*="confirm" i]',
                        'button[class*="apply" i]',
                        'button[class*="update" i]',
                    ]:
                        btn = page.query_selector(confirm_sel)
                        if btn:
                            btn.click()
                            page.wait_for_timeout(1500)
                            break
                    return
                except Exception:
                    continue

        # Fallback: click a location trigger first then retry
        for btn_sel in [
            '[class*="delivery-zip"]',
            '[class*="location-selector"]',
            'button[aria-label*="zip" i]',
            'button[aria-label*="location" i]',
        ]:
            el = page.query_selector(btn_sel)
            if el:
                try:
                    el.click()
                    page.wait_for_timeout(1000)
                    for inp_sel in zip_input_sels:
                        inp = page.query_selector(inp_sel)
                        if inp:
                            inp.fill(zip_code)
                            inp.press("Enter")
                            page.wait_for_timeout(2000)
                            return
                except Exception:
                    continue

    # ------------------------------------------------------------------
    # Price extraction
    # ------------------------------------------------------------------

    def extract(self, page: Page, url: str) -> dict:
        # Wait for the sticky bar to render (it needs JS hydration)
        try:
            page.wait_for_selector(
                '[data-testid="product-price-right-rail-sticky-desktop"]',
                timeout=8000,
            )
        except Exception:
            pass  # proceed anyway; extract() will return None if element is absent

        result = page.evaluate(_PRICE_JS)

        return {
            "comp_list_price":  result.get("listPrice"),
            "comp_sale_price":  result.get("salePrice"),
        }
