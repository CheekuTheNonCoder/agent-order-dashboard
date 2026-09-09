import html
import uuid
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
    "Colour issue",
    "Damaged Product",
    "DNR Order",
    "Defective product",
    "Delay in Delivery",
    "Low quality Product",
    "Missing Item",
    "Order Cancelled by Seller",
    "Order Cancelled by Customer",
    "Quanity Mismatch",
    "RTO",
    "Size Issue",
    "Wrong Product Delivered",
]

REFUND_REASON_OPTIONS = [REFUND_REASON_PLACEHOLDER] + REFUND_REASONS


# =========================================================
# SPECIAL COUPON OPTIONS
# =========================================================

COUPON_TYPE_PLACEHOLDER = "— Select Coupon —"

COUPON_TYPES = [
    "SORRY 1",
    "SORRY 2",
]

COUPON_TYPE_OPTIONS = [COUPON_TYPE_PLACEHOLDER] + COUPON_TYPES


# =========================================================
# SESSION
# =========================================================

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# Agent login/session state.
# st.session_state.agent_email holds the logged-in agent's email for the
# duration of the browser session. It is set on Login and cleared on Logout.
if "agent_email" not in st.session_state:
    st.session_state.agent_email = None

if "last_search_results" not in st.session_state:
    st.session_state.last_search_results = None

if "show_refund_confirm" not in st.session_state:
    st.session_state.show_refund_confirm = False

# Special Coupon panel toggle — independent of the refund flow.
if "show_coupon_form" not in st.session_state:
    st.session_state.show_coupon_form = False

