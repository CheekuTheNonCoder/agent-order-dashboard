"""
report_sync.py

Pushes CS classification / order / ticket / refund reporting data from
PostgreSQL into the "ZOP & AFORA CS REPORTING" Google Sheet, via the
existing Apps Script Web App (reporting_dashboard_apps_script.gs ->
doPost -> action: "update_dashboard").

WHY THIS FILE EXISTS
---------------------
This did not exist anywhere in the repository before (checked full git
history, all 49 commits, all branches -- app.py never called the
reporting webhook for anything except refunds/coupons). Section 40 of
the project brief describes this exact gap: Order Dump upload reaches
Postgres fine, but the Google Sheet never updates, because nothing
was ever wired up to call it.

WHEN THIS RUNS
---------------
Cheeku asked for near-real-time updates, not a nightly batch job, so
this is called directly (in-process, no subprocess) from app.py right
after:
  1. An agent submits a CS classification (normal ticket, "Other"
     ticket, or the auto-classification created from a refund).
  2. An admin uploads a new Order Dump.
  3. An admin uploads a ZOP or AFORA Ticket Dump.

It can also still be run by hand as a script:

    python report_sync.py

Every call site in app.py wraps this in try/except -- a reporting
failure NEVER rolls back or blocks the action that triggered it
(Section 41). Failures are returned as a status dict for the caller to
show as a warning; they are never raised as fatal to the caller unless
the caller wants to escalate.

PERIODS
--------
The Sheet's own dropdowns (built by Code.gs's buildLists_) expect
rolling windows: "Last Day", "Last 7 Days", "Last 30 Days" (Section
24). This is intentionally a different set of periods from the
in-app Reports tab in app.py, which uses calendar buckets ("Current",
"Week", "Month"). Both read the same underlying tables, but the two
period definitions will not produce identical numbers for the same
label -- that is expected, not a bug, because they're answering
slightly different questions ("this calendar week" vs "last 7 rolling
days").

WHAT IS NOT YET VERIFIED
--------------------------
This has been written against the actual columns app.py itself already
depends on (same alias-detection approach, same table names). It has
NOT been run against a live Postgres instance or a live Apps Script
deployment -- no DB credentials or webhook URL were available in this
environment. Treat this as: code implemented, external integration not
independently verified. Please run it once by hand against a
non-production sheet/data if possible before relying on the automatic
triggers.
"""

import os
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from database import get_connection

IST = ZoneInfo("Asia/Kolkata")

REPORT_PERIODS = ["Last Day", "Last 7 Days", "Last 30 Days"]
REPORT_MARKETPLACES = ["All", "ZOP", "AFORA"]

# Same subcategory lists as app.py (Section 26/27) -- kept in sync manually
# for now. If you ever edit the subcategory lists in app.py, mirror the
# change here too, since this is the payload that actually reaches the
# Sheet's SUMMARY tab.
CS_PRE_SUBCATEGORIES = [
    "Refund Cancellation",
    "Order Status Query",
    "Order Cancellation Request",
    "Order Modification Request",
    "RTO Refund",
    "NDR",
    "Order Confirmation Issue",
    "Delay in Delivery",
    "Need Details",
    "DNR",
    "Delay in Shipping",
]
CS_POST_SUBCATEGORIES = [
    "Defective Product",
    "Low Quality Product",
    "Damaged Product",
    "Need Details",
    "Refund Post Delivery",
    "Wrong Product Delivered",
    "Missing Items",
    "Quantity Mismatch",
    "Colour Issue",
]

# Section 29 gives this threshold explicitly for BRAND. Section 30 doesn't
# repeat a number for PRODUCT, so the same threshold is reused here as the
# most defensible assumption -- flag this if a different number is wanted.
MIN_BRAND_ORDER_VOLUME = 200
MIN_PRODUCT_ORDER_VOLUME = 0
TOP_N = 10


# =========================================================
# SECRETS (works both inside a running Streamlit app and as
# a standalone `python report_sync.py` run)
# =========================================================


