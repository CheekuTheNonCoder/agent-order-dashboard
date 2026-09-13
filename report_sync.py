import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()
IST = ZoneInfo("Asia/Kolkata")
DB_URL = os.getenv("DATABASE_URL")
REPORT_SHEET_WEBHOOK_URL = os.getenv("REPORT_SHEET_WEBHOOK_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not configured")
if not REPORT_SHEET_WEBHOOK_URL:
    raise RuntimeError("REPORT_SHEET_WEBHOOK_URL is not configured")

# A brand/product only qualifies for the "Top 20" ranking if it has at
# least this many orders in the period. Every brand/product still shows
# up in the dropdown and gets a TOTAL row -- this floor only keeps
# low-volume noise out of the ranked Top 20 list, per the handoff's
# ">200 orders" business rule.
MIN_ORDERS_FOR_TOP = 200

PRE = {
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
}
POST = {
    "Defective Product",
    "Low Quality Product",
    "Damaged Product",
    "Need Details",
    "Refund Post Delivery",
    "Wrong Product Delivered",
    "Missing Items",
    "Quantity Mismatch",
    "Colour Issue",
    "Size Issue",
}

PERIODS = ("Last Day", "Last 7 Days", "Last 30 Days")
MARKETS = ("All", "ZOP", "AFORA")


def period_start(period):
    now = datetime.now(IST)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "Last Day":
        return day
    if period == "Last 7 Days":
        return day - timedelta(days=6)
    if period == "Last 30 Days":
        return day - timedelta(days=29)
    raise ValueError(period)


def business_hours(start, end):
    if not start or not end or end <= start:
        return 0.0
    start = start.replace(tzinfo=IST) if start.tzinfo is None else start.astimezone(IST)
    end = end.replace(tzinfo=IST) if end.tzinfo is None else end.astimezone(IST)
    total = 0.0
    day = start.date()
    while day <= end.date():
        ws = datetime.combine(day, time(10), IST)
        we = datetime.combine(day, time(19), IST)
        a, b = max(start, ws), min(end, we)
        if b > a:
            total += (b - a).total_seconds() / 3600
        day += timedelta(days=1)
    return round(total, 4)


def fetch(cur, sql, params=()):
    cur.execute(sql, params)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def norm(v):
    return str(v or "").strip()


def delivery(v):
    x = norm(v).upper()
    if x in {"PRE", "PRE DELIVERY"}:
        return "Pre Delivery"
    if x in {"POST", "POST DELIVERY"}:
        return "Post Delivery"
    return x


def unique_cs(rows):
    seen = set()
    out = []
    for r in rows:
        key = (
            norm(r.get("order_id")),
            norm(r.get("product_id")),
            delivery(r.get("delivery_type")),
            norm(r.get("subcategory")),
        )
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def build_market_maps(conn):
    with conn.cursor() as cur:
        ticket_map = fetch(
            cur,
            """
            SELECT CAST(account_id AS TEXT) AS account_id,
                   MAX(UPPER(TRIM(marketplace))) AS marketplace
            FROM ticket_data
            WHERE account_id IS NOT NULL
              AND TRIM(CAST(account_id AS TEXT)) <> ''
              AND UPPER(TRIM(marketplace)) IN ('ZOP','AFORA')
            GROUP BY CAST(account_id AS TEXT)
        """,
        )
        order_rows = fetch(
            cur,
            """
            SELECT CAST(zop_order_id AS TEXT) AS order_id,
                   CAST(company_id AS TEXT) AS company_id,
                   company_name
            FROM orders
            WHERE company_id IS NOT NULL OR company_name IS NOT NULL
        """,
        )
    account_map = {
        norm(r["account_id"]): norm(r["marketplace"]).upper() for r in ticket_map
    }
    order_map = {}
    for r in order_rows:
        oid = norm(r.get("order_id"))
        cid = norm(r.get("company_id"))
        cname = norm(r.get("company_name")).upper()
        market = account_map.get(cid)
        if not market:
            if cname in {"ZOP", "AFORA"}:
                market = cname
            elif "AFORA" in cname:
                market = "AFORA"
            elif "ZOP" in cname:
                market = "ZOP"
        if market in {"ZOP", "AFORA"}:
            order_map[oid] = market
    return order_map