# Cat companion's current pose. None means "no active event" — the cat
# falls back to a time-of-day pose (see get_mascot_state). Business logic
# below updates this as the agent searches, opens refund/coupon, etc.
if "mascot_state" not in st.session_state:
    st.session_state.mascot_state = None


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

    /* ---- background ---- */
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

    /* ---- widget labels ---- */
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

    input[type="checkbox"], input[type="radio"] {
        accent-color: var(--accent-2) !important;
    }

    /* ---- number input ---- */
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

    /* ---- selectbox ---- */
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

    div[data-testid="stCheckbox"] label p {
        color: var(--text-1) !important;
        font-weight: 500 !important;
        font-size: 1rem !important;
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

    /* ---- radio ---- */
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

    div[data-testid="stDataFrame"] {
        border-radius: var(--radius-md);
        overflow: hidden;
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
    }

    details {
        background: var(--glass);
        border: 1px solid var(--line);
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(14px);
    }

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


def get_ist_hour():
    """
    Returns the current hour in India Standard Time (Asia/Kolkata),
    regardless of the server's own timezone (most hosts run UTC).
    """
    return datetime.now(ZoneInfo("Asia/Kolkata")).hour


def get_greeting(hour):
    """Time-aware greeting. Returns (headline, subtitle)."""

    if 5 <= hour < 12:
        return (
            "Good Morning ☀️",
            "Fresh start — let's find what you need.",
        )
    elif 12 <= hour < 17:
        return (
            "Good Afternoon 🌤️",
            "What order are we searching for today?",
        )
    elif 17 <= hour < 21:
        return (
            "Good Evening 🌙",
            "Let's make this search quick and easy.",
        )
    else:
        return (
            "Working Late? 🦉",
            "Burning the midnight oil — let's get this done.",
        )


def get_mascot_state(hour):
    """
    Resolves which pose the cat companion should be in.

    Priority:
      1. An explicit action state stashed in st.session_state.mascot_state
         (set by the search / refund / coupon flows below — e.g. "found",
         "refund_success"). This is what lets the cat react to what the
         agent is actually doing.
      2. Otherwise, fall back to a time-of-day pose so the cat still feels
         alive when nothing else is going on:
           • 5am–12pm  → morning  (sleepy, coffee)
           • 12pm–5pm  → idle     (normal daytime pose)
           • 5pm–9pm   → evening  (stretching)
           • 9pm–5am   → sleeping (curled up asleep)

    Streamlit reruns the whole script on every interaction, so this is
    plain, deterministic Python — no client-side state, nothing that can
    get out of sync with a rerun.
    """
    action_state = st.session_state.get("mascot_state")
    if action_state:
        return action_state

    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "idle"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "sleeping"


# =========================================================
# CAT COMPANION — draggable desktop-pet widget
# =========================================================
#
# The cat's SVG/CSS/animation "look" is unchanged from the original
# design (original character, not based on any existing IP). What
# changed is HOW it lives on the page:
#
#   • It used to be a plain st.markdown() block, CSS-pinned to the
#     bottom-right corner.
#   • It is now rendered through st.components.v1.html(), inside its
#     own normal-sized, self-contained widget lane near the top of the
#     dashboard (NOT stretched to cover the full page — that trick was
#     tried and dropped, since it mimics a clickjacking-style overlay
#     pattern that browser/security software can flag or block). The
#     cat is fully draggable within that lane using ordinary pointer
#     events, no frame or viewport hacks involved.
#
# All dragging, cursor-tracking, petting/click/hold/shake detection,
# and position persistence (sessionStorage) happen entirely inside
# that component's own vanilla JS — nothing here talks back to Python,
# so none of it triggers a Streamlit rerun or gets wiped by one. The
# only thing Python controls is `context_state` (idle/morning/
# searching/found/refund/etc.), which the search/refund/coupon flows
# above already set via st.session_state.mascot_state exactly as
# before.


def render_cat_companion_widget(context_state="idle"):
    """
    Renders the floating, draggable cat companion.

    context_state is one of the existing dashboard-driven poses
    (idle, morning, searching, found, not_found, refund,
    refund_success, coupon, coupon_success, evening, sleeping) — this
    is unchanged Python-side logic. On top of it, the widget layers
    purely client-side interaction states (hover, pet, excited,
    annoyed, dizzy, sick) that temporarily override the pose when the
    user drags, clicks, holds, or shakes the cat.
    """

    safe_state = html.escape(str(context_state or "idle"))

    widget_html = f"""
<div id="oos-cat-root" data-context-state="{safe_state}">
  <div id="oos-cat-wrap">
    <div class="cat-speech" id="oos-cat-speech"></div>
    <svg viewBox="0 0 100 100" width="86" height="86" id="oos-cat-svg">
      <defs>
        <linearGradient id="catGradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#F6DCB8"/>
          <stop offset="100%" stop-color="#E7AE81"/>
        </linearGradient>
        <linearGradient id="catEarInner" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#F2B8C6"/>
          <stop offset="100%" stop-color="#E8869B"/>
        </linearGradient>
      </defs>

      <g id="oos-cat-body" class="cat-body-anim">

        <g id="oos-acc-morning" class="acc">
          <rect x="20" y="90" width="60" height="4" rx="2" fill="#75757D" opacity="0.35"/>
          <rect x="62" y="76" width="12" height="10" rx="2" fill="#F5F5F7" opacity="0.94"/>
          <rect x="62" y="76" width="12" height="3.5" rx="1.5" fill="#BF5AF2"/>
          <path d="M74 79 q 4 1 3 5 q -1 3 -3 3" stroke="#F5F5F7" stroke-width="1.6" fill="none"/>
          <path class="cat-steam cat-steam-1" d="M66 74 Q 68 70 66 66" stroke="#A1A1A8" stroke-width="1.6" fill="none" stroke-linecap="round"/>
          <path class="cat-steam cat-steam-2" d="M71 74 Q 73 70 71 66" stroke="#A1A1A8" stroke-width="1.6" fill="none" stroke-linecap="round"/>
        </g>

        <g id="oos-acc-searching" class="acc">
          <rect x="20" y="90" width="60" height="4" rx="2" fill="#75757D" opacity="0.35"/>
          <rect x="30" y="70" width="40" height="17" rx="2.5" fill="#12141B" stroke="#64D2FF" stroke-width="1.4"/>
          <rect class="cat-screen-glow" x="33" y="73" width="34" height="11" rx="1.5" fill="#0A84FF" opacity="0.7"/>
        </g>

        <g id="oos-acc-sparkles" class="acc">
          <path class="cat-sparkle cat-sparkle-1" d="M18 30 L 20 34 L 24 36 L 20 38 L 18 42 L 16 38 L 12 36 L 16 34 Z" fill="#64D2FF"/>
          <path class="cat-sparkle cat-sparkle-2" d="M82 24 L 83.5 27 L 87 28.5 L 83.5 30 L 82 33 L 80.5 30 L 77 28.5 L 80.5 27 Z" fill="#BF5AF2"/>
          <path class="cat-sparkle cat-sparkle-3" d="M84 52 L 85 54.5 L 87.5 55.5 L 85 56.5 L 84 59 L 83 56.5 L 80.5 55.5 L 83 54.5 Z" fill="#30D158"/>
        </g>

        <g id="oos-acc-hearts" class="acc">
          <path class="cat-heart cat-heart-1" d="M16 34 c0-2.4 3.4-2.4 3.4 0 c0-2.4 3.4-2.4 3.4 0 c0 2.6-3.4 4.4-3.4 4.4 c0 0-3.4-1.8-3.4-4.4 Z" fill="#FF6482"/>
          <path class="cat-heart cat-heart-2" d="M78 26 c0-2 2.8-2 2.8 0 c0-2 2.8-2 2.8 0 c0 2.2-2.8 3.7-2.8 3.7 c0 0-2.8-1.5-2.8-3.7 Z" fill="#FF6482"/>
          <path class="cat-heart cat-heart-3" d="M82 50 c0-1.8 2.5-1.8 2.5 0 c0-1.8 2.5-1.8 2.5 0 c0 2-2.5 3.4-2.5 3.4 c0 0-2.5-1.4-2.5-3.4 Z" fill="#FF6482"/>
        </g>

        <g id="oos-acc-coupon" class="acc">
          <g class="cat-coupon-card">
            <rect x="60" y="72" width="18" height="12" rx="2" fill="#12141B" stroke="#FF9F0A" stroke-width="1.3" stroke-dasharray="2 1.5"/>
            <circle cx="65" cy="78" r="1.6" fill="#FF9F0A"/>
            <rect x="68" y="76" width="7" height="1.6" rx="0.8" fill="#A1A1A8"/>
            <rect x="68" y="79" width="5" height="1.6" rx="0.8" fill="#A1A1A8"/>
          </g>
        </g>

        <g id="oos-acc-evening" class="acc">
          <path class="cat-stretch-l" d="M28 62 Q 15 55 17 42" stroke="url(#catGradient)" stroke-width="5" fill="none" stroke-linecap="round"/>
          <path class="cat-stretch-r" d="M72 62 Q 85 55 83 42" stroke="url(#catGradient)" stroke-width="5" fill="none" stroke-linecap="round"/>
        </g>

        <g id="oos-acc-sleeping" class="acc">
          <ellipse cx="50" cy="93" rx="34" ry="7" fill="#64D2FF" opacity="0.14"/>
          <path d="M20 90 Q 50 100 80 90 L 80 84 Q 50 92 20 84 Z" fill="#12141B" opacity="0.55"/>
          <text class="cat-zzz cat-zzz-1" x="68" y="30" font-size="8" fill="#A1A1A8">z</text>
          <text class="cat-zzz cat-zzz-2" x="74" y="23" font-size="11" fill="#A1A1A8">z</text>
          <text class="cat-zzz cat-zzz-3" x="81" y="14" font-size="14" fill="#A1A1A8">Z</text>
        </g>

        <g id="oos-acc-sick" class="acc">
          <text x="60" y="24" font-size="13">🤢</text>
          <path class="cat-vomit-drip" d="M50 60 q -1 6 0 11" stroke="#8CD867" stroke-width="3" fill="none" stroke-linecap="round"/>
        </g>

        <path id="oos-tail" d="M74 78 Q 92 74 90 56 Q 89 47 80 49" stroke="url(#catGradient)" stroke-width="7" fill="none" stroke-linecap="round"/>
        <ellipse cx="50" cy="76" rx="27" ry="21" fill="url(#catGradient)"/>

        <g id="oos-paws-base">
          <ellipse class="oos-paw-l" cx="40" cy="88" rx="6" ry="4.5" fill="url(#catGradient)"/>
          <ellipse class="oos-paw-r" cx="60" cy="88" rx="6" ry="4.5" fill="url(#catGradient)"/>
        </g>
        <g id="oos-paws-point" class="acc">
          <ellipse cx="72" cy="80" rx="6.5" ry="4.5" fill="url(#catGradient)" transform="rotate(-18 72 80)"/>
          <ellipse cx="40" cy="88" rx="6" ry="4.5" fill="url(#catGradient)"/>
        </g>

        <g id="oos-head-tilt">
          <polygon id="oos-ear-l" points="30,30 24,10 42,24" fill="url(#catGradient)"/>
          <polygon points="30,27 27,15 37,23" fill="url(#catEarInner)"/>
          <polygon id="oos-ear-r" points="70,30 76,10 58,24" fill="url(#catGradient)"/>
          <polygon points="70,27 73,15 63,23" fill="url(#catEarInner)"/>
          <circle cx="50" cy="44" r="24" fill="url(#catGradient)"/>

          <path d="M22 46 L 34 44" stroke="#2B1B12" stroke-width="1" opacity="0.4" stroke-linecap="round"/>
          <path d="M22 51 L 34 49" stroke="#2B1B12" stroke-width="1" opacity="0.4" stroke-linecap="round"/>
          <path d="M78 46 L 66 44" stroke="#2B1B12" stroke-width="1" opacity="0.4" stroke-linecap="round"/>
          <path d="M78 51 L 66 49" stroke="#2B1B12" stroke-width="1" opacity="0.4" stroke-linecap="round"/>

          <g id="oos-eye-l" class="oos-eye">
            <circle class="cat-eye eye-normal" cx="0" cy="0" r="3.4" fill="#2B1B12"/>
            <path class="eye-sleepy" d="M-5 0 Q 0 3 5 0" stroke="#2B1B12" stroke-width="2.2" fill="none" stroke-linecap="round"/>
            <path class="eye-happy" d="M-5 1 Q 0 -5 5 1" stroke="#2B1B12" stroke-width="2.4" fill="none" stroke-linecap="round"/>
            <path class="eye-closed" d="M-5 0 q 5 3 10 0" stroke="#2B1B12" stroke-width="2.2" fill="none" stroke-linecap="round"/>
            <g class="eye-spiral" stroke="#2B1B12" stroke-width="1.3" fill="none">
              <path d="M0 0 m -4 0 a 4 4 0 1 1 8 0 a 2.6 2.6 0 1 1 -5.2 0 a 1.3 1.3 0 1 1 2.6 0"/>
            </g>
            <path class="eye-annoyed" d="M-5 -1 L 5 1" stroke="#2B1B12" stroke-width="2.2" stroke-linecap="round"/>
          </g>
          <g id="oos-eye-r" class="oos-eye">
            <circle class="cat-eye eye-normal" cx="0" cy="0" r="3.4" fill="#2B1B12"/>
            <path class="eye-sleepy" d="M-5 0 Q 0 3 5 0" stroke="#2B1B12" stroke-width="2.2" fill="none" stroke-linecap="round"/>
            <path class="eye-happy" d="M-5 1 Q 0 -5 5 1" stroke="#2B1B12" stroke-width="2.4" fill="none" stroke-linecap="round"/>
            <path class="eye-closed" d="M-5 0 q 5 3 10 0" stroke="#2B1B12" stroke-width="2.2" fill="none" stroke-linecap="round"/>
            <g class="eye-spiral" stroke="#2B1B12" stroke-width="1.3" fill="none">
              <path d="M0 0 m -4 0 a 4 4 0 1 1 8 0 a 2.6 2.6 0 1 1 -5.2 0 a 1.3 1.3 0 1 1 2.6 0"/>
            </g>
            <path class="eye-annoyed" d="M-5 -1 L 5 1" stroke="#2B1B12" stroke-width="2.2" stroke-linecap="round"/>
          </g>

          <path d="M48 49 L 52 49 L 50 51.5 Z" fill="#E8869B"/>

          <g id="oos-mouth">
            <path class="mouth-normal" d="M45 54 Q 50 58 55 54" stroke="#2B1B12" stroke-width="1.8" fill="none" stroke-linecap="round"/>
            <ellipse class="mouth-yawn" cx="50" cy="55" rx="3.2" ry="4" fill="#5C3A2E"/>
            <path class="mouth-happy" d="M42 53 Q 50 61 58 53" stroke="#2B1B12" stroke-width="2" fill="none" stroke-linecap="round"/>
            <path class="mouth-confused" d="M45 56 Q 50 53 55 56" stroke="#2B1B12" stroke-width="1.8" fill="none" stroke-linecap="round"/>
            <ellipse class="mouth-sick" cx="50" cy="56" rx="4" ry="3" fill="#5C3A2E"/>
          </g>
        </g>
      </g>
    </svg>
  </div>
</div>

<style>
  html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; background: transparent; overflow: hidden; }}

  #oos-cat-root {{
    position: relative;
    width: 100%;
    height: 100%;
  }}

  #oos-cat-wrap {{
    position: absolute;
    /* default: right side of its lane, away from the search box */
    left: 70%;
    top: 30%;
    width: 96px;
    height: 108px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    gap: 0.3rem;
    cursor: grab;
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
    z-index: 5;
    will-change: transform, left, top;
  }}
  #oos-cat-wrap.dragging {{ cursor: grabbing; }}
  #oos-cat-wrap::before {{
    content: "";
    position: absolute;
    inset: -12px -8px -6px -8px;
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 22px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.55), 0 2px 10px rgba(0, 0, 0, 0.35);
    z-index: -1;
    pointer-events: none;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }}
  #oos-cat-wrap:hover::before, #oos-cat-wrap.hover::before {{
    transform: scale(1.05);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6), 0 2px 10px rgba(0, 0, 0, 0.4);
  }}

  .cat-speech {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    color: #F5F5F7;
    text-align: center;
    letter-spacing: 0.01em;
    white-space: nowrap;
    background: rgba(255, 255, 255, 0.09);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 999px;
    padding: 0.22rem 0.65rem;
    backdrop-filter: blur(14px);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.55);
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.2s ease, transform 0.2s ease;
    pointer-events: none;
  }}
  .cat-speech.visible {{ opacity: 1; transform: translateY(0); }}

  #oos-cat-svg {{ display: block; }}

  .cat-body-anim {{
    animation: catBreathe 3.6s ease-in-out infinite;
    transform-origin: 50% 85%;
    transition: transform 0.15s ease;
  }}
  #oos-cat-wrap.hover .cat-body-anim,
  #oos-cat-wrap.pet .cat-body-anim,
  #oos-cat-wrap.excited .cat-body-anim {{ animation-duration: 1.4s; }}
  #oos-cat-wrap.dragging .cat-body-anim {{ animation-play-state: paused; }}

  @keyframes catBreathe {{
    0%, 100% {{ transform: translateY(0) scaleY(1); }}
    50% {{ transform: translateY(-2px) scaleY(1.015); }}
  }}

  /* mood layers — everything hidden by default, one shown per mood */
  .acc, .eye-sleepy, .eye-happy, .eye-closed, .eye-spiral, .eye-annoyed,
  .mouth-yawn, .mouth-happy, .mouth-confused, .mouth-sick {{ display: none; }}
  .eye-normal, .mouth-normal {{ display: block; }}

  #oos-eye-l {{ transform: translate(42px, 42px); }}
  #oos-eye-r {{ transform: translate(58px, 42px); }}
  .oos-eye {{ transition: transform 0.12s ease; }}

  /* ---- mood -> visible parts ---- */
  #oos-cat-wrap.mood-morning #oos-acc-morning,
  #oos-cat-wrap.mood-searching #oos-acc-searching,
  #oos-cat-wrap.mood-found #oos-acc-sparkles,
  #oos-cat-wrap.mood-refund_success #oos-acc-sparkles,
  #oos-cat-wrap.mood-coupon_success #oos-acc-sparkles,
  #oos-cat-wrap.mood-excited #oos-acc-sparkles,
  #oos-cat-wrap.mood-pet #oos-acc-hearts,
  #oos-cat-wrap.mood-excited #oos-acc-hearts,
  #oos-cat-wrap.mood-coupon #oos-acc-coupon,
  #oos-cat-wrap.mood-evening #oos-acc-evening,
  #oos-cat-wrap.mood-sleeping #oos-acc-sleeping,
  #oos-cat-wrap.mood-sick #oos-acc-sick,
  #oos-cat-wrap.mood-refund #oos-paws-point {{ display: block; }}

  #oos-cat-wrap.mood-refund #oos-paws-base,
  #oos-cat-wrap.mood-morning #oos-paws-base,
  #oos-cat-wrap.mood-searching #oos-paws-base {{ display: none; }}

  #oos-cat-wrap.mood-morning .eye-normal,
  #oos-cat-wrap.mood-sleeping .eye-normal {{ display: none; }}
  #oos-cat-wrap.mood-morning .eye-sleepy,
  #oos-cat-wrap.mood-sleeping .eye-closed {{ display: block; }}

  #oos-cat-wrap.mood-found .eye-normal,
  #oos-cat-wrap.mood-refund_success .eye-normal,
  #oos-cat-wrap.mood-coupon_success .eye-normal,
  #oos-cat-wrap.mood-pet .eye-normal,
  #oos-cat-wrap.mood-excited .eye-normal {{ display: none; }}
  #oos-cat-wrap.mood-found .eye-happy,
  #oos-cat-wrap.mood-refund_success .eye-happy,
  #oos-cat-wrap.mood-coupon_success .eye-happy,
  #oos-cat-wrap.mood-pet .eye-happy,
  #oos-cat-wrap.mood-excited .eye-happy {{ display: block; }}

  #oos-cat-wrap.mood-not_found .eye-normal,
  #oos-cat-wrap.mood-annoyed .eye-normal {{ display: none; }}
  #oos-cat-wrap.mood-not_found .eye-annoyed,
  #oos-cat-wrap.mood-annoyed .eye-annoyed {{ display: block; }}

  #oos-cat-wrap.mood-dizzy .eye-normal {{ display: none; }}
  #oos-cat-wrap.mood-dizzy .eye-spiral {{ display: block; }}
  #oos-cat-wrap.mood-dizzy .eye-spiral {{ animation: spin 1s linear infinite; transform-origin: center; }}
  @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}

  #oos-cat-wrap.mood-morning .mouth-normal {{ display: none; }}
  #oos-cat-wrap.mood-morning .mouth-yawn {{ display: block; }}
  #oos-cat-wrap.mood-found .mouth-normal,
  #oos-cat-wrap.mood-refund_success .mouth-normal,
  #oos-cat-wrap.mood-coupon_success .mouth-normal,
  #oos-cat-wrap.mood-pet .mouth-normal,
  #oos-cat-wrap.mood-excited .mouth-normal {{ display: none; }}
  #oos-cat-wrap.mood-found .mouth-happy,
  #oos-cat-wrap.mood-refund_success .mouth-happy,
  #oos-cat-wrap.mood-coupon_success .mouth-happy,
  #oos-cat-wrap.mood-pet .mouth-happy,
  #oos-cat-wrap.mood-excited .mouth-happy {{ display: block; }}
  #oos-cat-wrap.mood-not_found .mouth-normal {{ display: none; }}
  #oos-cat-wrap.mood-not_found .mouth-confused {{ display: block; }}
  #oos-cat-wrap.mood-sick .mouth-normal {{ display: none; }}
  #oos-cat-wrap.mood-sick .mouth-sick {{ display: block; }}

  /* ---- ears ---- */
  #oos-ear-l, #oos-ear-r {{ transform-origin: 30px 26px; transition: transform 0.15s ease; }}
  #oos-cat-wrap.hover #oos-ear-l {{ transform: rotate(-8deg); }}
  #oos-cat-wrap.hover #oos-ear-r {{ transform: rotate(8deg); }}
  #oos-cat-wrap.pet #oos-ear-l {{ transform: rotate(-14deg); }}
  #oos-cat-wrap.pet #oos-ear-r {{ transform: rotate(14deg); }}
  #oos-cat-wrap.excited #oos-ear-l {{ animation: earFlap 0.35s ease-in-out infinite; }}
  #oos-cat-wrap.excited #oos-ear-r {{ animation: earFlap 0.35s ease-in-out infinite reverse; }}
  #oos-cat-wrap.annoyed #oos-ear-l {{ transform: rotate(16deg); }}
  #oos-cat-wrap.annoyed #oos-ear-r {{ transform: rotate(-16deg); }}
  @keyframes earFlap {{
    0%, 100% {{ transform: rotate(-6deg); }}
    50% {{ transform: rotate(10deg); }}
  }}

  /* ---- head tilt (cursor tracking + moods) ---- */
  #oos-head-tilt {{ transform-origin: 50px 48px; transition: transform 0.18s ease; }}
  #oos-cat-wrap.mood-not_found #oos-head-tilt,
  #oos-cat-wrap.annoyed #oos-head-tilt {{ animation: headTiltConfused 2.6s ease-in-out infinite; }}
  @keyframes headTiltConfused {{
    0%, 100% {{ transform: rotate(0deg); }}
    30% {{ transform: rotate(-11deg); }}
    60% {{ transform: rotate(-6deg); }}
  }}
  #oos-cat-wrap.mood-coupon #oos-head-tilt,
  #oos-cat-wrap.mood-refund #oos-head-tilt {{ animation: headTiltCurious 3s ease-in-out infinite; }}
  @keyframes headTiltCurious {{
    0%, 100% {{ transform: rotate(0deg); }}
    50% {{ transform: rotate(6deg); }}
  }}

  /* ---- tail ---- */
  #oos-tail {{ transform-origin: 82px 78px; animation: tailSway 2.8s ease-in-out infinite; transition: animation-duration 0.15s ease; }}
  #oos-cat-wrap.pet #oos-tail, #oos-cat-wrap.excited #oos-tail {{ animation: tailSway 0.5s ease-in-out infinite; }}
  #oos-cat-wrap.annoyed #oos-tail {{ animation: tailTwitch 0.5s ease-in-out infinite; }}
  #oos-cat-wrap.mood-not_found #oos-tail {{ animation-duration: 4.5s; }}
  @keyframes tailSway {{
    0%, 100% {{ transform: rotate(-6deg); }}
    50% {{ transform: rotate(10deg); }}
  }}
  @keyframes tailTwitch {{
    0%, 100% {{ transform: rotate(-3deg); }}
    50% {{ transform: rotate(3deg); }}
  }}

  /* ---- bounce / squish reactions ---- */
  @keyframes catBounce {{
    0%, 100% {{ transform: translateY(0); }}
    30% {{ transform: translateY(-7px); }}
    55% {{ transform: translateY(0); }}
    75% {{ transform: translateY(-2px); }}
  }}
  #oos-cat-wrap.mood-found .cat-body-anim,
  #oos-cat-wrap.mood-refund_success .cat-body-anim,
  #oos-cat-wrap.mood-coupon_success .cat-body-anim,
  #oos-cat-wrap.pet .cat-body-anim {{ animation: catBounce 0.85s ease-out 2; }}
  #oos-cat-wrap.excited .cat-body-anim {{ animation: catBounce 0.4s ease-out infinite; }}

  #oos-cat-wrap.mood-not_found .cat-body-anim {{
    animation: catSigh 2.6s ease-in-out infinite;
  }}
  @keyframes catSigh {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(2px); }}
  }}

  #oos-cat-wrap.mood-searching .oos-paw-l {{ animation: pawTap 0.5s ease-in-out infinite; }}
  #oos-cat-wrap.mood-searching .oos-paw-r {{ animation: pawTap 0.5s ease-in-out infinite 0.25s; }}
  @keyframes pawTap {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-2.5px); }}
  }}

  .cat-screen-glow {{ animation: screenGlow 1.4s ease-in-out infinite; }}
  @keyframes screenGlow {{ 0%, 100% {{ opacity: 0.55; }} 50% {{ opacity: 1; }} }}

  .cat-steam {{ animation: catSteamRise 2.4s ease-in-out infinite; }}
  .cat-steam-2 {{ animation-delay: 0.5s; }}
  @keyframes catSteamRise {{
    0% {{ opacity: 0; transform: translateY(0); }}
    50% {{ opacity: 1; }}
    100% {{ opacity: 0; transform: translateY(-9px); }}
  }}

  .cat-stretch-l {{ transform-origin: 26px 60px; animation: catStretch 2.6s ease-in-out infinite; }}
  .cat-stretch-r {{ transform-origin: 74px 60px; animation: catStretch 2.6s ease-in-out infinite reverse; }}
  @keyframes catStretch {{
    0%, 100% {{ transform: rotate(0deg); }}
    50% {{ transform: rotate(-10deg); }}
  }}

  .cat-zzz {{ animation: catZzz 3.2s ease-in-out infinite; }}
  .cat-zzz-2 {{ animation-delay: 0.7s; }}
  .cat-zzz-3 {{ animation-delay: 1.4s; }}
  @keyframes catZzz {{
    0% {{ opacity: 0; transform: translateY(0) scale(0.8); }}
    35% {{ opacity: 1; }}
    100% {{ opacity: 0; transform: translateY(-15px) scale(1.05); }}
  }}
  #oos-cat-wrap.mood-sleeping .cat-body-anim {{ animation: catBreathe 4.4s ease-in-out infinite; }}

  .cat-sparkle {{ animation: sparklePop 1.1s ease-out infinite; }}
  .cat-sparkle-2 {{ animation-delay: 0.25s; }}
  .cat-sparkle-3 {{ animation-delay: 0.5s; }}
  @keyframes sparklePop {{
    0% {{ opacity: 0; transform: scale(0.3); }}
    40% {{ opacity: 1; transform: scale(1.15); }}
    100% {{ opacity: 0; transform: scale(0.6); }}
  }}

  .cat-heart {{ animation: heartFloat 1.2s ease-out infinite; transform-origin: center; }}
  .cat-heart-2 {{ animation-delay: 0.3s; }}
  .cat-heart-3 {{ animation-delay: 0.6s; }}
  @keyframes heartFloat {{
    0% {{ opacity: 0; transform: translateY(0) scale(0.5); }}
    35% {{ opacity: 1; transform: scale(1); }}
    100% {{ opacity: 0; transform: translateY(-10px) scale(0.8); }}
  }}

  .cat-coupon-card {{ transform-origin: center; animation: couponWiggle 1.8s ease-in-out infinite; }}
  @keyframes couponWiggle {{
    0%, 100% {{ transform: rotate(-4deg); }}
    50% {{ transform: rotate(4deg); }}
  }}

  /* ---- dizzy / sick sequence ---- */
  #oos-cat-wrap.mood-dizzy .cat-body-anim {{ animation: catWobble 0.35s ease-in-out infinite; }}
  @keyframes catWobble {{
    0%, 100% {{ transform: rotate(-6deg) translateY(0); }}
    50% {{ transform: rotate(6deg) translateY(-2px); }}
  }}
  #oos-cat-wrap.mood-sick .cat-body-anim {{ animation: catQueasy 0.9s ease-in-out infinite; }}
  @keyframes catQueasy {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(3px); }}
  }}
  .cat-vomit-drip {{ opacity: 0; animation: vomitDrip 0.9s ease-in-out infinite; }}
  #oos-cat-wrap.mood-sick .cat-vomit-drip {{ opacity: 1; }}
  @keyframes vomitDrip {{
    0%, 100% {{ opacity: 0.2; transform: translateY(0); }}
    50% {{ opacity: 1; transform: translateY(3px); }}
  }}

  /* ---- grab squish ---- */
  #oos-cat-wrap.dragging #oos-cat-body {{ transform: scale(1.06, 0.94); }}
  #oos-cat-body {{ transition: transform 0.12s ease; transform-origin: 50% 85%; }}
</style>

<script>
(function () {{
  // Self-contained widget: everything lives inside this component's own
  // iframe box (no frame-escaping, no full-viewport overlay, no z-index
  // tricks on the frame itself) — safe under strict browser/security
  // policies, and still fully draggable within its own lane.

  var root = document.getElementById('oos-cat-root');
  var wrap = document.getElementById('oos-cat-wrap');
  var speech = document.getElementById('oos-cat-speech');
  var headTilt = document.getElementById('oos-head-tilt');
  var eyeL = document.getElementById('oos-eye-l');
  var eyeR = document.getElementById('oos-eye-r');
  var contextState = root.getAttribute('data-context-state') || 'idle';

  var STORAGE_KEY = 'oos_cat_position_v1';
  var interactionState = null;      // hover | pet | excited | annoyed | dizzy | sick
  var interactionTimer = null;

  function applyMood() {{
    var mood = interactionState || contextState;
    wrap.className = wrap.className
      .split(' ')
      .filter(function (c) {{ return c.indexOf('mood-') !== 0; }})
      .join(' ');
    wrap.classList.add('mood-' + mood);
  }}
  applyMood();

  function say(text, ms) {{
    if (!text) {{
      speech.classList.remove('visible');
      return;
    }}
    speech.textContent = text;
    speech.classList.add('visible');
    window.clearTimeout(speech._t);
    speech._t = window.setTimeout(function () {{
      speech.classList.remove('visible');
    }}, ms || 1600);
  }}

  function setInteraction(state, durationMs, caption) {{
    interactionState = state;
    applyMood();
    if (caption) say(caption, Math.min(durationMs || 1500, 1800));
    window.clearTimeout(interactionTimer);
    if (durationMs) {{
      interactionTimer = window.setTimeout(function () {{
        interactionState = null;
        applyMood();
      }}, durationMs);
    }}
  }}

  // ---- 1. position: restore from sessionStorage, else default
  //         right side of this widget's own lane, away from the
  //         search box. Bounds are this component's own box (root),
  //         not the browser viewport — the cat never leaves its lane.
  function laneSize() {{
    return {{
      w: root.clientWidth || 420,
      h: root.clientHeight || 220,
    }};
  }}

  function clampPos(x, y) {{
    var lane = laneSize();
    var boxW = 110, boxH = 130;
    x = Math.max(4, Math.min(x, lane.w - boxW));
    y = Math.max(4, Math.min(y, lane.h - boxH));
    return {{ x: x, y: y }};
  }}

  function loadPosition() {{
    try {{
      var raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (raw) {{
        var p = JSON.parse(raw);
        if (typeof p.x === 'number' && typeof p.y === 'number') return p;
      }}
    }} catch (e) {{}}
    return null;
  }}

  function savePosition(x, y) {{
    try {{
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({{ x: x, y: y }}));
    }} catch (e) {{}}
  }}

  var saved = loadPosition();
  var pos;
  if (saved) {{
    pos = clampPos(saved.x, saved.y);
  }} else {{
    var lane = laneSize();
    pos = clampPos(lane.w * 0.72, lane.h * 0.28);
  }}
  wrap.style.left = pos.x + 'px';
  wrap.style.top = pos.y + 'px';

  // ---- 2. dragging (pointer events cover mouse + touch + pen) ----
  var dragging = false;
  var dragOffsetX = 0, dragOffsetY = 0;
  var pointerDownAt = 0;
  var pointerDownX = 0, pointerDownY = 0;
  var lastMoveX = 0, lastMoveY = 0, lastMoveT = 0;
  var velX = 0, velY = 0;
  var moved = false;
  var clickCount = 0;
  var clickTimer = null;
  var longPressTimer = null;

  // shake detection: rolling buffer of recent pointer travel distance
  var shakeSamples = [];
  var lastShakeCheck = 0;

  function recordShakeSample(dx, dy, t) {{
    var dist = Math.sqrt(dx * dx + dy * dy);
    shakeSamples.push({{ d: dist, t: t }});
    var cutoff = t - 900;
    while (shakeSamples.length && shakeSamples[0].t < cutoff) shakeSamples.shift();
    var total = 0;
    for (var i = 0; i < shakeSamples.length; i++) total += shakeSamples[i].d;
    if (total > 900 && interactionState !== 'dizzy' && interactionState !== 'sick') {{
      triggerShake();
      shakeSamples = [];
    }}
  }}

  function triggerShake() {{
    window.clearTimeout(interactionTimer);
    setInteraction('dizzy', 900, "Whoa, dizzy! 🌀");
    window.setTimeout(function () {{
      setInteraction('sick', 1400, "🤢");
      window.setTimeout(function () {{
        interactionState = null;
        applyMood();
      }}, 1400);
    }}, 900);
  }}

  wrap.addEventListener('pointerdown', function (e) {{
    dragging = true;
    moved = false;
    wrap.classList.add('dragging');
    try {{ wrap.setPointerCapture(e.pointerId); }} catch (err) {{}}

    var rect = wrap.getBoundingClientRect();
    dragOffsetX = e.clientX - rect.left;
    dragOffsetY = e.clientY - rect.top;

    pointerDownAt = Date.now();
    pointerDownX = e.clientX;
    pointerDownY = e.clientY;
    lastMoveX = e.clientX;
    lastMoveY = e.clientY;
    lastMoveT = pointerDownAt;
    velX = 0; velY = 0;

    // long-press -> annoyed, unless the user starts actually dragging
    window.clearTimeout(longPressTimer);
    longPressTimer = window.setTimeout(function () {{
      if (dragging && !moved) {{
        setInteraction('annoyed', 1300, "Okay okay, let go 😑");
      }}
    }}, 650);

    e.preventDefault();
  }});

  window.addEventListener('pointermove', function (e) {{
    if (!dragging) {{
      // ---- cursor-proximity awareness (hover/look-at, no body follow) ----
      var rect = wrap.getBoundingClientRect();
      var cx = rect.left + rect.width / 2;
      var cy = rect.top + rect.height / 2 - 20;
      var dx = e.clientX - cx;
      var dy = e.clientY - cy;
      var dist = Math.sqrt(dx * dx + dy * dy);
      var NEAR = 140;

      if (dist < NEAR) {{
        if (!wrap.classList.contains('hover') && !interactionState) {{
          wrap.classList.add('hover');
        }}
        var angle = Math.atan2(dy, dx);
        var pupilRange = 1.6;
        var ex = Math.max(-pupilRange, Math.min(pupilRange, Math.cos(angle) * pupilRange));
        var ey = Math.max(-pupilRange, Math.min(pupilRange, Math.sin(angle) * pupilRange));
        eyeL.style.transform = 'translate(' + (42 + ex) + 'px,' + (42 + ey) + 'px)';
        eyeR.style.transform = 'translate(' + (58 + ex) + 'px,' + (42 + ey) + 'px)';
        var tiltAngle = Math.max(-8, Math.min(8, dx / 40));
        headTilt.style.transform = 'rotate(' + tiltAngle + 'deg)';
      }} else {{
        if (wrap.classList.contains('hover')) wrap.classList.remove('hover');
        eyeL.style.transform = 'translate(42px,42px)';
        eyeR.style.transform = 'translate(58px,42px)';
        headTilt.style.transform = 'rotate(0deg)';
      }}
      return;
    }}

    var now = Date.now();
    var newX = e.clientX - dragOffsetX;
    var newY = e.clientY - dragOffsetY;
    var clamped = clampPos(newX, newY);
    wrap.style.left = clamped.x + 'px';
    wrap.style.top = clamped.y + 'px';

    var dt = Math.max(1, now - lastMoveT);
    velX = (e.clientX - lastMoveX) / dt;
    velY = (e.clientY - lastMoveY) / dt;

    recordShakeSample(e.clientX - lastMoveX, e.clientY - lastMoveY, now);

    lastMoveX = e.clientX;
    lastMoveY = e.clientY;
    lastMoveT = now;

    if (Math.abs(e.clientX - pointerDownX) > 4 || Math.abs(e.clientY - pointerDownY) > 4) {{
      moved = true;
      window.clearTimeout(longPressTimer);
    }}

    e.preventDefault();
  }}, {{ passive: false }});

  window.addEventListener('pointerup', function (e) {{
    if (!dragging) return;
    dragging = false;
    wrap.classList.remove('dragging');
    window.clearTimeout(longPressTimer);

    var rect = wrap.getBoundingClientRect();
    var startX = rect.left, startY = rect.top;

    // gentle throw: a little residual travel based on release velocity,
    // then settle with a small bounce — kept subtle and always clamped.
    var throwX = Math.max(-60, Math.min(60, velX * 90));
    var throwY = Math.max(-60, Math.min(60, velY * 90));
    var landed = clampPos(startX + throwX, startY + throwY);

    if (Math.abs(throwX) > 4 || Math.abs(throwY) > 4) {{
      wrap.style.transition = 'left 0.28s cubic-bezier(.2,.8,.3,1.1), top 0.28s cubic-bezier(.2,.8,.3,1.1)';
      wrap.style.left = landed.x + 'px';
      wrap.style.top = landed.y + 'px';
      window.setTimeout(function () {{ wrap.style.transition = ''; }}, 300);
    }}

    savePosition(landed.x, landed.y);

    if (!moved) {{
      // a genuine click/tap (no drag) -> pet / excited logic below
      handleClick();
    }}

    e.preventDefault();
  }});

  wrap.addEventListener('lostpointercapture', function () {{
    if (dragging) {{
      dragging = false;
      wrap.classList.remove('dragging');
    }}
  }});

  // ---- 3. click semantics: single = pet, rapid repeats = excited,
  //         double-click = extra happy burst.
  function handleClick() {{
    clickCount += 1;
    window.clearTimeout(clickTimer);
    clickTimer = window.setTimeout(function () {{
      if (clickCount >= 3) {{
        setInteraction('excited', 1600, "Wheee! 🎉");
      }} else {{
        var captions = ["Purrrr 🐱", "That feels nice!", "Mrow~"];
        var caption = captions[Math.floor(Math.random() * captions.length)];
        setInteraction('pet', 1500, caption);
      }}
      clickCount = 0;
    }}, 260);
  }}

  wrap.addEventListener('dblclick', function (e) {{
    window.clearTimeout(clickTimer);
    clickCount = 0;
    setInteraction('excited', 1800, "Best day ever! 💕");
    e.preventDefault();
  }});

  // ---- 4. keep the cat on-screen if the window is resized ----
  window.addEventListener('resize', function () {{
    var rect = wrap.getBoundingClientRect();
    var clamped = clampPos(rect.left, rect.top);
    wrap.style.left = clamped.x + 'px';
    wrap.style.top = clamped.y + 'px';
    savePosition(clamped.x, clamped.y);
  }});
}})();
</script>
"""

    # A real, visible box (not 0x0) — width is left unset so Streamlit
    # stretches it to the full column width, giving the cat a wide lane
    # to roam and drag around in without needing to escape its iframe.
    components.html(widget_html, height=230)


def status_badge(status):
    """Render a status value as a colored pill badge (display-only)."""
    raw = "" if status is None else str(status)
    key = raw.strip().lower()

    if key == "delivered":
        css_class = "badge-green"
        label = "Delivered"
    elif key == "cancelled":
        css_class = "badge-red"
        label = "Cancelled"
    elif key == "in transit":
        css_class = "badge-blue"
        label = "In Transit"
    elif key == "pending":
        css_class = "badge-orange"
        label = "Pending"
    elif key == "rto":
        css_class = "badge-orange"
        label = "RTO"
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


def prepare_refund_payload(refund_rows, agent_email):
    """
    Convert selected refund rows into the clean payload structure that
    the Google Sheet / refund automation will eventually consume.

    agent_email is appended to every row so the sheet's H column can
    record who submitted each refund. The existing A:G fields
    (channel_id, order_id, variant_id, quantity, amount, refund_reason)
    are completely unchanged.
    """
    payload = []

    for row in refund_rows:
        payload.append(
            {
                "channel_id": row.get("sr_channel_id"),
                "order_id": row.get("zop_order_id"),
                "variant_id": row.get("variant_id"),
                "quantity": int(row.get("quantity")),
                "amount": float(row.get("amount")),
                "refund_reason": row.get("refund_reason"),
                "agent_email": agent_email,
            }
        )

    return payload


def append_refunds_to_gsheet(refund_payload):
    """
    Sends refund data to Google Apps Script.

    Important:
    Apps Script may successfully write the refund but take longer than
    the HTTP timeout to return its response. Therefore a timeout is
    treated as an UNKNOWN result, not an automatic failure.

    We intentionally DO NOT retry the POST automatically because that
    could create duplicate refund rows.
    """

    try:
        webhook_url = st.secrets["gsheet_webhook_url"]

        # Unique submission ID for this refund request.
        # This is useful for future idempotency/verification.
        submission_id = str(uuid.uuid4())

        payload = []

        for row in refund_payload:
            clean_row = {}

            for key, value in row.items():

                # Convert pandas / numpy missing values safely
                if pd.isna(value):
                    clean_row[key] = None

                elif hasattr(value, "item"):
                    try:
                        clean_row[key] = value.item()
                    except Exception:
                        clean_row[key] = str(value)

                else:
                    clean_row[key] = value

            clean_row["submission_id"] = submission_id
            payload.append(clean_row)

        try:

            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30,
            )

        except requests.exceptions.ReadTimeout:

            # IMPORTANT:
            # The POST may already have reached Apps Script and written
            # the rows. DO NOT retry it automatically.

            return {
                "status": "unknown",
                "submission_id": submission_id,
                "message": (
                    "Google Sheet may already have received the refund. "
                    "Please do not submit again."
                ),
            }

        response.raise_for_status()

        try:
            res_json = response.json()
        except ValueError:
            res_json = {}

        if res_json.get("status") == "success":

            return {
                "status": "success",
                "submission_id": submission_id,
                "message": "Refund successfully added to Google Sheet.",
            }

        return {
            "status": "unknown",
            "submission_id": submission_id,
            "message": res_json.get(
                "message",
                "Google Apps Script returned an unexpected response.",
            ),
        }

    except requests.exceptions.RequestException as e:

        raise RuntimeError(
            f"Apps Script connection failed: {str(e)}"
        )

    except Exception as e:

        raise RuntimeError(
            f"Refund submission failed: {str(e)}"
        )


