import html
from datetime import datetime

import pandas as pd
import streamlit as st

from database import (
    initialize_database,
    replace_orders,
    search_orders,
    get_order_count,
    get_last_upload,
)

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="OrderOS • Dekho Woh Aa Gaya",
    page_icon="◆",
    layout="wide",
)


# =========================================================
# DATABASE
# =========================================================

initialize_database()


# =========================================================
# REQUIRED COLUMNS  (unchanged — do not modify)
# =========================================================

REQUIRED_COLUMNS = [
    "order_created_at",
    "zop_order_id",
    "zop_id",
    "seller_order_id",
    "company_id",
    "company_name",
    "sr_channel_id",
    "order_status",
    "awb",
    "variant_id",
    "product_id",
    "quantity",
    "title",
    "final_price",
]


# =========================================================
# REFUND REASONS  (edit this list to add/update reasons later)
# =========================================================

REFUND_REASON_PLACEHOLDER = "— Select Reason —"

REFUND_REASONS = [
    "Defective Product",
    "Damaged in Transit",
    "Wrong Item Delivered",
    "Size Issue",
    "Order Cancelled by Customer",
    "Duplicate Order",
    "Late Delivery",
    "Other",
]

REFUND_REASON_OPTIONS = [REFUND_REASON_PLACEHOLDER] + REFUND_REASONS


# =========================================================
# SESSION
# =========================================================

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "last_search_results" not in st.session_state:
    st.session_state.last_search_results = None

if "show_refund_confirm" not in st.session_state:
    st.session_state.show_refund_confirm = False


# =========================================================
# GLASSMORPHISM DESIGN SYSTEM
# =========================================================

