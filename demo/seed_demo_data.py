"""
Seed data/prices.db with 8 weeks of synthetic price history so the dashboard
can be explored without running a live scrape.

All prices are randomly generated around the fictional "client retail" values in
the sample input files. Nothing here reflects real retailer pricing.

Usage: python demo/seed_demo_data.py
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db
from run_scraper import load_non_zoned, load_zoned, build_result

WEEKS = 8
random.seed(42)


def simulate(row: dict, state: dict) -> dict:
    """Random-walk a list price and occasionally put the item on sale."""
    key = (row["url"], row.get("zone"))
    if key not in state:
        state[key] = round(row["our_retail"] * random.uniform(0.85, 1.25), -1) - 0.01
    list_p = state[key]
    if random.random() < 0.08:  # occasional permanent list-price change
        list_p = state[key] = round(list_p * random.choice([0.95, 1.05]), -1) - 0.01
    sale_p = None
    if random.random() < 0.35:  # promo running this week
        sale_p = round(list_p * random.uniform(0.70, 0.90), -1) - 0.01
    return {"comp_list_price": list_p, "comp_sale_price": sale_p}


def main():
    if db.DB_PATH.exists():
        db.DB_PATH.unlink()
    db.init_db()
    db.init_zoned_db()

    nz_rows = load_non_zoned()
    z_rows  = load_zoned()
    state: dict = {}
    prev_nz: dict = {}
    prev_z: dict  = {}

    start = date.today() - timedelta(weeks=WEEKS - 1)
    for w in range(WEEKS):
        run_date = (start + timedelta(weeks=w)).isoformat()

        nz_results = []
        for row in nz_rows:
            res = build_result(row, simulate(row, state), run_date, prev_nz.get(row["url"]))
            prev_nz[row["url"]] = res["comp_active_price"]
            nz_results.append(res)
        db.insert_results([{k: v for k, v in r.items()
                            if k not in ("price_changed", "price_change_delta", "zone", "zip_code")}
                           for r in nz_results])

        z_results = []
        for row in z_rows:
            key = (row["url"], row["zone"], row["zip_code"])
            res = build_result(row, simulate(row, state), run_date, prev_z.get(key))
            prev_z[key] = res["comp_active_price"]
            z_results.append(res)
        db.insert_zoned_results([{k: v for k, v in r.items()
                                  if k not in ("price_changed", "price_change_delta")}
                                 for r in z_results])

    print(f"Seeded {WEEKS} weeks of demo data into {db.DB_PATH}")
    print("Run: streamlit run dashboard.py")


if __name__ == "__main__":
    main()