def _get_secret(name, default=None):
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    env_names = [name.upper()]
    if name == "report_sheet_webhook_url":
        env_names.extend(["REPORT_SHEET_WEBHOOK_URL", "REPORTING_WEBHOOK_URL"])

    for env_name in env_names:
        value = os.environ.get(env_name)
        if value:
            return value

    return default


# =========================================================
# SMALL DB HELPERS (same pattern app.py already uses)
# =========================================================


def _fetch_df(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)


def _table_columns(table_name):
    df = _fetch_df(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table_name,),
    )
    return df["column_name"].tolist() if not df.empty else []


def _pick_col(columns, candidates):
    lookup = {str(c).lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lookup:
            return lookup[cand.lower()]
    return None


def _ident(name):
    if not name or not str(name).replace("_", "").isalnum():
        raise ValueError(f"Invalid column name: {name!r}")
    return '"' + str(name).replace('"', '""') + '"'


def _marketplace_case(order_col):
    return (
        f"CASE WHEN {_ident(order_col)} ILIKE 'ZOP#%%' THEN 'ZOP' "
        f"WHEN {_ident(order_col)} ILIKE 'AFORA#%%' THEN 'AFORA' ELSE 'OTHER' END"
    )


def _period_start(period):
    now = datetime.now(IST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "Last Day":
        return today_start
    if period == "Last 7 Days":
        return today_start - timedelta(days=6)
    return today_start - timedelta(days=29)  # Last 30 Days


def _canonical_subcategory(value):
    """Section 27: fold whitespace/case/invisible-character variants of
    the same subcategory into one canonical string, e.g. 'Defective
    Product', 'defective product', 'Defective Product  ' all collapse
    to 'Defective Product'."""
    if value is None:
        return ""
    text = "".join(ch for ch in str(value) if ch.isprintable() or ch == " ")
    text = " ".join(text.split())
    return text.strip().title()


def _canonical_delivery(value):
    text = " ".join(str(value or "").split()).strip().upper()
    if text in {"PRE", "PRE DELIVERY"}:
        return "Pre Delivery"
    if text in {"POST", "POST DELIVERY"}:
        return "Post Delivery"
    return text


# =========================================================
# ORDERS
# =========================================================


def _orders_df(period, marketplace):
    cols = _table_columns("orders")
    if not cols:
        return pd.DataFrame()
    order_col = _pick_col(cols, ["zop_order_id"])
    marketplace_col = _pick_col(cols, ["zop_id"])
    created_col = _pick_col(cols, ["order_created_at"])
    status_col = _pick_col(cols, ["order_status"])
    brand_col = _pick_col(cols, ["company_name"])
    title_col = _pick_col(cols, ["title"])
    product_col = _pick_col(cols, ["product_id"])
    if not order_col:
        return pd.DataFrame()

    select = [f"{_ident(order_col)} AS order_id"]
    for col, alias in [
        (created_col, "order_created_at"),
        (status_col, "order_status"),
        (brand_col, "brand"),
        (title_col, "product"),
        (product_col, "product_id"),
    ]:
        select.append(f"{_ident(col)} AS {alias}" if col else f"NULL AS {alias}")

    sql = f"SELECT {', '.join(select)} FROM orders WHERE 1=1"
    params = []
    if created_col:
        sql += f" AND {_ident(created_col)} >= %s"
        params.append(_period_start(period))
    if marketplace != "All":
        filter_col = marketplace_col or order_col
        sql += f" AND {_marketplace_case(filter_col)} = %s"
        params.append(marketplace)
    return _fetch_df(sql, tuple(params))


# =========================================================
# CS CLASSIFICATIONS (joined to orders, same as app.py's own
# _cs_report_data -- kept structurally identical on purpose)
# =========================================================


def _cs_df(period, marketplace):
    cs_cols = _table_columns("cs_classifications")
    order_cols = _table_columns("orders")
    if not cs_cols or not order_cols:
        return pd.DataFrame()

    c_order = _pick_col(cs_cols, ["order_id"])
    c_product = _pick_col(cs_cols, ["product_id"])
    c_delivery = _pick_col(cs_cols, ["delivery_type"])
    c_subcat = _pick_col(cs_cols, ["subcategory"])
    c_date = _pick_col(cs_cols, ["classified_at"])
    o_order = _pick_col(order_cols, ["zop_id"])
    o_product = _pick_col(order_cols, ["product_id"])
    o_brand = _pick_col(order_cols, ["company_name"])
    o_title = _pick_col(order_cols, ["title"])
    if not all([c_order, c_product, c_delivery, c_subcat, c_date, o_order, o_product]):
        return pd.DataFrame()

    select = [
        f"c.{_ident(c_order)} AS order_id",
        f"c.{_ident(c_product)} AS product_id",
        f"c.{_ident(c_delivery)} AS delivery_type",
        f"c.{_ident(c_subcat)} AS subcategory",
        f"c.{_ident(c_date)} AS classified_at",
    ]
    select.append(f"o.{_ident(o_brand)} AS brand" if o_brand else "NULL AS brand")
    select.append(f"o.{_ident(o_title)} AS product" if o_title else "NULL AS product")

    sql = (
        f"SELECT {', '.join(select)} FROM cs_classifications c "
        f"LEFT JOIN orders o ON CAST(c.{_ident(c_order)} AS TEXT)=CAST(o.{_ident(o_order)} AS TEXT) "
        f"AND CAST(c.{_ident(c_product)} AS TEXT)=CAST(o.{_ident(o_product)} AS TEXT) "
        f"WHERE c.{_ident(c_date)} >= %s"
    )
    params = [_period_start(period)]
    if marketplace != "All":
        o_order_expr = f"o.{_ident(o_order)}"
        sql += (
            f" AND CASE WHEN {o_order_expr} ILIKE 'ZOP#%%' THEN 'ZOP' "
            f"WHEN {o_order_expr} ILIKE 'AFORA#%%' THEN 'AFORA' ELSE 'OTHER' END = %s"
        )
        params.append(marketplace)

    df = _fetch_df(sql, tuple(params))
    if not df.empty:
        df["delivery_type"] = df["delivery_type"].map(_canonical_delivery)
        df["subcategory"] = df["subcategory"].map(_canonical_subcategory)
        # Section 12 dedup key: same issue reported across multiple ticket
        # interactions counts once.
        df = df.drop_duplicates(
            subset=["order_id", "product_id", "delivery_type", "subcategory"],
            keep="first",
        )
    return df


# =========================================================
# TICKET DATA (same alias map app.py's _ticket_report_data uses)
# =========================================================


def _ticket_df(period, marketplace):
    cols = _table_columns("ticket_data")
    if not cols:
        return pd.DataFrame()
    aliases = {
        "ticket_id": ["ticket_id", "ticketid"],
        "created_at": ["created_at", "ticket_created_at", "createdat"],
        "first_assignment_at": [
            "first_assignment_at",
            "first_assigned_at",
            "assigned_at",
        ],
        "first_response_at": [
            "first_response_at",
            "agents_first_response_date",
            "agent_first_response_at",
            "last_response_at",
        ],
        "resolved_at": ["resolved_at", "resolved_date", "resolvedat"],
        "closed_at": ["closed_at", "closed_date", "closedat"],
        "reopened_at": ["reopened_at", "reopened_date", "reopen_date"],
        "first_responding_agent": ["first_responding_agent", "first_response_agent"],
        "reopened_by": ["reopened_by", "reopen_by"],
        "resolved_by": ["resolved_by", "resolver", "resolved_agent"],
        "order_id": ["order_id", "zop_order_id"],
        "marketplace": ["marketplace"],
    }
    picked = {k: _pick_col(cols, v) for k, v in aliases.items()}
    if not picked["ticket_id"]:
        return pd.DataFrame()

    select = [f"{_ident(picked['ticket_id'])} AS ticket_id"]
    for key in aliases:
        if key == "ticket_id":
            continue
        col = picked[key]
        select.append(f"{_ident(col)} AS {key}" if col else f"NULL AS {key}")

    date_col = picked["created_at"] or picked["first_response_at"]
    sql = f"SELECT {', '.join(select)} FROM ticket_data WHERE 1=1"
    params = []
    if date_col:
        sql += f" AND {_ident(date_col)} >= %s"
        params.append(_period_start(period))
    if marketplace != "All":
        if picked["marketplace"]:
            sql += f" AND {_ident(picked['marketplace'])} = %s"
        elif picked["order_id"]:
            sql += f" AND {_marketplace_case(picked['order_id'])} = %s"
        else:
            return pd.DataFrame()
        params.append(marketplace)
    return _fetch_df(sql, tuple(params))


def _business_hours_between(start_value, end_value):
    """Working hours 10:00-19:00 IST. No weekend-skipping -- no weekend
    policy was ever defined (same caveat as app.py)."""
    if (
        start_value is None
        or end_value is None
        or pd.isna(start_value)
        or pd.isna(end_value)
    ):
        return None
    try:
        start = pd.Timestamp(start_value)
        end = pd.Timestamp(end_value)
        start = (
            start.tz_localize(IST) if start.tzinfo is None else start.tz_convert(IST)
        )
        end = end.tz_localize(IST) if end.tzinfo is None else end.tz_convert(IST)
        if end <= start:
            return 0.0
        total_seconds = 0.0
        day = start.normalize()
        last_day = end.normalize()
        while day <= last_day:
            window_start = day + pd.Timedelta(hours=10)
            window_end = day + pd.Timedelta(hours=19)
            overlap_start = max(start, window_start)
            overlap_end = min(end, window_end)
            if overlap_end > overlap_start:
                total_seconds += (overlap_end - overlap_start).total_seconds()
            day += pd.Timedelta(days=1)
        return total_seconds / 3600.0
    except Exception:
        return None


def _agent_rows(ticket_df):
    """Returns a list of dicts, one per agent, matching Section 31's columns."""
    if ticket_df.empty:
        return []

    df = ticket_df.copy()
    for c in ["first_responding_agent", "reopened_by", "resolved_by"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    for c in [
        "first_response_at",
        "first_assignment_at",
        "created_at",
        "resolved_at",
        "closed_at",
        "reopened_at",
    ]:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    df["frt_start"] = df["first_assignment_at"].fillna(df["created_at"])
    df["frt_hours"] = [
        _business_hours_between(a, b)
        for a, b in zip(df["frt_start"], df["first_response_at"])
    ]
    df["resolution_start"] = df["first_assignment_at"].fillna(df["created_at"])
    df["resolution_hours"] = [
        _business_hours_between(a, b)
        for a, b in zip(df["resolution_start"], df["resolved_at"])
    ]
    df["valid_resolved"] = df["resolved_at"].notna() & df["closed_at"].notna()
    df["has_reopen"] = df["reopened_at"].notna() | (df["reopened_by"] != "")

    agents = sorted(
        set(df.loc[df.first_responding_agent != "", "first_responding_agent"])
        | set(df.loc[df.reopened_by != "", "reopened_by"])
    )
    rows = []
    for agent in agents:
        first = df[df.first_responding_agent == agent]
        reopened = df[df.reopened_by == agent]
        work_ids = set(first.ticket_id.astype(str)) | set(
            reopened.ticket_id.astype(str)
        )
        complete = first[
            (first.first_responding_agent == first.resolved_by) & (~first.has_reopen)
        ]
        resolved_work = df[df.ticket_id.astype(str).isin(work_ids)]
        valid_resolved = resolved_work[resolved_work.valid_resolved]
        frt = first["frt_hours"].dropna()
        resolution = valid_resolved["resolution_hours"].dropna()
        rows.append(
            {
                "agent": agent,
                "first_response_tickets": len(first),
                "reopened_tickets": len(reopened),
                "total_work_handled": len(work_ids),
                "complete_tickets": len(complete),
                "avg_frt": round(float(frt.mean()), 2) if not frt.empty else None,
                "resolution_rate": (
                    (len(valid_resolved) / len(work_ids)) if work_ids else 0.0
                ),
                "avg_resolution_time": (
                    round(float(resolution.mean()), 2) if not resolution.empty else None
                ),
            }
        )
    return rows


# =========================================================
# REFUNDS (read-only from the live Google Sheet -- same
# secret app.py's REFUNDS report tab already uses)
# =========================================================


def _refund_rows_raw():
    read_url = _get_secret("refund_report_read_url", "")
    if not read_url:
        return (
            pd.DataFrame(),
            "refund_report_read_url is not configured; skipping refunds.",
        )
    try:
        response = requests.get(read_url, timeout=20)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("rows", payload if isinstance(payload, list) else [])
        df = pd.DataFrame(rows)
        if df.empty:
            return df, None
        df.columns = [str(c).strip() for c in df.columns]
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"Could not read refund sheet: {e}"


def _refund_col(df, options):
    for c in df.columns:
        if c.lower() in options:
            return c
    return None


# =========================================================
# PAYLOAD BUILDERS -- one function per Sheet tab
# =========================================================


def _build_summary_rows():
    header = [
        "period",
        "marketplace",
        "total_orders",
        "delivered_orders",
        "pre_issues",
        "pre_pct",
        "post_issues",
        "post_pct",
        "tag",
        "sub_pre",
        "sub_post",
    ]
    rows = [header]
    all_subcats = list(dict.fromkeys(CS_PRE_SUBCATEGORIES + CS_POST_SUBCATEGORIES))

    for period in REPORT_PERIODS:
        for marketplace in REPORT_MARKETPLACES:
            orders = _orders_df(period, marketplace)
            cs = _cs_df(period, marketplace)

            total_orders = len(orders)
            delivered_orders = (
                int(
                    (
                        orders["order_status"].astype(str).str.strip() == "DELIVERED"
                    ).sum()
                )
                if not orders.empty
                else 0
            )
            pre = (
                cs[cs.delivery_type == "Pre Delivery"]
                if not cs.empty
                else pd.DataFrame()
            )
            post = (
                cs[cs.delivery_type == "Post Delivery"]
                if not cs.empty
                else pd.DataFrame()
            )

            # Every subcategory that shows up in the data but isn't in the
            # known lists still gets counted (never silently dropped) --
            # just appended to the working subcat set for this bucket.
            observed = set(cs["subcategory"].unique()) if not cs.empty else set()
            subcats_here = list(dict.fromkeys(all_subcats + sorted(observed)))

            sub_counts = {}
            for sub in subcats_here:
                sub_pre = int((pre.subcategory == sub).sum()) if not pre.empty else 0
                sub_post = int((post.subcategory == sub).sum()) if not post.empty else 0
                sub_counts[sub] = (sub_pre, sub_post)

            # Section 28: Pre/Post Issues are DEFINED as the sum over
            # subcategories, not computed independently -- this makes the
            # consistency rule true by construction instead of needing a
            # separate check that can silently be skipped.
            pre_issues = sum(v[0] for v in sub_counts.values())
            post_issues = sum(v[1] for v in sub_counts.values())

            pre_pct = (pre_issues / total_orders) if total_orders else "N/A"
            post_pct = (post_issues / delivered_orders) if delivered_orders else "N/A"

            rows.append(
                [
                    period,
                    marketplace,
                    total_orders,
                    delivered_orders,
                    pre_issues,
                    pre_pct,
                    post_issues,
                    post_pct,
                    "TOTAL",
                    0,
                    0,
                ]
            )
            for sub, (sub_pre, sub_post) in sub_counts.items():
                rows.append(
                    [
                        period,
                        marketplace,
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        sub,
                        sub_pre,
                        sub_post,
                    ]
                )
    return rows


def _build_brand_rows():
    header = [
        "period",
        "marketplace",
        "rank",
        "brand",
        "order_volume",
        "pre_issues",
        "post_issues",
        "total_issues",
        "tag",
        "sub_pre",
        "sub_post",
    ]
    rows = [header]

    for period in REPORT_PERIODS:
        for marketplace in REPORT_MARKETPLACES:
            orders = _orders_df(period, marketplace)
            cs = _cs_df(period, marketplace)
            if orders.empty and cs.empty:
                continue

            volume_by_brand = (
                orders.groupby("brand", dropna=False).size()
                if not orders.empty
                else pd.Series(dtype=int)
            )
            pre = (
                cs[cs.delivery_type == "Pre Delivery"]
                if not cs.empty
                else pd.DataFrame()
            )
            post = (
                cs[cs.delivery_type == "Post Delivery"]
                if not cs.empty
                else pd.DataFrame()
            )
            pre_by_brand = (
                pre.groupby("brand", dropna=False).size()
                if not pre.empty
                else pd.Series(dtype=int)
            )
            post_by_brand = (
                post.groupby("brand", dropna=False).size()
                if not post.empty
                else pd.Series(dtype=int)
            )

            all_brands = (
                set(volume_by_brand.index)
                | set(pre_by_brand.index)
                | set(post_by_brand.index)
            )
            all_brands = {b for b in all_brands if b not in (None, "")}

            summary = []
            for brand in all_brands:
                vol = int(volume_by_brand.get(brand, 0))
                pre_n = int(pre_by_brand.get(brand, 0))
                post_n = int(post_by_brand.get(brand, 0))
                summary.append((brand, vol, pre_n, post_n, pre_n + post_n))

            qualifying = [s for s in summary if s[1] > MIN_BRAND_ORDER_VOLUME]
            qualifying.sort(key=lambda s: s[4], reverse=True)
            ranked_names = {s[0]: i + 1 for i, s in enumerate(qualifying[:TOP_N])}

            for brand, vol, pre_n, post_n, total_n in summary:
                rank = ranked_names.get(brand, "")
                rows.append(
                    [
                        period,
                        marketplace,
                        rank,
                        brand,
                        vol,
                        pre_n,
                        post_n,
                        total_n,
                        "TOTAL",
                        0,
                        0,
                    ]
                )
                if not cs.empty:
                    brand_cs = cs[cs.brand == brand]
                    for sub, sub_df in brand_cs.groupby("subcategory"):
                        sub_pre = int((sub_df.delivery_type == "Pre Delivery").sum())
                        sub_post = int((sub_df.delivery_type == "Post Delivery").sum())
                        rows.append(
                            [
                                period,
                                marketplace,
                                "",
                                brand,
                                "",
                                "",
                                "",
                                "",
                                sub,
                                sub_pre,
                                sub_post,
                            ]
                        )
    return rows


def _build_product_rows():
    header = [
        "period",
        "marketplace",
        "rank",
        "product_id",
        "product",
        "brand",
        "order_volume",
        "pre_issues",
        "post_issues",
        "total_issues",
        "tag",
        "sub_pre",
        "sub_post",
    ]
    rows = [header]

    for period in REPORT_PERIODS:
        for marketplace in REPORT_MARKETPLACES:
            orders = _orders_df(period, marketplace)
            cs = _cs_df(period, marketplace)
            if orders.empty and cs.empty:
                continue

            vol_by_product = (
                orders.groupby(["product_id", "product", "brand"], dropna=False).size()
                if not orders.empty
                else pd.Series(dtype=int)
            )
            pre = (
                cs[cs.delivery_type == "Pre Delivery"]
                if not cs.empty
                else pd.DataFrame()
            )
            post = (
                cs[cs.delivery_type == "Post Delivery"]
                if not cs.empty
                else pd.DataFrame()
            )
            pre_by_product = (
                pre.groupby("product_id", dropna=False).size()
                if not pre.empty
                else pd.Series(dtype=int)
            )
            post_by_product = (
                post.groupby("product_id", dropna=False).size()
                if not post.empty
                else pd.Series(dtype=int)
            )

            summary = []
            for (pid, pname, brand), vol in vol_by_product.items():
                pre_n = int(pre_by_product.get(pid, 0))
                post_n = int(post_by_product.get(pid, 0))
                summary.append(
                    (pid, pname, brand, int(vol), pre_n, post_n, pre_n + post_n)
                )

            # Product report is about escalations, not order-volume qualification.
            # Rank products by unique CS issue count and expose only the Top 10.
            qualifying = [s for s in summary if s[6] > 0]
            qualifying.sort(key=lambda s: (-s[6], str(s[1]).lower()))
            ranked_ids = {s[0]: i + 1 for i, s in enumerate(qualifying[:TOP_N])}

            for pid, pname, brand, vol, pre_n, post_n, total_n in summary:
                rank = ranked_ids.get(pid, "")
                rows.append(
                    [
                        period,
                        marketplace,
                        rank,
                        pid,
                        pname,
                        brand,
                        vol,
                        pre_n,
                        post_n,
                        total_n,
                        "TOTAL",
                        0,
                        0,
                    ]
                )
                if not cs.empty:
                    prod_cs = cs[cs.product_id == pid]
                    for sub, sub_df in prod_cs.groupby("subcategory"):
                        sub_pre = int((sub_df.delivery_type == "Pre Delivery").sum())
                        sub_post = int((sub_df.delivery_type == "Post Delivery").sum())
                        rows.append(
                            [
                                period,
                                marketplace,
                                "",
                                pid,
                                pname,
                                brand,
                                "",
                                "",
                                "",
                                "",
                                sub,
                                sub_pre,
                                sub_post,
                            ]
                        )
    return rows


def _build_agent_rows():
    header = [
        "period",
        "marketplace",
        "agent",
        "first_response_tickets",
        "reopened_tickets",
        "total_work_handled",
        "complete_tickets",
        "avg_frt",
        "resolution_rate",
        "avg_resolution_time",
    ]
    rows = [header]
    for period in REPORT_PERIODS:
        for marketplace in REPORT_MARKETPLACES:
            tickets = _ticket_df(period, marketplace)
            for r in _agent_rows(tickets):
                rows.append(
                    [
                        period,
                        marketplace,
                        r["agent"],
                        r["first_response_tickets"],
                        r["reopened_tickets"],
                        r["total_work_handled"],
                        r["complete_tickets"],
                        r["avg_frt"] if r["avg_frt"] is not None else "",
                        r["resolution_rate"],
                        (
                            r["avg_resolution_time"]
                            if r["avg_resolution_time"] is not None
                            else ""
                        ),
                    ]
                )
    return rows


def _build_refund_rows():
    header = [
        "period",
        "marketplace",
        "refund_orders",
        "refund_amount",
        "date",
        "order_id",
        "brand",
        "product",
        "amount",
        "refund_reason",
    ]
    rows = [header]
    refund_df, warning = _refund_rows_raw()
    if refund_df.empty:
        return rows, warning

    date_col = _refund_col(
        refund_df, {"done date", "done_date", "date", "submitted at", "submitted_at"}
    )
    order_col = _refund_col(refund_df, {"order id", "order_id"})
    brand_col = _refund_col(refund_df, {"brand", "company_name"})
    product_col = _refund_col(refund_df, {"product", "product name", "product_name"})
    amount_col = _refund_col(refund_df, {"amount", "refund amount", "refund_amount"})
    reason_col = _refund_col(refund_df, {"refund reason", "refund_reason"})

    if date_col:
        refund_df[date_col] = pd.to_datetime(refund_df[date_col], errors="coerce")
    if amount_col:
        refund_df["_amount_numeric"] = pd.to_numeric(
            refund_df[amount_col], errors="coerce"
        ).fillna(0)
    else:
        refund_df["_amount_numeric"] = 0.0

    if order_col:
        refund_df["_marketplace"] = (
            refund_df[order_col]
            .astype(str)
            .map(
                lambda v: (
                    "ZOP"
                    if v.upper().startswith("ZOP#")
                    else ("AFORA" if v.upper().startswith("AFORA#") else "OTHER")
                )
            )
        )
    else:
        refund_df["_marketplace"] = "OTHER"

    for period in REPORT_PERIODS:
        start = _period_start(period)
        for marketplace in REPORT_MARKETPLACES:
            bucket = refund_df
            if date_col:
                bucket = bucket[bucket[date_col] >= start]
            if marketplace != "All":
                bucket = bucket[bucket["_marketplace"] == marketplace]
            if bucket.empty:
                continue

            refund_orders = bucket[order_col].nunique() if order_col else len(bucket)
            refund_amount = float(bucket["_amount_numeric"].sum())

            for _, r in bucket.iterrows():
                rows.append(
                    [
                        period,
                        marketplace,
                        refund_orders,
                        refund_amount,
                        (
                            r[date_col].isoformat()
                            if date_col and pd.notna(r[date_col])
                            else ""
                        ),
                        r[order_col] if order_col else "",
                        r[brand_col] if brand_col else "",
                        r[product_col] if product_col else "",
                        float(r["_amount_numeric"]),
                        r[reason_col] if reason_col else "",
                    ]
                )
    return rows, warning


# =========================================================
# WEBHOOK SEND
# =========================================================


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is pd.NaT:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (ValueError, TypeError):
            return str(value)
    missing = pd.isna(value)
    if isinstance(missing, bool) and missing:
        return None
    return value


def _send_to_apps_script(sheets_payload):
    webhook_url = _get_secret("report_sheet_webhook_url")
    if not webhook_url:
        return {
            "status": "error",
            "message": (
                "report_sheet_webhook_url is not configured in secrets/.env. "
                "Add the Apps Script Web App URL there to enable reporting sync."
            ),
        }

    try:
        safe_payload = _json_safe(sheets_payload)
        response = requests.post(
            webhook_url,
            json={"action": "update_dashboard", "sheets": safe_payload},
            timeout=10,
            # Section 38/Bug 5: a 302 from an Apps Script Web App is a
            # normal, successful response -- do NOT follow it, and do NOT
            # treat it as a failure.
            allow_redirects=False,
        )
    except requests.exceptions.ReadTimeout:
        return {
            "status": "unknown",
            "message": "Apps Script did not respond in time. The Sheet may still update; do not retry immediately.",
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Reporting webhook connection failed: {e}",
        }

    if response.status_code in (301, 302, 303, 307, 308):
        return {
            "status": "success",
            "message": "Reporting sync accepted (redirect response).",
        }

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return {
            "status": "error",
            "message": f"Reporting webhook returned an error: {e}",
        }

    try:
        body = response.json()
    except ValueError:
        body = {}

    if body.get("success"):
        return {
            "status": "success",
            "message": body.get("message", "Reporting sync completed."),
        }
    return {
        "status": "error",
        "message": body.get("error", "Apps Script reported an unknown failure."),
    }


# =========================================================
# INCREMENTAL CS DELTA
# =========================================================


def _send_cs_delta(events):
    webhook_url = _get_secret("report_sheet_webhook_url")
    if not webhook_url:
        return {"status": "error", "message": "report_sheet_webhook_url is not configured."}
    if not events:
        return {"status": "success", "message": "No unique CS events to report."}
    try:
        response = requests.post(
            webhook_url,
            json={"action": "cs_delta", "events": _json_safe(events)},
            timeout=15,
            allow_redirects=False,
        )
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"CS delta webhook connection failed: {e}"}
    if response.status_code in (301, 302, 303, 307, 308):
        return {"status": "success", "message": "CS delta accepted by Apps Script."}
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"CS delta webhook returned an error: {e}"}
    try:
        body = response.json()
    except ValueError:
        body = {}
    if body.get("success"):
        return {"status": "success", "message": body.get("message", "CS delta applied.")}
    return {"status": "error", "message": body.get("error", "Apps Script rejected CS delta.")}


def push_cs_delta(events):
    """Send only newly-created unique CS issues to the reporting sheet."""
    return _send_cs_delta(events)


# =========================================================
# PUBLIC ENTRY POINT
# =========================================================


def sync_reports():
    """
    Builds the full SUMMARY/BRAND/PRODUCT/AGENT/REFUNDS payload and pushes
    it to the reporting Google Sheet. Returns a status dict; never raises
    for a reporting-side failure (DB errors while *reading* Postgres are
    still allowed to raise, since that's a real bug worth surfacing loudly
    rather than silently sending an empty report).

    Call this after any of: a CS classification is saved, an Order Dump
    is uploaded, or a Ticket Dump is uploaded.
    """
    warnings = []

    summary_rows = _build_summary_rows()
    brand_rows = _build_brand_rows()
    product_rows = _build_product_rows()
    agent_rows = _build_agent_rows()
    refund_rows, refund_warning = _build_refund_rows()
    if refund_warning:
        warnings.append(refund_warning)

    result = _send_to_apps_script(
        {
            "SUMMARY": summary_rows,
            "BRAND": brand_rows,
            "PRODUCT": product_rows,
            "AGENT": agent_rows,
            "REFUNDS": refund_rows,
        }
    )
    if warnings:
        result["warnings"] = warnings
    return result


if __name__ == "__main__":
    outcome = sync_reports()
    print(outcome)