def prepare_coupon_payload(customer_contact, coupon_type, agent_email, order_id=None):
    """
    Build the Special Coupon payload. Completely separate from the
    refund payload/shape — this is never mixed into refund rows and never
    touches the Filtered Data sheet.
    """
    payload = {
        "type": "special_coupon",
        "customer_contact": customer_contact,
        "coupon_type": coupon_type,
        "agent_email": agent_email,
        "submitted_at": datetime.utcnow().isoformat(),
    }

    # Only attach order context if we actually have it — never invented.
    if order_id not in (None, ""):
        payload["order_id"] = order_id

    return payload


def submit_special_coupon(coupon_payload):
    """
    Sends the Special Coupon payload to the same Apps Script Web App
    used for refunds. The Apps Script routes it to the separate
    "Special Coupons" sheet based on payload["type"], so refund rows and
    refund automation are never touched by this call.
    """
    try:
        webhook_url = st.secrets["gsheet_webhook_url"]

        response = requests.post(webhook_url, json=coupon_payload, timeout=15)

        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                return True
            else:
                raise RuntimeError(
                    res_json.get("message", "GAS webapp failed to write coupon")
                )
        else:
            raise RuntimeError(f"HTTP Server Error: {response.status_code}")
    except Exception as e:
        raise RuntimeError(f"Apps Script Connection Failed: {str(e)}")