st.markdown(
    """
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --bg-0: #06070A;
        --bg-1: #0B0D12;
        --bg-2: #12141B;
        --glass: rgba(255, 255, 255, 0.05);
        --glass-strong: rgba(255, 255, 255, 0.09);
        --glass-border: rgba(255, 255, 255, 0.12);
        --line: rgba(255, 255, 255, 0.10);

        --text-1: #F5F5F7;
        --text-2: #A1A1A8;
        --text-3: #75757D;

        --accent: #0A84FF;
        --accent-2: #64D2FF;
        --accent-3: #BF5AF2;
        --accent-soft: rgba(10, 132, 255, 0.18);

        --green: #30D158;
        --green-soft: rgba(48, 209, 88, 0.16);
        --red: #FF453A;
        --red-soft: rgba(255, 69, 58, 0.16);
        --blue: #0A84FF;
        --blue-soft: rgba(10, 132, 255, 0.16);
        --orange: #FF9F0A;
        --orange-soft: rgba(255, 159, 10, 0.16);
        --grey: #9A9AA1;
        --grey-soft: rgba(154, 154, 161, 0.14);

        --radius-lg: 24px;
        --radius-md: 16px;
        --radius-sm: 10px;
        --shadow: 0 20px 50px rgba(0, 0, 0, 0.55), 0 2px 10px rgba(0, 0, 0, 0.35);
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                      'SF Pro Text', 'Segoe UI', 'Apple Color Emoji', 'Segoe UI Emoji',
                      'Segoe UI Symbol', 'Noto Color Emoji', sans-serif !important;
        color: var(--text-1);
    }

    /* ---- background: deep space + drifting aurora blobs ---- */
    .stApp {
        position: relative;
        overflow-x: hidden;
        min-height: 100vh;
        background:
            radial-gradient(1200px 600px at 15% -10%, rgba(10, 132, 255, 0.10), transparent 60%),
            radial-gradient(1000px 600px at 100% 10%, rgba(191, 90, 242, 0.08), transparent 55%),
            linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 55%, var(--bg-0) 100%);
    }
    .stApp::before, .stApp::after {
        content: "";
        position: absolute;
        border-radius: 50%;
        filter: blur(110px);
        pointer-events: none;
        z-index: 0;
        opacity: 0.5;
    }
    .stApp::before {
        width: 620px;
        height: 620px;
        top: -220px;
        left: -160px;
        background: radial-gradient(circle, var(--accent-2), transparent 70%);
        animation: auroraDrift1 20s ease-in-out infinite alternate;
    }
    .stApp::after {
        width: 560px;
        height: 560px;
        bottom: -200px;
        right: -140px;
        background: radial-gradient(circle, var(--accent-3), transparent 70%);
        animation: auroraDrift2 24s ease-in-out infinite alternate;
    }
    @keyframes auroraDrift1 {
        from { transform: translate(0, 0) scale(1); }
        to   { transform: translate(70px, 50px) scale(1.15); }
    }
    @keyframes auroraDrift2 {
        from { transform: translate(0, 0) scale(1); }
        to   { transform: translate(-60px, -40px) scale(1.12); }
    }
    .block-container { position: relative; z-index: 1; }

    /* ---- hide default chrome ---- */
    #MainMenu, footer, header[data-testid="stHeader"] {
        background: transparent;
    }
    header[data-testid="stHeader"] { box-shadow: none; }

    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    /* ---- sidebar ---- */
    section[data-testid="stSidebar"] {
        position: relative;
        z-index: 2;
        background: rgba(10, 11, 15, 0.7);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border-right: 1px solid var(--line);
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* ---- generic text ---- */
    h1, h2, h3 { color: var(--text-1); letter-spacing: -0.02em; }
    p, span, label, div { color: inherit; }

    /* ---- widget labels: small muted caption, consistent everywhere ---- */
    [data-testid="stWidgetLabel"] p {
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: var(--text-3) !important;
        margin-bottom: 0.35rem !important;
    }

    /* ---- inputs ---- */
    div[data-testid="stTextInput"] div[data-baseweb="input"] {
        background: var(--glass-strong) !important;
        border: 1px solid var(--line) !important;
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(14px);
        box-shadow: none !important;
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
    }
    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: var(--accent-2) !important;
        box-shadow: 0 0 0 3px rgba(100, 210, 255, 0.16), 0 0 26px rgba(100, 210, 255, 0.22) !important;
    }
    div[data-testid="stTextInput"] input {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 0.85rem 1.1rem !important;
        font-size: 1.02rem !important;
        color: var(--text-1) !important;
    }
    div[data-testid="stTextInput"] input::placeholder { color: var(--text-3); opacity: 1; }

    /* ---- native checkbox / radio accent (fixes default red dot) ---- */
    input[type="checkbox"], input[type="radio"] {
        accent-color: var(--accent-2) !important;
    }

    /* ---- number input (refund quantity / amount) ---- */
    div[data-testid="stNumberInput"] div[data-baseweb="input"] {
        background: var(--glass-strong) !important;
        border: 1px solid var(--line) !important;
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(14px);
        box-shadow: none !important;
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
    }
    div[data-testid="stNumberInput"] div[data-baseweb="input"]:focus-within {
        border-color: var(--accent-2) !important;
        box-shadow: 0 0 0 3px rgba(100, 210, 255, 0.16) !important;
    }
    div[data-testid="stNumberInput"] input {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: var(--text-1) !important;
    }

    /* ---- selectbox (refund reason dropdown) ---- */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background: var(--glass-strong) !important;
        border: 1px solid var(--line) !important;
        border-radius: var(--radius-md) !important;
        color: var(--text-1) !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
        border-color: var(--accent-2) !important;
    }
    ul[data-baseweb="menu"] {
        background: var(--bg-1) !important;
        border: 1px solid var(--line) !important;
    }
    li[role="option"] {
        color: var(--text-1) !important;
    }
    li[role="option"]:hover, li[aria-selected="true"] {
        background: var(--glass-strong) !important;
    }

    /* ---- checkbox label text ---- */
    div[data-testid="stCheckbox"] label p {
        color: var(--text-1) !important;
        font-weight: 500 !important;
        text-transform: none !important;
        letter-spacing: normal !important;
    }

    /* ---- buttons ---- */
    .stButton > button {
        border-radius: var(--radius-sm) !important;
        border: 1px solid var(--glass-border) !important;
        background: var(--glass-strong) !important;
        color: var(--text-1) !important;
        font-weight: 600 !important;
        padding: 0.65rem 1.3rem !important;
        backdrop-filter: blur(14px);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        box-shadow: var(--shadow);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.24) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-2), var(--accent) 60%, var(--accent-3)) !important;
        border: none !important;
        color: #06070A !important;
        font-weight: 700 !important;
        box-shadow: 0 10px 30px rgba(10, 132, 255, 0.35);
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 14px 40px rgba(100, 210, 255, 0.45);
        transform: translateY(-2px) scale(1.01);
    }

    /* ---- radio (mode switch) ---- */
    div[role="radiogroup"] {
        gap: 0.35rem;
    }
    div[role="radiogroup"] label {
        background: var(--glass);
        border: 1px solid var(--line);
        border-radius: var(--radius-sm);
        padding: 0.45rem 0.7rem;
        transition: background 0.15s ease, transform 0.15s ease;
    }
    div[role="radiogroup"] label:hover {
        background: var(--glass-strong);
        transform: translateY(-1px);
    }

    /* ---- dataframe ---- */
    div[data-testid="stDataFrame"] {
        border-radius: var(--radius-md);
        overflow: hidden;
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
    }

    /* ---- expander ---- */
    details {
        background: var(--glass);
        border: 1px solid var(--line);
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(14px);
    }

    /* ---- dividers less heavy ---- */
    hr { border-color: var(--line) !important; margin: 1.6rem 0 !important; }

    /* =====================================================
       CUSTOM COMPONENTS
    ===================================================== */

    .oos-eyebrow {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--accent-2);
        margin-bottom: 0.5rem;
    }
    .oos-eyebrow .pulse-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--accent-2);
        box-shadow: 0 0 0 0 rgba(100, 210, 255, 0.55);
        animation: pulseDot 2s infinite;
        flex-shrink: 0;
    }
    @keyframes pulseDot {
        0%   { box-shadow: 0 0 0 0 rgba(100, 210, 255, 0.55); }
        70%  { box-shadow: 0 0 0 9px rgba(100, 210, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(100, 210, 255, 0); }
    }

    .oos-hero {
        animation: fadeUp 0.5s ease both;
        margin-bottom: 1.6rem;
    }
    .oos-hero h1 {
        font-size: 2.6rem;
        font-weight: 800;
        margin: 0 0 0.15rem 0;
        letter-spacing: -0.03em;
        background: linear-gradient(120deg, #FFFFFF 0%, #FFFFFF 45%, var(--accent-2) 75%, var(--accent-3) 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
    }
    .oos-hero .oos-sub {
        color: var(--text-2);
        font-size: 1.02rem;
        margin-bottom: 1.1rem;
    }
    .oos-greeting {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text-1);
        margin: 0;
    }
    .oos-greeting-sub {
        color: var(--text-2);
        font-size: 0.94rem;
        margin-top: 0.1rem;
    }

    .glass-card {
        position: relative;
        overflow: hidden;
        background: var(--glass);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow), inset 0 1px 0 rgba(255, 255, 255, 0.06);
        padding: 1.4rem 1.6rem;
        animation: fadeUp 0.45s ease both;
    }
    .glass-card::before, .id-card::before, .stat-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: -160%;
        width: 55%;
        height: 100%;
        background: linear-gradient(115deg, transparent, rgba(255, 255, 255, 0.10), transparent);
        transform: skewX(-18deg);
        transition: left 0.65s ease;
        pointer-events: none;
    }
    .glass-card:hover::before, .id-card:hover::before, .stat-card:hover::before {
        left: 160%;
    }

    .oos-order-found {
        display: flex;
        align-items: baseline;
        gap: 0.7rem;
        margin-bottom: 0.2rem;
    }
    .oos-order-found .tag {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        background: var(--green-soft);
        color: var(--green);
        padding: 0.22rem 0.6rem;
        border-radius: 999px;
    }
    .oos-order-found .id {
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    .id-card {
        position: relative;
        overflow: hidden;
        background: var(--glass);
        border: 1px solid var(--line);
        border-radius: var(--radius-md);
        padding: 0.9rem 1.1rem;
        backdrop-filter: blur(14px);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
        height: 100%;
    }
    .id-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
    .id-card .label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-3);
        margin-bottom: 0.25rem;
    }
    .id-card .value {
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--text-1);
        word-break: break-word;
    }

    .stat-card {
        position: relative;
        overflow: hidden;
        background: var(--glass);
        border: 1px solid var(--line);
        border-radius: var(--radius-md);
        padding: 1rem 1.1rem;
        backdrop-filter: blur(14px);
        text-align: left;
        transition: transform 0.15s ease;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
        height: 100%;
    }
    .stat-card:hover { transform: translateY(-2px); }
    .stat-card .stat-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-3);
        margin-bottom: 0.35rem;
    }
    .stat-card .stat-value {
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .stat-total .stat-value { color: var(--text-1); }
    .stat-delivered .stat-value { color: var(--green); }
    .stat-cancelled .stat-value { color: var(--red); }
    .stat-transit .stat-value { color: var(--blue); }
    .stat-pending .stat-value { color: var(--orange); }

    /* ---- product table ---- */
    .oos-table-wrap {
        background: var(--glass);
        border: 1px solid var(--line);
        border-radius: var(--radius-md);
        backdrop-filter: blur(16px);
        overflow-x: auto;
        box-shadow: var(--shadow);
    }
    table.oos-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.92rem;
    }
    table.oos-table thead th {
        text-align: left;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-3);
        padding: 0.85rem 1rem;
        border-bottom: 1px solid var(--line);
        white-space: nowrap;
    }
    table.oos-table tbody td {
        padding: 0.8rem 1rem;
        border-bottom: 1px solid var(--line);
        color: var(--text-1);
        white-space: nowrap;
    }
    table.oos-table tbody tr:last-child td { border-bottom: none; }
    table.oos-table tbody tr:hover { background: rgba(100, 210, 255, 0.05); }

    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 0.28rem 0.7rem;
        border-radius: 999px;
        white-space: nowrap;
    }
    .badge .dot {
        width: 7px; height: 7px; border-radius: 50%; display: inline-block;
    }
    .badge-green { background: var(--green-soft); color: var(--green); box-shadow: 0 0 14px rgba(48, 209, 88, 0.18); }
    .badge-green .dot { background: var(--green); }
    .badge-red { background: var(--red-soft); color: var(--red); box-shadow: 0 0 14px rgba(255, 69, 58, 0.18); }
    .badge-red .dot { background: var(--red); }
    .badge-blue { background: var(--blue-soft); color: var(--blue); box-shadow: 0 0 14px rgba(10, 132, 255, 0.18); }
    .badge-blue .dot { background: var(--blue); }
    .badge-orange { background: var(--orange-soft); color: var(--orange); box-shadow: 0 0 14px rgba(255, 159, 10, 0.18); }
    .badge-orange .dot { background: var(--orange); }
    .badge-grey { background: var(--grey-soft); color: var(--grey); }
    .badge-grey .dot { background: var(--grey); }

    .oos-section-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--text-1);
        margin: 1.5rem 0 0.7rem 0;
    }

    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HELPERS
# =========================================================


def get_greeting():
    """Time-aware, meme-flavoured greeting. Returns (headline, subtitle)."""
    hour = datetime.now().hour

    if 5 <= hour < 12:
        return (
            "Pratahkal! ☀️",
            "Fresh start. Bilkul ricks nahi lene ka re baba! Let's find what you need.",
        )
    elif 12 <= hour < 17:
        return (
            "Namaskar, dophar ho gayi! 🌤️",
            "Abhi hum zinda hain! What order are we searching for?",
        )
    elif 17 <= hour < 21:
        return (
            "Good evening, mitron. 🌙",
            "Kya chal raha hai? Fogg chal raha hai? Let's make this search easy.",
        )
    else:
        return (
            "Are you still awake? 🦉",
            "Ye Baburao ka style hai! Sleeping schedule is crying in the corner.",
        )


def status_badge(status):
    """Render a status value as a colored, meme-flavoured pill badge (display-only)."""
    raw = "" if status is None else str(status)
    key = raw.strip().lower()

    if key == "delivered":
        css_class = "badge-green"
        label = "Delivered (Mazza Aaya!)"
    elif key == "cancelled":
        css_class = "badge-red"
        label = "Cancelled (Dukh. Dard. Peeda.)"
    elif key == "in transit":
        css_class = "badge-blue"
        label = "In Transit (Safar Jaari Hai)"
    elif key == "pending":
        css_class = "badge-orange"
        label = "Pending (Thoda Thahar Jao...)"
    else:
        css_class = "badge-grey"
        label = raw.title() if raw.strip() else "Unknown Status"

    label = html.escape(label)

    return f'<span class="badge {css_class}"><span class="dot"></span>{label}</span>'


def format_amount(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return html.escape(str(value)) if value is not None else "—"


def esc(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return html.escape(str(value))


def render_product_table(df):
    """Render the product/company table as a premium HTML table with status badges."""

    rows_html = []

    for _, row in df.iterrows():
        rows_html.append(
            "<tr>"
            f"<td>{esc(row.get('company_name'))}</td>"
            f"<td>{esc(row.get('title'))}</td>"
            f"<td>{esc(row.get('variant_id'))}</td>"
            f"<td>{esc(row.get('quantity'))}</td>"
            f"<td>{status_badge(row.get('order_status'))}</td>"
            f"<td>{esc(row.get('awb'))}</td>"
            f"<td>{esc(row.get('sr_channel_id'))}</td>"
            f"<td>{format_amount(row.get('final_price'))}</td>"
            "</tr>"
        )

    table_html = (
        '<div class="oos-table-wrap"><table class="oos-table">'
        "<thead><tr>"
        "<th>Company</th><th>Product</th><th>Variant</th><th>Qty</th>"
        "<th>Status</th><th>AWB</th><th>Channel ID</th><th>Amount</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table></div>"
    )

    st.markdown(table_html, unsafe_allow_html=True)


def id_card(label, value):
    return (
        '<div class="id-card">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{esc(value)}</div>'
        "</div>"
    )


def stat_card(css_class, label, value):
    return (
        f'<div class="stat-card {css_class}">'
        f'<div class="stat-label">{html.escape(label)}</div>'
        f'<div class="stat-value">{value}</div>'
        "</div>"
    )


def prepare_refund_payload(refund_rows):
    """
    Convert selected refund rows into the clean payload structure that
    the Google Sheet / refund automation will eventually consume.

    Input: list of dicts with keys
        sr_channel_id, zop_order_id, variant_id, quantity, amount, refund_reason
    Output: list of dicts with keys
        channel_id, order_id, variant_id, quantity, amount, refund_reason
    """
    payload = []

    for row in refund_rows:
        payload.append(
            {
                "channel_id": row.get("sr_channel_id"),
                "order_id": row.get("zop_order_id"),
                "variant_id": row.get("variant_id"),
                "quantity": row.get("quantity"),
                "amount": row.get("amount"),
                "refund_reason": row.get("refund_reason"),
            }
        )

    return payload


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown(
        """
        <div style="margin-bottom: 1.6rem;">
            <div style="font-size:1.3rem; font-weight:800; letter-spacing:-0.02em;">
                ◆ OrderOS
            </div>
            <div style="font-size:0.8rem; color:var(--text-2); margin-top:0.15rem;">
                Order intelligence, made simple. (Thoda tameez se, thoda masti se.)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "Select Mode",
        ["Agent", "Admin"],
    )