def resolve_market(order_id, order_map):
    """
    Data-driven mapping (ticket_data.account_id -> marketplace, joined via
    orders.company_id, with a company_name fallback) is the source of
    truth and is tried FIRST. The 'ZOP#'/'AFORA#' order-id-prefix check is
    a legacy fallback only -- your real sample data (plain numeric Shopify
    IDs like 8103688274070) never has this prefix, so this branch should
    rarely if ever fire. It is kept only for whatever historical data may
    still use that prefix; it must never override an actual data-driven
    match.
    """
    oid = norm(order_id)
    market = order_map.get(oid)
    if market in {"ZOP", "AFORA"}:
        return market
    x = oid.upper()
    if x.startswith("ZOP#"):
        return "ZOP"
    if x.startswith("AFORA#"):
        return "AFORA"
    return "OTHER"


def load_period_data(conn, period, order_market_map):
    start = period_start(period)
    with conn.cursor() as cur:
        orders = fetch(
            cur,
            """
            SELECT CAST(zop_order_id AS TEXT) AS order_id, order_created_at,
                   order_status, company_name AS brand, title AS product,
                   CAST(product_id AS TEXT) AS product_id, CAST(company_id AS TEXT) AS company_id
            FROM orders
            WHERE order_created_at >= %s
        """,
            (start,),
        )
        cs_rows = fetch(
            cur,
            """
            SELECT CAST(c.order_id AS TEXT) AS order_id,
                   CAST(c.product_id AS TEXT) AS product_id,
                   c.delivery_type, c.subcategory, c.classified_at, c.agent_email,
                   o.company_name AS brand, o.title AS product,
                   o.order_created_at, o.order_status, CAST(o.company_id AS TEXT) AS company_id
            FROM cs_classifications c
            LEFT JOIN orders o
              ON CAST(c.order_id AS TEXT) = CAST(o.zop_order_id AS TEXT)
             AND CAST(c.product_id AS TEXT) = CAST(o.product_id AS TEXT)
            WHERE c.classified_at >= %s
        """,
            (start,),
        )
        tickets = fetch(
            cur,
            """
            SELECT ticket_id, created_at, first_assignment_at, first_response_at,
                   resolved_at, closed_at, reopened_at, first_responding_agent,
                   reopened_by, resolved_by, marketplace
            FROM ticket_data
            WHERE COALESCE(created_at, first_response_at, first_assignment_at) >= %s
        """,
            (start,),
        )

    for o in orders:
        o["marketplace"] = resolve_market(o["order_id"], order_market_map)
    for r in cs_rows:
        r["marketplace"] = resolve_market(r["order_id"], order_market_map)

    return orders, unique_cs(cs_rows), tickets


def market_filter(rows, market):
    if market == "All":
        return rows
    return [r for r in rows if r.get("marketplace") == market]


def summary_rows(period_data):
    # NOTE: Pre %/Post % are stored as FRACTIONS (0-1), not already-scaled
    # percentages. The Apps Script side applies a '0.00%' number format,
    # which multiplies by 100 for display -- so the value must be a
    # fraction here, or the sheet shows e.g. 3333.00% instead of 33.33%.
    rows = [
        [
            "Period",
            "Marketplace",
            "Total Orders",
            "Delivered Orders",
            "Pre Issues",
            "Pre %",
            "Post Issues",
            "Post %",
            "Subcategory",
            "Pre Delivery",
            "Post Delivery",
        ]
    ]
    for period in PERIODS:
        orders, cs, _ = period_data[period]
        for market in MARKETS:
            o = market_filter(orders, market)
            c = market_filter(cs, market)
            order_ids = {norm(r["order_id"]) for r in o if norm(r.get("order_id"))}
            delivered = {
                norm(r["order_id"])
                for r in o
                if norm(r.get("order_id"))
                and norm(r.get("order_status")).upper() == "DELIVERED"
            }
            pre = [r for r in c if delivery(r.get("delivery_type")) == "Pre Delivery"]
            post = [r for r in c if delivery(r.get("delivery_type")) == "Post Delivery"]
            pre_pct = round(len(pre) / len(order_ids), 4) if order_ids else "N/A"
            post_pct = round(len(post) / len(delivered), 4) if delivered else "N/A"
            rows.append(
                [
                    period,
                    market,
                    len(order_ids),
                    len(delivered),
                    len(pre),
                    pre_pct,
                    len(post),
                    post_pct,
                    "TOTAL",
                    len(pre),
                    len(post),
                ]
            )
            sub = defaultdict(lambda: [0, 0])
            for r in c:
                s = norm(r.get("subcategory")) or "Unknown"
                d = delivery(r.get("delivery_type"))
                if d == "Pre Delivery":
                    sub[s][0] += 1
                elif d == "Post Delivery":
                    sub[s][1] += 1
            for s in sorted(sub):
                rows.append(
                    [period, market, "", "", "", "", "", "", s, sub[s][0], sub[s][1]]
                )
    return rows