def render_agent_login():
    """
    Simple session-based Agent Login screen.
    No OAuth / GCP — this just captures the agent's email into
    st.session_state.agent_email for the rest of the browser session.
    """

    st.markdown(
        """
        <div class="oos-hero">
            <div class="oos-eyebrow"><span class="pulse-dot"></span>OrderOS · Agent Access</div>
            <h1>Agent Login</h1>
            <p class="oos-greeting-sub">Enter your company email to open the Agent Dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):

        email_input = st.text_input(
            "Agent Email",
            placeholder="you@company.com",
            key="agent_email_input",
        )

        login_clicked = st.button(
            "Login",
            type="primary",
            use_container_width=True,
            key="agent_login_btn",
        )

        if login_clicked:

            cleaned_email = email_input.strip()

            if not cleaned_email or "@" not in cleaned_email:

                st.error("Please enter a valid company email to continue.")

            else:

                st.session_state.agent_email = cleaned_email
                st.rerun()


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
                Order intelligence, made simple.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "Select Mode",
        ["Agent", "Admin"],
    )

    # Show the logged-in agent's email + Logout button in the sidebar,
    # only relevant while in Agent mode and once logged in.
    if mode == "Agent" and st.session_state.agent_email:

        st.markdown("---")

        st.markdown(
            f'<div style="font-size:0.85rem; color:var(--text-2);">👤 {esc(st.session_state.agent_email)}</div>',
            unsafe_allow_html=True,
        )

        if st.button("Logout", use_container_width=True, key="agent_logout_btn"):

            st.session_state.agent_email = None
            st.session_state.last_search_results = None
            st.session_state.show_refund_confirm = False
            st.session_state.mascot_state = None

            st.rerun()


# =========================================================
# AGENT DASHBOARD
# =========================================================

if mode == "Agent":

    # Gate the entire Agent Dashboard behind agent login.
    if not st.session_state.agent_email:

        render_agent_login()

    else:

        current_hour = get_ist_hour()
        greeting_headline, greeting_sub = get_greeting(current_hour)

        st.markdown(
            '<div class="oos-hero">'
            '<div class="oos-eyebrow"><span class="pulse-dot"></span>OrderOS · Agent Order Intelligence</div>'
            f"<h1>{greeting_headline}</h1>"
            f'<p class="oos-greeting-sub">{greeting_sub}</p>'
            "</div>",
            unsafe_allow_html=True,
        )

        # The cat companion is a floating, draggable desktop-pet style
        # component (see render_cat_companion_widget near the top of this
        # file). It renders itself via a full-viewport overlay and keeps
        # its own position/interaction state client-side, so it survives
        # Streamlit reruns without any Python-side tracking.
        render_cat_companion_widget(get_mascot_state(current_hour))

        # -----------------------------------------------------
        # UNIVERSAL SEARCH
        # -----------------------------------------------------

        search_value = st.text_input(
            "Universal Search",
            placeholder="ZOP Order ID · ZOP ID · Seller Order ID · AWB...",
        )

        search_button = st.button(
            "🔍 Search ",
            type="primary",
            use_container_width=True,
        )

        if search_button:

            if not search_value.strip():

                st.session_state.last_search_results = None

                st.warning(
                    "Search field is empty. Please enter an Order ID, ZOP ID, Seller Order ID or AWB."
                )

            else:

                results = search_orders(search_value)

                if results.empty:

                    st.session_state.last_search_results = None

                    st.session_state.mascot_state = "not_found"

                    st.error("No matching order found.")

                else:

                    st.session_state.last_search_results = results
                    st.session_state.show_refund_confirm = False
                    st.session_state.mascot_state = "found"

                # Rerun so the cat companion (rendered above the search box)
                # reflects the new state right away instead of waiting for
                # the agent's next click.
                st.rerun()

        # -----------------------------------------------------
        # RESULTS DISPLAY
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
                        <span class="tag">Found</span>
                        <span class="id">{esc(order_id)}</span>
                    </div>
                    <div style="margin-top:0.4rem; font-size:0.85rem; font-weight:600; color:var(--accent-2);">
                         Scroll Down for Refund
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # =================================================
            # IDENTIFIERS
            # =================================================

            st.markdown(
                '<div class="oos-section-title">📋 Identifiers </div>',
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

            # Anything that isn't Delivered / Cancelled / In Transit is
            # treated as Pending -- this naturally covers "Order
            # Confirmed", "Accepted", "Pending Pickup", "RTO", and any
            # other pre-shipment status the source data uses.
            pending = (
                ~status_series.isin(["delivered", "cancelled", "in transit"])
            ).sum()

            st.markdown(
                '<div class="oos-section-title">📊 Status Summary </div>',
                unsafe_allow_html=True,
            )

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.markdown(
                stat_card("stat-total", "Total", total_products), unsafe_allow_html=True
            )
            col2.markdown(
                stat_card("stat-delivered", "Delivered", delivered),
                unsafe_allow_html=True,
            )
            col3.markdown(
                stat_card("stat-cancelled", "Cancelled", cancelled),
                unsafe_allow_html=True,
            )
            col4.markdown(
                stat_card("stat-transit", "In Transit", in_transit),
                unsafe_allow_html=True,
            )
            col5.markdown(
                stat_card("stat-pending", "Pending", pending), unsafe_allow_html=True
            )

            # =================================================
            # PRODUCT LEVEL DETAILS
            # =================================================

            st.markdown(
                '<div class="oos-section-title">🛍️ Product Breakdown </div>',
                unsafe_allow_html=True,
            )

            render_product_table(results)

            # =================================================
            # RAW IDENTIFIERS
            # =================================================

            with st.expander("🔍 View all order identifiers"):

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
                '<div class="oos-section-title">💸 Refund Zone </div>',
                unsafe_allow_html=True,
            )

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

            # FIX: use a real Streamlit bordered container instead of a raw
            # HTML div — the previous open/close-div pattern doesn't actually
            # wrap the checkboxes in Streamlit, so it rendered as an empty
            # floating box above the (visually tiny) checkbox list.
            with st.container(border=True):

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

            refund_clicked = st.button(
                "💸 Refund",
                type="primary",
                use_container_width=True,
                disabled=len(selected_products) == 0,
            )

            if refund_clicked:

                st.session_state.show_refund_confirm = True
                st.session_state.mascot_state = "refund"
                st.rerun()

            # -------------------------------------------------
            # SPECIAL COUPON
            # Placed directly below the Refund button, as a separate
            # action. Uses a real Streamlit bordered container.
            # -------------------------------------------------

            st.markdown(
                '<div class="oos-section-title">🎟️ Special Coupon </div>',
                unsafe_allow_html=True,
            )

            coupon_toggle_clicked = st.button(
                "🎟️ Special Coupon",
                use_container_width=True,
                key="open_special_coupon_btn",
            )

            if coupon_toggle_clicked:
                st.session_state.show_coupon_form = (
                    not st.session_state.show_coupon_form
                )
                st.session_state.mascot_state = (
                    "coupon" if st.session_state.show_coupon_form else None
                )
                st.rerun()

            if st.session_state.show_coupon_form:

                with st.container(border=True):

                    st.markdown(
                        '<div style="font-weight:700; font-size:1.05rem; margin-bottom:0.7rem;">Special Coupon</div>',
                        unsafe_allow_html=True,
                    )

                    # Order context comes from the order already open on this
                    # page — never required, never blocks submission if absent.
                    st.caption(f"Linked to order: {order_id}")

                    customer_contact_value = st.text_input(
                        "Customer Contact",
                        placeholder="Phone number or email",
                        key="coupon_customer_contact",
                    )

                    coupon_type_value = st.selectbox(
                        "Coupon Type",
                        COUPON_TYPE_OPTIONS,
                        key="coupon_type_select",
                    )

                    coupon_submit_clicked = st.button(
                        "Submit Special Coupon",
                        type="primary",
                        use_container_width=True,
                        key="submit_special_coupon_btn",
                    )

                    if coupon_submit_clicked:

                        # Validation — mirrors the same guard used for refunds.
                        if not st.session_state.agent_email:

                            st.error(
                                "You must be logged in as an agent to submit a special coupon."
                            )

                        elif not customer_contact_value.strip():

                            st.warning("Please enter the customer's contact detail.")

                        elif coupon_type_value == COUPON_TYPE_PLACEHOLDER:

                            st.warning("Please select a coupon type.")

                        else:

                            coupon_payload = prepare_coupon_payload(
                                customer_contact=customer_contact_value.strip(),
                                coupon_type=coupon_type_value,
                                agent_email=st.session_state.agent_email,
                                order_id=order_id,
                            )

                            try:
                                with st.spinner("Submitting special coupon..."):
                                    submit_special_coupon(coupon_payload)

                                # Reset the form fields for the next submission.
                                st.session_state.show_coupon_form = False
                                for form_key in (
                                    "coupon_customer_contact",
                                    "coupon_type_select",
                                ):
                                    if form_key in st.session_state:
                                        del st.session_state[form_key]

                                st.session_state.mascot_state = "coupon_success"

                                st.success("Special coupon submitted successfully ✅")
                                st.rerun()

                            except Exception as e:
                                st.error(f"❌ Something went wrong: {str(e)}")

            # -------------------------------------------------
            # REFUND CONFIRMATION
            # -------------------------------------------------

            if st.session_state.show_refund_confirm and selected_products:

                st.markdown(
                    '<div class="oos-section-title">🎯 Refund Confirmation</div>',
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
                        "Please select a reason for every product before locking the refund."
                    )

                submit_clicked = st.button(
                    "🔒 Confirm & Lock Refund",
                    type="primary",
                    use_container_width=True,
                    disabled=any_reason_missing,
                )

                if submit_clicked and not any_reason_missing:

                    # Guard — refund cannot be submitted without a logged-in agent.
                    if not st.session_state.agent_email:

                        st.error(
                            "You must be logged in as an agent to submit a refund. Please log in again."
                        )

                    else:

                        refund_payload = prepare_refund_payload(
                            refund_rows, st.session_state.agent_email
                        )

                        # Connect up and append directly to GSheet queue via Web App URL
                        try:
                            with st.spinner(
                                "Locking refund details into the GSheet queue..."
                            ):
                                append_refunds_to_gsheet(refund_payload)

                            st.session_state.show_refund_confirm = False
                            st.session_state.mascot_state = "refund_success"

                            st.success(
                                "🎉 Refund submitted & Google Sheet updated successfully!"
                            )
                        except Exception as e:
                            st.error(f"❌ Something went wrong: {str(e)}")


# =========================================================
# ADMIN DASHBOARD
# =========================================================


else:

    st.markdown(
        """
        <div class="oos-hero">
            <div class="oos-eyebrow"><span class="pulse-dot"></span>OrderOS · Admin Control Console</div>
            <h1>Control Center</h1>
            <p class="oos-greeting-sub">
                Upload today's complete order dump.
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
                <div class="oos-section-title" style="margin-top:0;">Admin Access</div>
                <div style="font-size:0.85rem; color:var(--text-2); margin-bottom:0.8rem;">
                    Enter your credentials to access the admin panel.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        password = st.text_input(
            "Admin Password",
            type="password",
            placeholder="Enter admin password",
        )

        login_button = st.button(
            "Verify & Grant Access",
            type="primary",
        )

        if login_button:

            # TEMPORARY PASSWORD
            # Will move to Streamlit Secrets later.

            if password == "admin123":

                st.session_state.admin_logged_in = True

                st.rerun()

            else:

                st.error("Incorrect password. Please try again.")

        st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================
    # ADMIN PANEL
    # =====================================================

    else:

        top1, top2 = st.columns([5, 1])

        with top1:

            st.success("🛡️ Session authenticated. Full access granted.")

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
            '<div class="oos-section-title">📊 Database Statistics</div>',
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
            "This upload will replace the existing dataset. Please confirm carefully."
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
                # -----------------------------------------

                if "quantity" in df.columns:

                    numeric_qty = pd.to_numeric(df["quantity"], errors="coerce").fillna(
                        0
                    )

                    df["quantity"] = numeric_qty.astype("int64")

                st.write(f"**Rows detected:** {len(df):,}")

                # -----------------------------------------
                # COLUMN VALIDATION
                # -----------------------------------------

                missing_columns = [
                    column for column in REQUIRED_COLUMNS if column not in df.columns
                ]

                if missing_columns:

                    st.error(
                        "❌ Required columns are missing. Please check the file and try again."
                    )

                    st.write("Missing columns:")

                    for column in missing_columns:

                        st.write(f"• `{column}`")

                    st.stop()

                # -----------------------------------------
                # VALID FILE
                # -----------------------------------------

                st.success("✅ File structure is valid.")

                # -----------------------------------------
                # PREVIEW
                # -----------------------------------------

                st.markdown(
                    '<div class="oos-section-title">Schema Preview</div>',
                    unsafe_allow_html=True,
                )

                st.dataframe(
                    df.head(10),
                    use_container_width=True,
                    hide_index=True,
                )

                st.warning(
                    "Uploading this file will replace the current database. "
                    "Please confirm to continue."
                )

                # -----------------------------------------
                # CONFIRM UPLOAD
                # -----------------------------------------

                confirm = st.checkbox("I confirm this is today's complete order dump.")

                if confirm:

                    if st.button(
                        "💾 Replace Database",
                        type="primary",
                        use_container_width=True,
                    ):

                        with st.spinner("Processing transaction data..."):

                            replace_orders(df, uploaded_file.name)

                        st.success(f"🚀 Uploaded {len(df):,} records successfully!")

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

            st.info("No order dump has been uploaded yet.")