# =========================================================
# AGENT DASHBOARD
# =========================================================

if mode == "Agent":

    greeting_headline, greeting_sub = get_greeting()

    st.markdown(
        f"""
        <div class="oos-hero">
            <div class="oos-eyebrow"><span class="pulse-dot"></span>OrderOS · Agent Order Intelligence</div>
            <h1>{greeting_headline}</h1>
            <p class="oos-greeting-sub">{greeting_sub}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # UNIVERSAL SEARCH
    # -----------------------------------------------------

    search_value = st.text_input(
        "Universal Search",
        placeholder="ZOP Order ID · ZOP ID · Seller Order ID · AWB... (Arre jaldi waha se hato!)",
    )

    search_button = st.button(
        "🔍 Search (Bhidu, jaldi kar!)",
        type="primary",
        use_container_width=True,
    )

    if search_button:

        if not search_value.strip():

            st.session_state.last_search_results = None

            st.warning(
                "O Bhai, Maro Mujhe Maro! Input empty hai. Please enter an Order ID, ZOP ID, Seller Order ID or AWB."
            )

        else:

            results = search_orders(search_value)

            if results.empty:

                st.session_state.last_search_results = None

                st.error(
                    "Yeh toh dukh khatam nahi hota sabka... No matching order found."
                )

            else:

                # a fresh search means any open refund confirmation
                # from a previous order should not carry over
                st.session_state.last_search_results = results
                st.session_state.show_refund_confirm = False

    # -----------------------------------------------------
    # RESULTS DISPLAY
    # (reads from session_state, not the button click, so that
    # checkboxes / quantity / amount / reason widgets inside the
    # refund workflow below keep the results visible across their
    # own reruns)
    # -----------------------------------------------------

    results = st.session_state.last_search_results

    if results is not None and not results.empty:

        # =================================================
        # ORDER INFORMATION
        # =================================================

        first_row = results.iloc[0]

        order_id = first_row["zop_order_id"]

        zop_id = first_row["zop_id"]

        seller_order_id = first_row["seller_order_id"]

        st.markdown(
            f"""
            <div class="glass-card" style="margin-top:1.4rem;">
                <div class="oos-order-found">
                    <span class="tag">Mil Gaya! 🎯</span>
                    <span class="id">{esc(order_id)}</span>
                </div>
                <div style="margin-top:0.4rem; font-size:0.85rem; font-weight:600; color:var(--accent-2);">
                    PAISA HI PAISA HOGA! 💸
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # =================================================
        # IDENTIFIERS
        # =================================================

        st.markdown(
            '<div class="oos-section-title">📋 Identifiers (Kanoon Ke Haath)</div>',
            unsafe_allow_html=True,
        )

        info1, info2, info3 = st.columns(3)

        info1.markdown(id_card("ZOP Order ID", order_id), unsafe_allow_html=True)
        info2.markdown(id_card("ZOP ID", zop_id), unsafe_allow_html=True)
        info3.markdown(
            id_card("Seller Order ID", seller_order_id), unsafe_allow_html=True
        )

        # =================================================
        # STATUS SUMMARY
        # =================================================

        status_series = (
            results["order_status"].fillna("").astype(str).str.strip().str.lower()
        )

        total_products = len(results)

        delivered = status_series.eq("delivered").sum()

        cancelled = status_series.eq("cancelled").sum()

        in_transit = status_series.eq("in transit").sum()

        pending = status_series.eq("pending").sum()

        st.markdown(
            '<div class="oos-section-title">📊 Status Summary (Bawaal Cheez Hai)</div>',
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.markdown(
            stat_card("stat-total", "Total", total_products), unsafe_allow_html=True
        )
        col2.markdown(
            stat_card("stat-delivered", "Delivered", delivered), unsafe_allow_html=True
        )
        col3.markdown(
            stat_card("stat-cancelled", "Cancelled", cancelled), unsafe_allow_html=True
        )
        col4.markdown(
            stat_card("stat-transit", "In Transit", in_transit), unsafe_allow_html=True
        )
        col5.markdown(
            stat_card("stat-pending", "Pending", pending), unsafe_allow_html=True
        )

        # =================================================
        # PRODUCT LEVEL DETAILS
        # =================================================

        st.markdown(
            '<div class="oos-section-title">🛍️ Product Breakdown (Saman Ki List)</div>',
            unsafe_allow_html=True,
        )

        render_product_table(results)

        # =================================================
        # RAW IDENTIFIERS
        # =================================================

        with st.expander("🔍 View all order identifiers (Pura Chittha)"):

            identifiers = results[
                [
                    "zop_order_id",
                    "zop_id",
                    "seller_order_id",
                    "awb",
                ]
            ].drop_duplicates()

            st.dataframe(
                identifiers,
                use_container_width=True,
                hide_index=True,
            )

        # =================================================
        # V2 — REFUND WORKFLOW
        # =================================================

        st.markdown(
            '<div class="oos-section-title">💸 Refund Zone (Paisa Wapas Karo Ji)</div>',
            unsafe_allow_html=True,
        )

        # Build one entry per product/company row, each with a
        # unique key so multiple rows never collide.
        refund_products = []

        for row_position, row in results.reset_index(drop=True).iterrows():

            refund_products.append(
                {
                    "row_key": f"{order_id}_{row_position}_{row.get('variant_id')}",
                    "title": row.get("title"),
                    "variant_id": row.get("variant_id"),
                    "quantity": row.get("quantity"),
                    "final_price": row.get("final_price"),
                    "sr_channel_id": row.get("sr_channel_id"),
                    "zop_order_id": row.get("zop_order_id"),
                }
            )

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)

        selected_products = []

        for product in refund_products:

            checkbox_key = f"refund_chk_{product['row_key']}"

            product_label = (
                str(product["title"])
                if product["title"] not in (None, "")
                else "Unnamed Product"
            )

            is_checked = st.checkbox(product_label, key=checkbox_key)

            if is_checked:

                selected_products.append(product)

        st.markdown("</div>", unsafe_allow_html=True)

        refund_clicked = st.button(
            "💸 Refund",
            type="primary",
            use_container_width=True,
            disabled=len(selected_products) == 0,
        )

        if refund_clicked:

            st.session_state.show_refund_confirm = True

        # -------------------------------------------------
        # REFUND CONFIRMATION
        # -------------------------------------------------

        if st.session_state.show_refund_confirm and selected_products:

            st.markdown(
                '<div class="oos-section-title">🎯 Refund Confirmation (Computer Ji, Dhyaan Se!)</div>',
                unsafe_allow_html=True,
            )

            refund_rows = []

            any_reason_missing = False

            for product in selected_products:

                qty_key = f"refund_qty_{product['row_key']}"
                amt_key = f"refund_amt_{product['row_key']}"
                reason_key = f"refund_reason_{product['row_key']}"

                default_qty = (
                    int(product["quantity"]) if pd.notna(product["quantity"]) else 1
                )

                try:
                    default_amt = (
                        float(product["final_price"])
                        if pd.notna(product["final_price"])
                        else 0.0
                    )
                except (TypeError, ValueError):
                    default_amt = 0.0

                st.markdown(
                    '<div class="glass-card" style="margin-top:1rem;">',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f'<div style="font-weight:700; font-size:1.05rem; margin-bottom:0.7rem;">{esc(product["title"])}</div>',
                    unsafe_allow_html=True,
                )

                rc1, rc2, rc3 = st.columns(3)

                qty_value = rc1.number_input(
                    "Quantity",
                    min_value=1,
                    value=max(default_qty, 1),
                    step=1,
                    key=qty_key,
                )

                amount_value = rc2.number_input(
                    "Refund Amount (₹)",
                    min_value=0.0,
                    value=default_amt,
                    step=1.0,
                    format="%.2f",
                    key=amt_key,
                )

                reason_value = rc3.selectbox(
                    "Reason",
                    REFUND_REASON_OPTIONS,
                    key=reason_key,
                )

                if reason_value == REFUND_REASON_PLACEHOLDER:
                    any_reason_missing = True

                refund_rows.append(
                    {
                        "sr_channel_id": product["sr_channel_id"],
                        "zop_order_id": product["zop_order_id"],
                        "variant_id": product["variant_id"],
                        "quantity": qty_value,
                        "amount": amount_value,
                        "refund_reason": reason_value,
                    }
                )

                st.markdown("</div>", unsafe_allow_html=True)

            if any_reason_missing:

                st.warning(
                    "Har product ke liye Reason chunna zaroori hai — bina wajah refund lock nahi hoga!"
                )

            submit_clicked = st.button(
                "🔒 Computer Ji, Lock Kar Dijiye!",
                type="primary",
                use_container_width=True,
                disabled=any_reason_missing,
            )

            if submit_clicked and not any_reason_missing:

                refund_payload = prepare_refund_payload(refund_rows)

                # NOTE: this payload is prepared only, for now.
                # The actual Google Sheet / refund automation
                # connection will be wired up separately.

                st.session_state.show_refund_confirm = False

                st.success(
                    "🎉 Lock Ho Gaya Bhidu! 7 Crore Jeet Gaye — Refund Submitted Successfully!"
                )


# =========================================================
# ADMIN DASHBOARD
# =========================================================


else:

    st.markdown(
        """
        <div class="oos-hero">
            <div class="oos-eyebrow"><span class="pulse-dot"></span>OrderOS · Baburao Control Console</div>
            <h1>Control Center</h1>
            <p class="oos-greeting-sub">
                Yeh Baburao ka style hai! Upload today's complete order dump smoothly.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =====================================================
    # LOGIN
    # =====================================================

    if not st.session_state.admin_logged_in:

        st.markdown(
            '<div class="glass-card" style="max-width:420px;">', unsafe_allow_html=True
        )

        st.markdown(
            """
            <div style="text-align:center; margin-bottom: 0.6rem;">
                <div style="font-size:2.2rem; margin-bottom:0.3rem;">🛡️</div>
                <div class="oos-section-title" style="margin-top:0;">Baburao's Lock Screen</div>
                <div style="font-size:0.85rem; color:var(--text-2); margin-bottom:0.8rem;">
                    Enter verification credentials before we unleash the databases.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        password = st.text_input(
            "Admin Password",
            type="password",
            placeholder="Secret key de re baba!",
        )

        login_button = st.button(
            "Verify & Grant Access (Sabaash Beta!)",
            type="primary",
        )

        if login_button:

            # TEMPORARY PASSWORD
            # Will move to Streamlit Secrets later.

            if password == "admin123":

                st.session_state.admin_logged_in = True

                st.rerun()

            else:

                st.error("Bilkul Chup! Incorrect password. Gunda banega re tu?")

        st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================
    # ADMIN PANEL
    # =====================================================

    else:

        top1, top2 = st.columns([5, 1])

        with top1:

            st.success("🛡️ Session Authenticated. Full power access activated.")

        with top2:

            if st.button(
                "Logout Console",
                use_container_width=True,
            ):

                st.session_state.admin_logged_in = False

                st.rerun()

        # =================================================
        # DATABASE STATUS
        # =================================================

        st.markdown(
            '<div class="oos-section-title">📊 Database Statistics (Pura Ka Pura)</div>',
            unsafe_allow_html=True,
        )

        record_count = get_order_count()

        last_upload = get_last_upload()

        c1, c2, c3 = st.columns(3)

        c1.markdown(
            stat_card("stat-total", "Current Records", f"{record_count:,}"),
            unsafe_allow_html=True,
        )

        if last_upload:

            uploaded_at = last_upload[0]
            file_name = last_upload[1]
            upload_records = last_upload[2]

            c2.markdown(
                stat_card(
                    "stat-delivered", "Last Upload Records", f"{upload_records:,}"
                ),
                unsafe_allow_html=True,
            )

            c3.markdown(
                id_card("Last Upload", f"{uploaded_at} · {file_name}"),
                unsafe_allow_html=True,
            )

        else:

            c2.markdown(
                stat_card("stat-delivered", "Last Upload Records", "0"),
                unsafe_allow_html=True,
            )

            c3.markdown(id_card("Last Upload", "No upload yet"), unsafe_allow_html=True)

        # =================================================
        # DAILY FULL DUMP UPLOAD
        # =================================================

        st.markdown(
            '<div class="oos-section-title">📤 Upload Today\'s Full Order Dump</div>',
            unsafe_allow_html=True,
        )

        st.info(
            "This upload replaces the existing dataset. Sambhalke, badme mat bolna data ud gaya!"
        )

        uploaded_file = st.file_uploader(
            "Choose Excel or CSV file",
            type=[
                "xlsx",
                "xls",
                "csv",
            ],
        )

        if uploaded_file:

            try:

                # -----------------------------------------
                # READ FILE
                # -----------------------------------------

                if uploaded_file.name.lower().endswith(".csv"):

                    df = pd.read_csv(uploaded_file)

                else:

                    df = pd.read_excel(uploaded_file)

                # -----------------------------------------
                # CLEAN HEADERS
                # -----------------------------------------

                df.columns = df.columns.astype(str).str.strip()

                # -----------------------------------------
                # NORMALIZE INTEGER COLUMNS
                # (fixes "1.0" being sent to an integer DB column,
                # which happens when a numeric column has a blank/NaN
                # cell and pandas silently upcasts it to float64)
                #
                # NOTE: only "quantity" is touched here. Columns like
                # variant_id / product_id / company_id / sr_channel_id
                # are NOT coerced because they can be alphanumeric
                # (e.g. "V001") — forcing them to numeric would corrupt
                # those values instead of fixing anything.
                # -----------------------------------------

                if "quantity" in df.columns:

                    numeric_qty = pd.to_numeric(df["quantity"], errors="coerce").fillna(
                        0
                    )

                    df["quantity"] = numeric_qty.astype("int64")

                st.write(f"**Rows detected (Total Maal):** {len(df):,}")

                # -----------------------------------------
                # COLUMN VALIDATION
                # -----------------------------------------

                missing_columns = [
                    column for column in REQUIRED_COLUMNS if column not in df.columns
                ]

                if missing_columns:

                    st.error(
                        "❌ Operational Halt! Required columns are missing. Yeh kya jhamela bana diya?"
                    )

                    st.write("Missing columns:")

                    for column in missing_columns:

                        st.write(f"• `{column}`")

                    st.stop()

                # -----------------------------------------
                # VALID FILE
                # -----------------------------------------

                st.success("✅ Bawaal Cheez Hai! File structure is perfectly valid.")

                # -----------------------------------------
                # PREVIEW
                # -----------------------------------------

                st.markdown(
                    '<div class="oos-section-title">Schema Preview (Ek Jhalak)</div>',
                    unsafe_allow_html=True,
                )

                st.dataframe(
                    df.head(10),
                    use_container_width=True,
                    hide_index=True,
                )

                st.warning(
                    "Uploading this file will replace the current database. "
                    "Risk hai toh ishq hai! Confirm karke aage badho."
                )

                # -----------------------------------------
                # CONFIRM UPLOAD
                # -----------------------------------------

                confirm = st.checkbox("I confirm this is today's complete order dump.")

                if confirm:

                    if st.button(
                        "💾 Replace Database (Karde Bhai!)",
                        type="primary",
                        use_container_width=True,
                    ):

                        with st.spinner(
                            "Processing transaction data... Sabra karo bhidu!"
                        ):

                            replace_orders(df, uploaded_file.name)

                        st.success(
                            f"🚀 Uploaded {len(df):,} records successfully! Paisa hi paisa!"
                        )

                        st.rerun()

            except Exception as e:

                st.error("❌ Parser processing failure on file.")

                st.exception(e)

        # =================================================
        # UPLOAD HISTORY
        # =================================================

        st.markdown(
            '<div class="oos-section-title">📋 System Archive Log</div>',
            unsafe_allow_html=True,
        )

        latest_upload = get_last_upload()

        if latest_upload:

            st.markdown(
                f"""
                <div class="glass-card">
                    <div><strong>Date:</strong> {esc(latest_upload[0])}</div>
                    <div style="margin-top:0.3rem;"><strong>File:</strong> {esc(latest_upload[1])}</div>
                    <div style="margin-top:0.3rem;"><strong>Records:</strong> {latest_upload[2]:,}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:

            st.info("No order dump has been uploaded yet. Abhi tak sannata hai bhidu.")