def brand_rows(period_data):
    # Every brand present in ORDERS or CS data gets exactly one TOTAL row
    # per (period, market) -- this is what feeds the full dropdown, not
    # just brands that happen to have an issue. Rank is only assigned to
    # brands that clear MIN_ORDERS_FOR_TOP; everyone else still gets a
    # TOTAL row with a blank rank so they're selectable but not in Top 20.
    rows = [
        [
            "Period",
            "Marketplace",
            "Rank",
            "Brand",
            "Order Volume",
            "Pre Issues",
            "Post Issues",
            "Total Issues",
            "Subcategory",
            "Sub Pre",
            "Sub Post",
        ]
    ]
    for period in PERIODS:
        orders, cs, _ = period_data[period]
        for market in MARKETS:
            o = market_filter(orders, market)
            c = market_filter(cs, market)

            brand_orders = defaultdict(set)
            for r in o:
                b = norm(r.get("brand")) or "Unknown"
                oid = norm(r.get("order_id"))
                if oid:
                    brand_orders[b].add(oid)

            counts = defaultdict(lambda: [0, 0])
            sub_counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
            all_brands = set(brand_orders.keys())
            for r in c:
                b = norm(r.get("brand")) or "Unknown"
                all_brands.add(b)
                d = delivery(r.get("delivery_type"))
                s = norm(r.get("subcategory")) or "Unknown"
                if d == "Pre Delivery":
                    counts[b][0] += 1
                    sub_counts[b][s][0] += 1
                elif d == "Post Delivery":
                    counts[b][1] += 1
                    sub_counts[b][s][1] += 1

            eligible = [
                (b, len(brand_orders.get(b, ())), counts[b][0], counts[b][1])
                for b in all_brands
                if len(brand_orders.get(b, ())) >= MIN_ORDERS_FOR_TOP
            ]
            eligible.sort(key=lambda x: (-(x[2] + x[3]), x[0]))
            ranked = eligible[:20]
            ranked_names = {b for b, *_ in ranked}

            for i, (b, vol, pre, post) in enumerate(ranked, 1):
                rows.append(
                    [
                        period,
                        market,
                        i,
                        b,
                        vol,
                        pre,
                        post,
                        pre + post,
                        "TOTAL",
                        pre,
                        post,
                    ]
                )

            for b in sorted(all_brands):
                if b in ranked_names:
                    continue
                vol = len(brand_orders.get(b, ()))
                pre, post = counts.get(b, [0, 0])
                rows.append(
                    [
                        period,
                        market,
                        "",
                        b,
                        vol,
                        pre,
                        post,
                        pre + post,
                        "TOTAL",
                        pre,
                        post,
                    ]
                )

            for b, subs in sub_counts.items():
                for s, (pre, post) in subs.items():
                    rows.append([period, market, "", b, "", "", "", "", s, pre, post])
    return rows


