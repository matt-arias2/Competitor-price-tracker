"""
Comp Scraper Dashboard — run with: streamlit run dashboard.py
Shows combined data from non-zoned retailers and zoned retailers (Retailer M).
"""
import streamlit as st
import pandas as pd
import db

st.set_page_config(
    page_title="Comp Pricing Dashboard",
    page_icon="📊",
    layout="wide",
)


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_combined_history() -> pd.DataFrame:
    """Load from both price_history and price_history_zoned, merged into one df."""
    non_z = pd.DataFrame(db.get_all_history())
    zoned = pd.DataFrame(db.get_all_zoned_history())
    if not non_z.empty:
        non_z["zone"]     = None
        non_z["zip_code"] = None
    frames = [f for f in [non_z, zoned] if not f.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    # Composite key for change detection: url for non-zoned, url||zone for zoned
    df["_row_key"] = df.apply(
        lambda r: f"{r['url']}||{r['zone']}" if pd.notna(r["zone"]) else r["url"],
        axis=1,
    )
    return df


def get_all_dates() -> list[str]:
    nz = db.get_available_dates()
    z  = db.get_available_zoned_dates()
    return sorted(set(nz) | set(z), reverse=True)


# ── Bootstrap ─────────────────────────────────────────────────────────────────

all_dates = get_all_dates()
if not all_dates:
    st.warning("No data yet. Run `python run_scraper.py` to collect pricing data.")
    st.stop()

all_df = load_combined_history()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.title("Filters")
selected_date = st.sidebar.selectbox("Run Date", all_dates)

run_df = all_df[all_df["scraped_date"] == selected_date].copy()
if run_df.empty:
    st.warning(f"No data for {selected_date}")
    st.stop()

retailers_available = sorted(run_df["competitor"].dropna().unique())
selected_retailers  = st.sidebar.multiselect("Retailers", retailers_available, default=retailers_available)

categories_available = sorted(run_df["category"].dropna().unique())
selected_cats = st.sidebar.multiselect("Categories", categories_available, default=categories_available)

# Zone filter — only shown when zoned data is present
zones_available = sorted(run_df["zone"].dropna().unique().astype(int))
if zones_available:
    zone_options    = ["All Zones"] + [f"Zone {z}" for z in zones_available]
    selected_zone_s = st.sidebar.selectbox("Zone (Zoned Retailers)", zone_options)
    selected_zone   = None if selected_zone_s == "All Zones" else int(selected_zone_s.split()[-1])
else:
    selected_zone = None

# Apply filters
mask = (
    run_df["competitor"].isin(selected_retailers) &
    run_df["category"].isin(selected_cats)
)
if selected_zone is not None:
    mask = mask & ((run_df["zone"] == selected_zone) | run_df["zone"].isna())
run_df = run_df[mask].copy()

# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_pct(val):
    if pd.isna(val): return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"

def fmt_dollar(val):
    if pd.isna(val): return "—"
    return f"${val:,.2f}"

def color_pct(val):
    try:
        v = float(str(val).replace("%", "").replace("+", ""))
        return f"color: {'#2ecc71' if v >= 0 else '#e74c3c'}; font-weight: bold"
    except Exception:
        return ""

# Ensure numeric columns
for col in ["comp_active_price", "our_retail", "vs_our_retail_pct",
            "comp_list_price", "comp_sale_price", "markdown_pct"]:
    run_df[col] = pd.to_numeric(run_df[col], errors="coerce")

# ── Change detection (week-over-week) ─────────────────────────────────────────

def compute_changes(current_df: pd.DataFrame, all_data: pd.DataFrame, current_date: str):
    """Return merged df with price_change column, or empty df if no prior date."""
    sorted_d = sorted(all_data["scraped_date"].dropna().unique())
    try:
        idx = list(sorted_d).index(current_date)
    except ValueError:
        return pd.DataFrame()
    if idx == 0:
        return pd.DataFrame()
    prev_date = sorted_d[idx - 1]
    prev_df   = all_data[all_data["scraped_date"] == prev_date].copy()
    for col in ["comp_active_price", "comp_sale_price", "comp_list_price"]:
        prev_df[col]    = pd.to_numeric(prev_df[col],    errors="coerce")
        current_df[col] = pd.to_numeric(current_df[col], errors="coerce")
    merged = current_df.merge(
        prev_df[["_row_key", "comp_active_price", "comp_sale_price"]].rename(columns={
            "comp_active_price": "prev_active",
            "comp_sale_price":   "prev_sale",
        }),
        on="_row_key", how="inner",
    )
    merged["price_change"] = merged["comp_active_price"] - merged["prev_active"]
    merged["change_pct"]   = (merged["price_change"] / merged["prev_active"] * 100).round(1)
    return merged[merged["price_change"].abs() > 0.01].copy(), prev_date

changes_result = compute_changes(run_df.copy(), all_df.copy(), selected_date)
if isinstance(changes_result, tuple):
    changed_df, prev_date = changes_result
else:
    changed_df, prev_date = pd.DataFrame(), None

_n_changes = len(changed_df)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Competitor Pricing Dashboard")
n_zoned = int(run_df["zone"].notna().sum())
caption = f"Run: **{selected_date}**  |  {len(run_df)} URLs  |  {len(selected_retailers)} retailers"
if n_zoned:
    caption += f"  |  {n_zoned} zoned (Retailer M)"
st.caption(caption)

# ── KPI row ───────────────────────────────────────────────────────────────────

ok_df       = run_df[run_df["scrape_status"] == "ok"]
errors_df   = run_df[run_df["scrape_status"] == "error"]
no_price_df = run_df[run_df["scrape_status"] == "no_price"]
below_df    = run_df[run_df["vs_our_retail_pct"] < 0]
above_df    = run_df[run_df["vs_our_retail_pct"] >= 0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("URLs Scraped",     len(run_df))
c2.metric("On Sale",          int(run_df["comp_sale_price"].notna().sum()))
c3.metric("Price Changes",    _n_changes,
          delta=f"{_n_changes} alert(s)" if _n_changes else None, delta_color="inverse")
c4.metric("Below Client Retail", len(below_df),
          delta=f"{len(below_df)} risk" if not below_df.empty else None, delta_color="inverse")
c5.metric("Above Client Retail", len(above_df))
c6.metric("Errors / N/A",     f"{len(errors_df)} / {len(no_price_df)}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Alerts", "Full Results", "vs Client Retail", "Trends", "By Retailer"
])

# ── Tab 1: Alerts ─────────────────────────────────────────────────────────────
with tab1:

    st.subheader("Week-over-Week Price Changes")
    if changed_df.empty:
        if prev_date:
            st.success(f"No price changes detected vs {prev_date}.")
        else:
            st.info("Only one week of data available — no prior week to compare.")
    else:
        st.markdown(f"**Comparing {selected_date} vs {prev_date}** — {_n_changes} change(s) detected")
        disp_ch = changed_df[[
            "competitor", "zone", "category", "comp_family", "our_family",
            "our_retail", "prev_active", "comp_active_price",
            "price_change", "change_pct", "comp_sale_price", "vs_our_retail_pct", "url",
        ]].copy()

        def arrow(v):
            if pd.isna(v): return "—"
            return f"{'▲' if v > 0 else '▼'} {abs(v):,.2f}"

        disp_ch["prev_active"]       = disp_ch["prev_active"].apply(fmt_dollar)
        disp_ch["comp_active_price"] = disp_ch["comp_active_price"].apply(fmt_dollar)
        disp_ch["price_change"]      = disp_ch["price_change"].apply(arrow)
        disp_ch["change_pct"]        = disp_ch["change_pct"].apply(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")
        disp_ch["our_retail"]        = disp_ch["our_retail"].apply(fmt_dollar)
        disp_ch["comp_sale_price"]   = disp_ch["comp_sale_price"].apply(fmt_dollar)
        disp_ch["vs_our_retail_pct"] = disp_ch["vs_our_retail_pct"].apply(fmt_pct)
        disp_ch["zone"]              = disp_ch["zone"].apply(lambda v: f"Zone {int(v)}" if pd.notna(v) else "")
        disp_ch.columns = [
            "Retailer", "Zone", "Category", "Comp Product", "Client Product",
            "Client Retail", "Prev Price", "New Price",
            "$ Change", "% Change", "Sale Price", "vs Client %", "URL",
        ]
        st.dataframe(disp_ch, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("**Insights**")
        for _, row in changed_df.iterrows():
            direction   = "increased" if row["price_change"] > 0 else "decreased"
            arrow_icon  = "▲" if row["price_change"] > 0 else "▼"
            zone_tag    = f" (Zone {int(row['zone'])})" if pd.notna(row["zone"]) else ""
            insight_lines = [
                f"{arrow_icon} **{row['competitor']}{zone_tag} — {row['comp_family']}** "
                f"{direction} from **{fmt_dollar(row['prev_active'])}** "
                f"→ **{fmt_dollar(row['comp_active_price'])}** ({row['change_pct']:+.1f}%)"
            ]
            vs_pct      = row["vs_our_retail_pct"]
            our_r       = row["our_retail"]
            on_sale_now = pd.notna(row["comp_sale_price"])
            if row["price_change"] > 0:
                if on_sale_now:
                    insight_lines.append("  - Still on sale but the promotional price is creeping up — monitor for wind-down.")
                if pd.notna(vs_pct) and vs_pct < 0:
                    insight_lines.append(f"  - Remains **{abs(vs_pct):.1f}% below client retail** ({fmt_dollar(our_r)}). Gap narrowing — less pressure but still a risk.")
                elif pd.notna(vs_pct):
                    insight_lines.append(f"  - Now **{vs_pct:.1f}% above client retail** ({fmt_dollar(our_r)}) — favorable position.")
            else:
                if on_sale_now:
                    insight_lines.append("  - Promotional price dropped further — increased competitive pressure.")
                if pd.notna(vs_pct) and vs_pct < 0:
                    insight_lines.append(f"  - Now **{abs(vs_pct):.1f}% below client retail** ({fmt_dollar(our_r)}) — worsening gap.")
            # Escape "$" so Streamlit doesn't render "$X → $Y" as LaTeX math
            st.markdown("\n".join(insight_lines).replace("$", r"\$"))

    st.divider()
    st.subheader("Competitors Priced Below Client Retail")
    if below_df.empty:
        st.success("No competitors are currently priced below client retail — great position!")
    else:
        disp = below_df[[
            "competitor", "zone", "category", "comp_family", "our_family",
            "our_retail", "comp_active_price", "vs_our_retail_pct", "comp_sale_price", "url",
        ]].copy()
        disp["our_retail"]        = disp["our_retail"].apply(fmt_dollar)
        disp["comp_active_price"] = disp["comp_active_price"].apply(fmt_dollar)
        disp["comp_sale_price"]   = disp["comp_sale_price"].apply(fmt_dollar)
        disp["vs_our_retail_pct"] = disp["vs_our_retail_pct"].apply(fmt_pct)
        disp["zone"]              = disp["zone"].apply(lambda v: f"Zone {int(v)}" if pd.notna(v) else "")
        disp.columns = ["Retailer", "Zone", "Category", "Comp Product", "Client Product",
                        "Client Retail", "Comp Price", "vs Client %", "Sale Price", "URL"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Significant Discounts (Markdown > 20%)")
    big_sale = run_df[run_df["markdown_pct"] > 20].sort_values("markdown_pct", ascending=False)
    if big_sale.empty:
        st.info("No major markdowns detected this week.")
    else:
        disp2 = big_sale[[
            "competitor", "zone", "category", "comp_family",
            "comp_list_price", "comp_sale_price", "markdown_pct", "our_retail", "vs_our_retail_pct",
        ]].copy()
        disp2["comp_list_price"]   = disp2["comp_list_price"].apply(fmt_dollar)
        disp2["comp_sale_price"]   = disp2["comp_sale_price"].apply(fmt_dollar)
        disp2["our_retail"]        = disp2["our_retail"].apply(fmt_dollar)
        disp2["markdown_pct"]      = disp2["markdown_pct"].apply(lambda v: f"{v:.1f}%")
        disp2["vs_our_retail_pct"] = disp2["vs_our_retail_pct"].apply(fmt_pct)
        disp2["zone"]              = disp2["zone"].apply(lambda v: f"Zone {int(v)}" if pd.notna(v) else "")
        disp2.columns = ["Retailer", "Zone", "Category", "Comp Product",
                         "List Price", "Sale Price", "Markdown %", "Client Retail", "vs Client %"]
        st.dataframe(disp2, use_container_width=True, hide_index=True)


# ── Tab 2: Full Results ───────────────────────────────────────────────────────
with tab2:
    st.subheader(f"All Results — {selected_date}")
    disp = run_df[[
        "competitor", "zone", "zip_code", "category", "comp_family", "our_family", "our_retail",
        "comp_list_price", "comp_sale_price", "comp_active_price",
        "markdown_pct", "vs_our_retail_pct", "scrape_status", "url",
    ]].copy()
    for col in ["our_retail", "comp_list_price", "comp_sale_price", "comp_active_price"]:
        disp[col] = disp[col].apply(fmt_dollar)
    disp["markdown_pct"]     = disp["markdown_pct"].apply(fmt_pct)
    disp["vs_our_retail_pct"] = disp["vs_our_retail_pct"].apply(fmt_pct)
    disp["zone"]             = disp["zone"].apply(lambda v: f"Zone {int(v)}" if pd.notna(v) else "")
    disp.columns = [
        "Retailer", "Zone", "Zip", "Category", "Comp Product", "Client Product", "Client Retail",
        "List Price", "Sale Price", "Active Price",
        "Markdown %", "vs Client %", "Status", "URL",
    ]
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ── Tab 3: vs Client Retail ──────────────────────────────────────────────────────
with tab3:
    st.subheader("Competitor Pricing vs Client Retail")
    chart_df = run_df[run_df["vs_our_retail_pct"].notna()].copy()
    chart_df["vs_our_retail_pct"] = pd.to_numeric(chart_df["vs_our_retail_pct"], errors="coerce")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**By Category — Average % vs Client Retail**")
        cat_avg = chart_df.groupby("category")["vs_our_retail_pct"].mean().round(1).reset_index()
        cat_avg.columns = ["Category", "Avg % vs Client"]
        st.bar_chart(cat_avg.set_index("Category"))
    with col_b:
        st.markdown("**By Retailer — Average % vs Client Retail**")
        # For Retailer M, label includes zone
        chart_df["retailer_label"] = chart_df.apply(
            lambda r: f"{r['competitor']} Z{int(r['zone'])}" if pd.notna(r["zone"]) else r["competitor"],
            axis=1,
        )
        ret_avg = chart_df.groupby("retailer_label")["vs_our_retail_pct"].mean().round(1).reset_index()
        ret_avg.columns = ["Retailer", "Avg % vs Client"]
        st.bar_chart(ret_avg.set_index("Retailer"))

    st.markdown("**Detail: Client Product vs All Comps**")
    chart_df["comp_label"] = chart_df.apply(
        lambda r: f"{r['competitor']} Z{int(r['zone'])}" if pd.notna(r["zone"]) else r["competitor"],
        axis=1,
    )
    pivot = run_df.pivot_table(
        index=["our_family", "category"],
        columns="competitor",
        values="vs_our_retail_pct",
        aggfunc="mean",
    ).round(1).rename_axis(index=["Client Product", "Category"], columns="Retailer")
    st.dataframe(pivot.map(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—"), use_container_width=True)


# ── Tab 4: Trends ─────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Price Trends Over Time")
    all_num = load_combined_history()
    for col in ["comp_active_price", "comp_list_price", "comp_sale_price"]:
        all_num[col] = pd.to_numeric(all_num[col], errors="coerce")

    our_families = sorted(all_num["our_family"].dropna().unique())
    sel_family   = st.selectbox("Select Client Product", our_families)

    fam_df = all_num[all_num["our_family"] == sel_family].copy()
    fam_df = fam_df[fam_df["comp_active_price"].notna()]

    if fam_df.empty:
        st.info("No historical data for this family yet.")
    else:
        # Label Retailer M with zone in the trend chart
        fam_df["comp_label"] = fam_df.apply(
            lambda r: f"{r['competitor']} Z{int(r['zone'])}" if pd.notna(r["zone"]) else r["competitor"],
            axis=1,
        )
        pivot = fam_df.pivot_table(
            index="scraped_date", columns="comp_label",
            values="comp_active_price", aggfunc="mean",
        )
        our_price = fam_df["our_retail"].dropna().iloc[0] if not fam_df["our_retail"].dropna().empty else None
        if our_price:
            pivot["CLIENT RETAIL"] = our_price
        st.line_chart(pivot)
        st.caption("'CLIENT RETAIL' is a flat reference line at the client's current retail price.")


# ── Tab 5: By Retailer ────────────────────────────────────────────────────────
with tab5:
    st.subheader("Breakdown by Retailer")

    # Build retailer labels including zone for Retailer M
    run_df["retailer_label"] = run_df.apply(
        lambda r: f"{r['competitor']} (Zone {int(r['zone'])})" if pd.notna(r["zone"]) else r["competitor"],
        axis=1,
    )
    retailer_options = sorted(run_df["retailer_label"].unique())
    sel_label        = st.selectbox("Select Retailer", retailer_options)
    ret_df           = run_df[run_df["retailer_label"] == sel_label].copy()

    cols = ["category", "comp_family", "our_family", "our_retail",
            "comp_list_price", "comp_sale_price", "comp_active_price",
            "markdown_pct", "vs_our_retail_pct"]
    disp = ret_df[cols].copy()
    for col in ["our_retail", "comp_list_price", "comp_sale_price", "comp_active_price"]:
        disp[col] = disp[col].apply(fmt_dollar)
    disp["markdown_pct"]      = disp["markdown_pct"].apply(fmt_pct)
    disp["vs_our_retail_pct"] = disp["vs_our_retail_pct"].apply(fmt_pct)
    disp.columns = ["Category", "Comp Product", "Client Product", "Client Retail",
                    "List", "Sale", "Active", "Markdown %", "vs Client %"]
    st.dataframe(disp, use_container_width=True, hide_index=True)

    summary = ret_df.groupby("category").agg(
        avg_vs_retail=("vs_our_retail_pct", "mean"),
        n_on_sale=("comp_sale_price", lambda x: x.notna().sum()),
        n_below=("vs_our_retail_pct", lambda x: (x < 0).sum()),
    ).round(1).reset_index()
    summary.columns = ["Category", "Avg % vs Client", "# On Sale", "# Below Client Retail"]
    st.dataframe(summary, use_container_width=True, hide_index=True)
