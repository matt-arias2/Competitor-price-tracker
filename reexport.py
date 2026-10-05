"""
Re-export today's full scrape results to Excel by reading from the database.
Useful when you need to combine partial re-runs with the main run.

Usage: python reexport.py [YYYY-MM-DD]
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import db
from excel_export import export_to_excel
from run_scraper import get_file_retailer_order, get_file_url_order, NON_ZONED_FILE


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()

    # Load file order for sorting
    retailer_order = get_file_retailer_order(NON_ZONED_FILE)
    url_order      = get_file_url_order(NON_ZONED_FILE)

    # Load today's non-zoned rows (DB order doesn't matter; we sort after)
    with db.get_conn() as conn:
        nz_rows = conn.execute(
            "SELECT * FROM price_history WHERE scraped_date = ?",
            (today,)
        ).fetchall()

    # Load previous day's non-zoned prices for change detection
    prev_nz = db.get_last_run_prices(exclude_date=today)

    # Load today's zoned rows
    with db.get_conn() as conn:
        z_rows = conn.execute(
            "SELECT * FROM price_history_zoned WHERE scraped_date = ? ORDER BY zone, competitor",
            (today,)
        ).fetchall()

    # Load previous day's zoned prices for change detection
    prev_z = db.get_last_run_zoned_prices(exclude_date=today)

    all_results = []

    nz_results = []
    for row in nz_rows:
        r = dict(row)
        prev_active = prev_nz.get(r["url"])
        active = r.get("comp_active_price")
        price_changed = (prev_active is not None) and (active is not None) and (round(prev_active, 2) != round(active, 2))
        price_delta = round(active - prev_active, 2) if price_changed else None
        r["price_changed"] = price_changed
        r["price_change_delta"] = price_delta
        r["zone"] = None
        r["zip_code"] = None
        nz_results.append(r)

    # Sort non-zoned rows by individual URL position in the links file
    nz_results.sort(key=lambda r: url_order.get(r["url"].strip(), 99999))
    all_results.extend(nz_results)

    for row in z_rows:
        r = dict(row)
        key = (r["url"], r["zone"], r["zip_code"])
        prev_active = prev_z.get(key)
        active = r.get("comp_active_price")
        price_changed = (prev_active is not None) and (active is not None) and (round(prev_active, 2) != round(active, 2))
        price_delta = round(active - prev_active, 2) if price_changed else None
        r["price_changed"] = price_changed
        r["price_change_delta"] = price_delta
        all_results.append(r)

    if not all_results:
        print(f"No data found for {today}")
        return

    out_path = export_to_excel(all_results, today, retailer_order=retailer_order)

    changed = [r for r in all_results if r.get("price_changed")]
    no_prices = [r for r in all_results if r.get("scrape_status") == "no_price"]

    print(f"Re-exported {len(all_results)} rows for {today}")
    print(f"  Price changes : {len(changed)}")
    print(f"  N/A (no price): {len(no_prices)}")
    print(f"  Output: {out_path}")


if __name__ == "__main__":
    main()