def product_rows(period_data):
    rows = [
        [
            "Period",
            "Marketplace",
            "Rank",
            "Product ID",
            "Product",
            "Brand",
            "Order Volume",
            "Pre Issues",
            "Post Issues",
            "Total Issues",
            "Subcategory",
            "Sub Pre",
            "Sub Post",
        ]
    ]
    for period in PERIODS:
        orders, cs, _ = period_data[period]
        for market in MARKETS:
            o = market_filter(orders, market)
            c = market_filter(cs, market)

            product_orders = defaultdict(set)
            for r in o:
                pid = norm(r.get("product_id")) or "Unknown"
                p = norm(r.get("product")) or "Unknown"
                b = norm(r.get("brand")) or "Unknown"
                oid = norm(r.get("order_id"))
                key = (pid, p, b)
                if oid:
                    product_orders[key].add(oid)

            counts = defaultdict(lambda: [0, 0])
            sub_counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
            all_products = set(product_orders.keys())
            for r in c:
                pid = norm(r.get("product_id")) or "Unknown"
                p = norm(r.get("product")) or "Unknown"
                b = norm(r.get("brand")) or "Unknown"
                key = (pid, p, b)
                all_products.add(key)
                d = delivery(r.get("delivery_type"))
                s = norm(r.get("subcategory")) or "Unknown"
                if d == "Pre Delivery":
                    counts[key][0] += 1
                    sub_counts[key][s][0] += 1
                elif d == "Post Delivery":
                    counts[key][1] += 1
                    sub_counts[key][s][1] += 1

            eligible = [
                (key, len(product_orders.get(key, ())), counts[key][0], counts[key][1])
                for key in all_products
                if len(product_orders.get(key, ())) >= MIN_ORDERS_FOR_TOP
            ]
            eligible.sort(key=lambda x: (-(x[2] + x[3]), x[0][1]))
            ranked = eligible[:20]
            ranked_keys = {key for key, *_ in ranked}

            for i, (key, vol, pre, post) in enumerate(ranked, 1):
                pid, p, b = key
                rows.append(
                    [
                        period,
                        market,
                        i,
                        pid,
                        p,
                        b,
                        vol,
                        pre,
                        post,
                        pre + post,
                        "TOTAL",
                        pre,
                        post,
                    ]
                )

            for key in sorted(all_products, key=lambda k: k[1]):
                if key in ranked_keys:
                    continue
                pid, p, b = key
                vol = len(product_orders.get(key, ()))
                pre, post = counts.get(key, [0, 0])
                rows.append(
                    [
                        period,
                        market,
                        "",
                        pid,
                        p,
                        b,
                        vol,
                        pre,
                        post,
                        pre + post,
                        "TOTAL",
                        pre,
                        post,
                    ]
                )

            for key, subs in sub_counts.items():
                pid, p, b = key
                for s, (pre, post) in subs.items():
                    rows.append(
                        [period, market, "", pid, p, b, "", "", "", "", s, pre, post]
                    )
    return rows


def agent_metrics(tickets, market):
    ts = [
        t
        for t in tickets
        if market == "All" or norm(t.get("marketplace")).upper() == market
    ]
    agents = {}

    def get(email):
        if not email:
            return None
        email = norm(email)
        return agents.setdefault(
            email,
            {"fr": 0, "re": 0, "tickets": set(), "complete": 0, "frt": [], "res": []},
        )

    for t in ts:
        tid = norm(t.get("ticket_id"))
        first = get(t.get("first_responding_agent"))
        if first:
            first["fr"] += 1
            first["tickets"].add(tid)
            if (
                norm(t.get("resolved_by")) == norm(t.get("first_responding_agent"))
                and not t.get("reopened_at")
                and t.get("resolved_at")
                and t.get("closed_at")
            ):
                first["complete"] += 1
            st = t.get("first_assignment_at") or t.get("created_at")
            if st and t.get("first_response_at"):
                first["frt"].append(business_hours(st, t["first_response_at"]))
            if st and t.get("resolved_at") and t.get("closed_at"):
                first["res"].append(business_hours(st, t["resolved_at"]))
        reopened = get(t.get("reopened_by"))
        if reopened:
            reopened["re"] += 1
            reopened["tickets"].add(tid)
    out = []
    for email, a in agents.items():
        total = len(a["tickets"])
        resolved = sum(
            1
            for t in ts
            if norm(t.get("ticket_id")) in a["tickets"]
            and t.get("resolved_at")
            and t.get("closed_at")
        )
        # Resolution rate is stored as a fraction too, for the same reason
        # as Pre %/Post % above -- consistent with whatever number format
        # the sheet applies to this column.
        out.append(
            [
                email,
                a["fr"],
                a["re"],
                total,
                a["complete"],
                round(sum(a["frt"]) / len(a["frt"]), 2) if a["frt"] else "",
                round(resolved / total, 4) if total else "N/A",
                round(sum(a["res"]) / len(a["res"]), 2) if a["res"] else "",
            ]
        )
    return sorted(out, key=lambda x: (-x[3], x[0]))


def agent_rows(period_data):
    rows = [
        [
            "Period",
            "Marketplace",
            "Agent",
            "First Response Tickets",
            "Reopened Tickets",
            "Total Work Handled",
            "Complete Tickets",
            "Avg FRT (hrs)",
            "Resolution Rate",
            "Avg Resolution Time (hrs)",
        ]
    ]
    for period in PERIODS:
        _, _, tickets = period_data[period]
        for market in MARKETS:
            for r in agent_metrics(tickets, market):
                rows.append([period, market, *r])
    return rows


def refund_rows_from_cs(period_data):
    # PLACEHOLDER ONLY. This does not read the real refund sheet -- it
    # derives rows from CS classifications tagged "Refund Post Delivery",
    # so Amount is always blank and "Refund Orders" really counts CS
    # classifications, not actual refund transactions. Per the handoff
    # (section 21) this tab must read from the existing live refund
    # Google Sheet instead. Left unchanged pending that read endpoint --
    # see the accompanying note for what's needed to finish this.
    rows = [
        [
            "Period",
            "Marketplace",
            "Refund Orders",
            "Refund Amount",
            "Date",
            "Order ID",
            "Brand",
            "Product",
            "Amount",
            "Refund Reason",
        ]
    ]
    for period in PERIODS:
        _, cs, _ = period_data[period]
        for r in cs:
            if norm(r.get("subcategory")).lower() == "refund post delivery":
                rows.append(
                    [
                        period,
                        r.get("marketplace", "OTHER"),
                        1,
                        "",
                        r.get("classified_at"),
                        r.get("order_id"),
                        r.get("brand"),
                        r.get("product"),
                        "",
                        "Refund Post Delivery",
                    ]
                )
    return rows


def clean(rows):
    width = max((len(r) for r in rows), default=1)
    return [list(r) + [""] * (width - len(r)) for r in rows]


def main():
    print("REPORT DASHBOARD SYNC STARTED")
    with psycopg.connect(DB_URL, prepare_threshold=None) as conn:
        order_market_map = build_market_maps(conn)
        period_data = {}
        for p in PERIODS:
            print(f"Building {p}...")
            period_data[p] = load_period_data(conn, p, order_market_map)
    payload = {
        "action": "update_dashboard",
        "sheets": {
            "SUMMARY": clean(summary_rows(period_data)),
            "BRAND": clean(brand_rows(period_data)),
            "PRODUCT": clean(product_rows(period_data)),
            "AGENT": clean(agent_rows(period_data)),
            "REFUNDS": clean(refund_rows_from_cs(period_data)),
        },
        "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
    }
    print("Sending dashboard payload...")

    # IMPORTANT: do not treat an HTTP redirect as success. Apps Script web
    # apps deployed correctly for "Anyone" access return the JSON body
    # directly (normally HTTP 200); a redirect here usually means the
    # deployment/auth is wrong, not that doPost() ran. We follow the
    # redirect (default requests behaviour) and then require an explicit
    # {"success": true} in the JSON body -- nothing else counts as success.
    r = requests.post(REPORT_SHEET_WEBHOOK_URL, json=payload, timeout=60)
    print("HTTP Status:", r.status_code)

    try:
        result = r.json()
    except ValueError:
        result = None

    if result is None or result.get("success") is not True:
        print("Apps Script raw response:", r.text[:1000])
        raise RuntimeError(
            f"Dashboard update was NOT confirmed successful (HTTP {r.status_code}). "
            "Do not assume the Google Sheet updated -- see the raw response above."
        )

    print(f"Apps Script confirmed success (version={result.get('version')}).")
    print("REPORT DASHBOARD SYNC COMPLETED")


if __name__ == "__main__":
    main()
