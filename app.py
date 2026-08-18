import streamlit as st
import pandas as pd
import datetime

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
    page_icon="📦",
    layout="wide",
)

# =========================================================
# DATABASE INITIALIZATION
# =========================================================

initialize_database()

# =========================================================
# REQUIRED COLUMNS
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
# SESSION
# =========================================================

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# =========================================================
# INDIAN MEME + APPLE GLASSMORPHISM CSS
# =========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Target App Base Theme with glowing reactive gradients */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #050811 !important;
        background-image: 
            radial-gradient(at 10% 20%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
            radial-gradient(at 90% 80%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
            radial-gradient(at 50% 50%, rgba(236, 72, 153, 0.05) 0px, transparent 50%) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #e2e8f0 !important;
    }
    
    [data-testid="stHeader"] {
        background-color: rgba(5, 8, 17, 0.4) !important;
        backdrop-filter: blur(12px);
    }

    [data-testid="stSidebar"] {
        background-color: rgba(10, 15, 30, 0.7) !important;
        backdrop-filter: blur(24px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }

    /* Glass Cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.02) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
        transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        border-color: rgba(139, 92, 246, 0.3);
        box-shadow: 0 12px 40px 0 rgba(139, 92, 246, 0.15);
    }
    
    /* Metrics block styling */
    .metric-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 24px;
    }
    
    .metric-container {
        flex: 1;
        min-width: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        padding: 18px 12px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.01);
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: all 0.2s ease;
    }
    .metric-container:hover {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        transform: scale(1.02);
    }
    .metric-label {
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 800;
        color: #ffffff;
    }
    
    /* Glowing card status markers */
    .metric-total { border-bottom: 3px solid #a855f7; }
    .metric-delivered { border-bottom: 3px solid #22c55e; }
    .metric-cancelled { border-bottom: 3px solid #ef4444; }
    .metric-transit { border-bottom: 3px solid #3b82f6; }
    .metric-pending { border-bottom: 3px solid #eab308; }

    /* Streamlit overrides */
    .stButton > button {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        color: #f1f5f9 !important;
        padding: 10px 24px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        backdrop-filter: blur(8px);
    }
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.08) !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(255, 255, 255, 0.05);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%) !important;
        border: none !important;
        color: #ffffff !important;
        box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #a78bfa 0%, #60a5fa 100%) !important;
        box-shadow: 0 6px 20px rgba(139, 92, 246, 0.5) !important;
    }

    div[data-baseweb="input"] {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.25) !important;
        background-color: rgba(255, 255, 255, 0.04) !important;
    }
    div[data-baseweb="input"] input {
        color: #ffffff !important;
        font-size: 15px;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
        color: #ffffff !important;
    }
    
    .sidebar-logo {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -1px;
        background: linear-gradient(135deg, #a78bfa 0%, #60a5fa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .hero-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 3.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 30%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .hero-subtitle {
        font-size: 1.2rem;
        color: #94a3b8;
        font-weight: 400;
        margin-top: 6px;
        margin-bottom: 2rem;
    }

    /* Animations */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(16px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    .animate-fade-up {
        animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    /* Elegant labels */
    .field-label {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #64748b;
        margin-bottom: 8px;
    }
    
    /* Clean custom alert frames */
    .custom-error {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 12px;
        padding: 16px;
        color: #fca5a5;
        margin-bottom: 20px;
    }
    .custom-success {
        background: rgba(34, 197, 94, 0.08);
        border: 1px solid rgba(34, 197, 94, 0.25);
        border-radius: 12px;
        padding: 16px;
        color: #86efac;
        margin-bottom: 20px;
    }
    .custom-meme-quote {
        font-style: italic;
        color: #a78bfa;
        font-weight: 500;
        margin-top: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# MEME-AWARE TIME ENGINE
# =========================================================


def get_meme_time_greeting():
    try:
        hour = datetime.datetime.now().hour
    except Exception:
        hour = 12

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
    elif 17 <= hour < 22:
        return (
            "Good evening, mitron. 🌙",
            "Kya chal raha hai? Fogg chal raha hai? Let's make this search easy.",
        )
    else:
        return (
            "Are you still awake? 🦉",
            "Dehaadi majdoori! Ghar jaakr sutti babu.",
        )


# =========================================================
# HELPER FOR MEME STATUS BADGES
# =========================================================


def format_status_badge(status_str):
    if not isinstance(status_str, str):
        return "⚪ Unknown Status"
    status_clean = status_str.strip().lower()
    if status_clean == "delivered":
        return "🟢 Delivered (Mazza Aaya!)"
    elif status_clean == "cancelled":
        return "🔴 Cancelled (Dukh. Dard. Peeda.)"
    elif status_clean == "in transit":
        return "🔵 In Transit (Safar Jaari Hai)"
    elif status_clean == "pending":
        return "🟡 Pending (Thoda Thahar Jao...)"
    else:
        return f"⚪ {status_str.title()}"


# =========================================================
# SIDEBAR SETUP (Where 'mode' is defined)
# =========================================================

st.sidebar.markdown(
    """
    <div class="sidebar-logo">
        <span>📦</span> OrderOS
    </div>
    """,
    unsafe_allow_html=True,
)

mode = st.sidebar.radio(
    "Select Mode",
    [
        "Agent",
        "Admin",
    ],
)


# =========================================================
# AGENT DASHBOARD
# =========================================================

if mode == "Agent":

    greeting_title, greeting_sub = get_meme_time_greeting()

    # Dynamic Hero Welcome Screen
    st.markdown(
        f"""
        <div class="animate-fade-up" style="margin-top: 1.5rem; margin-bottom: 1rem;">
            <span style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 3px; color: #a855f7;">OrderOS Agent Intelligence</span>
            <h1 class="hero-title">{greeting_title}</h1>
            <p class="hero-subtitle">{greeting_sub}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Search Box with Premium Glass Panel
    st.markdown(
        '<div class="field-label">Universal Search Identifier</div>',
        unsafe_allow_html=True,
    )

    search_value = st.text_input(
        "Universal Search Input",
        placeholder="Enter ZOP Order ID / ZOP ID / Seller Order ID / AWB... (Arre jaldi waha se hato!)",
        label_visibility="collapsed",
    )

    st.markdown('<div style="margin-top:12px;"></div>', unsafe_allow_html=True)

    search_button = st.button(
        "🔍 Are jaldi karo subha panwel nikalna hai",
        type="primary",
        use_container_width=True,
    )

    if search_button or (search_value.strip() and not search_button):

        if not search_value.strip():
            st.markdown(
                """
                <div class="custom-error">
                    <strong>O Bhai, Maro Mujhe Maro!</strong> Input empty hai. Please enter an Order ID, ZOP ID, Seller ID, or AWB first.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            results = search_orders(search_value)

            if results.empty:
                st.markdown(
                    """
                    <div class="custom-error">
                        <strong>Yeh toh dukh khatam nahi hota sabka...</strong> No matching order found! (Abhi maza aayega na bhidu)
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                first_row = results.iloc[0]
                order_id = first_row["zop_order_id"]
                zop_id = first_row["zop_id"]
                seller_order_id = first_row["seller_order_id"]

                # Found Header
                st.markdown(
                    f"""
                    <div class="glass-card animate-fade-up" style="margin-top: 2rem; border-left: 5px solid #8b5cf6;">
                        <span style="font-size: 10px; text-transform: uppercase; letter-spacing: 2px; color: #a78bfa; font-weight: 700;">PAISA HI PAISA HOGA! 💸</span>
                        <h2 style="margin: 4px 0 0 0; font-size: 2rem; font-weight: 800;">Order Found: {order_id}</h2>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Identifiers Cards
                st.markdown("### 📋 Identifiers (Kanoon Ke Haath)")
                info1, info2, info3 = st.columns(3)

                with info1:
                    st.markdown(
                        f"""
                        <div class="glass-card" style="padding: 16px;">
                            <div class="field-label">ZOP Order ID</div>
                            <div style="font-size: 16px; font-weight: 700; color: #ffffff;">{order_id}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with info2:
                    st.markdown(
                        f"""
                        <div class="glass-card" style="padding: 16px;">
                            <div class="field-label">ZOP ID</div>
                            <div style="font-size: 16px; font-weight: 700; color: #ffffff;">{zop_id}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with info3:
                    st.markdown(
                        f"""
                        <div class="glass-card" style="padding: 16px;">
                            <div class="field-label">Seller Order ID</div>
                            <div style="font-size: 16px; font-weight: 700; color: #ffffff;">{seller_order_id}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Calculations
                status_series = (
                    results["order_status"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                )

                total_products = len(results)
                delivered = status_series.eq("delivered").sum()
                cancelled = status_series.eq("cancelled").sum()
                in_transit = status_series.eq("in transit").sum()
                pending = status_series.eq("pending").sum()

                # Status Metrics Display
                st.markdown("### 📊 Summary Status (Bawaal Cheez Hai)")
                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.markdown(
                        f"""
                        <div class="metric-container metric-total animate-fade-up">
                            <div class="metric-label">Total items</div>
                            <div class="metric-value">{total_products}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown(
                        f"""
                        <div class="metric-container metric-delivered animate-fade-up">
                            <div class="metric-label">Delivered</div>
                            <div class="metric-value" style="color: #22c55e;">{delivered}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col3:
                    st.markdown(
                        f"""
                        <div class="metric-container metric-cancelled animate-fade-up">
                            <div class="metric-label">Cancelled</div>
                            <div class="metric-value" style="color: #ef4444;">{cancelled}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col4:
                    st.markdown(
                        f"""
                        <div class="metric-container metric-transit animate-fade-up">
                            <div class="metric-label">In Transit</div>
                            <div class="metric-value" style="color: #3b82f6;">{in_transit}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col5:
                    st.markdown(
                        f"""
                        <div class="metric-container metric-pending animate-fade-up">
                            <div class="metric-label">Pending</div>
                            <div class="metric-value" style="color: #eab308;">{pending}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Table Details
                st.markdown("### 🛍️ Product Breakdown (Saman Ki List)")

                display_df = results[
                    [
                        "company_name",
                        "title",
                        "variant_id",
                        "quantity",
                        "order_status",
                        "awb",
                        "sr_channel_id",
                        "final_price",
                    ]
                ].copy()

                display_df.columns = [
                    "Company",
                    "Product",
                    "Variant",
                    "Qty",
                    "Status",
                    "AWB",
                    "Channel ID",
                    "Amount",
                ]

                # Apply status transformations
                display_df["Status"] = display_df["Status"].apply(format_status_badge)

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Amount": st.column_config.NumberColumn(
                            "Amount", format="₹%.2f"
                        ),
                    },
                )

                # Raw Identifiers
                with st.expander("🔍 View All Order Identifiers (Pura Chittha)"):
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


# =========================================================
# ADMIN DASHBOARD
# =========================================================

else:

    # Admin Control Center Hero
    st.markdown(
        """
        <div class="animate-fade-up" style="margin-top: 1.5rem; margin-bottom: 2rem;">
            <span style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 3px; color: #ec4899;">Secure Control Console</span>
            <h1 class="hero-title">OrderOS Control Center</h1>
            <p class="hero-subtitle">Yeh Baburao ka style hai! Upload daily data dumps smoothly.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # PASSWORD GATE
    # -----------------------------------------------------

    if not st.session_state.admin_logged_in:

        st.markdown(
            """
            <div class="glass-card animate-fade-up" style="max-width: 500px; margin: 0 auto; padding: 40px; text-align: center;">
                <div style="font-size: 3.5rem; margin-bottom: 12px;">🛡️</div>
                <h3 style="margin-top:0;">Baburao's Lock Screen</h3>
                <p style="color: #94a3b8; font-size: 14px; margin-bottom: 24px;">Enter verification credentials before we unleash the databases.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        pass_col1, pass_col2, pass_col3 = st.columns([1, 2, 1])
        with pass_col2:
            password = st.text_input(
                "Admin Password",
                type="password",
                label_visibility="collapsed",
                placeholder="Enter password... (Secret key de re baba!)",
            )

            st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)

            login_button = st.button(
                "Verify & Grant Access (Sabaash Beta!)",
                type="primary",
                use_container_width=True,
            )

            if login_button:
                if password == "admin123":
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.markdown(
                        """
                        <div class="custom-error" style="margin-top: 15px; text-align: center;">
                            ❌ <strong>Bilkul Chup!</strong> Incorrect password. Gunda banega re tu?
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # -----------------------------------------------------
    # ADMIN CONTROL CENTER ACTIVE
    # -----------------------------------------------------

    else:

        top1, top2 = st.columns([5, 1])

        with top1:
            st.markdown(
                """
                <div class="custom-success" style="padding: 10px 16px; display: inline-flex; align-items: center; gap: 8px;">
                    🛡️ Session Authenticated (Full power access activated)
                </div>
                """,
                unsafe_allow_html=True,
            )

        with top2:
            if st.button("Logout Console", use_container_width=True):
                st.session_state.admin_logged_in = False
                st.rerun()

        st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)

        # -------------------------------------------------
        # DATABASE STATS
        # -------------------------------------------------

        st.markdown("### 📊 Database Statistics (Pura Ka Pura)")

        record_count = get_order_count()
        last_upload = get_last_upload()

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown(
                f"""
                <div class="metric-container animate-fade-up" style="border-bottom: 3px solid #8b5cf6;">
                    <div class="metric-label">Stored Records Count</div>
                    <div class="metric-value">{record_count:,}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c2:
            last_rec = last_upload[2] if last_upload else 0
            st.markdown(
                f"""
                <div class="metric-container animate-fade-up" style="border-bottom: 3px solid #ec4899;">
                    <div class="metric-label">Last Upload Records</div>
                    <div class="metric-value">{last_rec:,}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c3:
            if last_upload:
                uploaded_at = last_upload[0]
                file_name = last_upload[1]
                st.markdown(
                    f"""
                    <div class="glass-card animate-fade-up" style="padding: 16px; margin-bottom: 0; font-size: 13px; height: 100%;">
                        <div style="font-weight: 700; color: #a78bfa; margin-bottom: 2px;">LAST REFRESH TIMESTAMP</div>
                        <div style="color: #cbd5e1; margin-bottom: 8px;">{uploaded_at}</div>
                        <div style="font-weight: 700; color: #a78bfa; margin-bottom: 2px;">FILE ORIGIN</div>
                        <div style="color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{file_name}">{file_name}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div class="glass-card animate-fade-up" style="padding: 16px; margin-bottom:0; font-size: 13px; text-align: center; color: #94a3b8; display: flex; align-items: center; justify-content: center; height: 100%;">
                        No existing system dump log detected. Database is empty.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)

        # -------------------------------------------------
        # DAILY DUMP IMPORT
        # -------------------------------------------------

        st.markdown("### 📤 Upload Today's Complete Dump")

        st.info(
            "This structural file action entirely replaces the current dataset. "
            "Sambhalke, badme mat bolna data ud gaya!"
        )

        uploaded_file = st.file_uploader(
            "Choose Excel or CSV file",
            type=["xlsx", "xls", "csv"],
            label_visibility="collapsed",
        )

        if uploaded_file:

            try:
                # Read structural data
                if uploaded_file.name.lower().endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                # Clean Whitespace headers
                df.columns = df.columns.astype(str).str.strip()

                st.markdown(
                    f"""
                    <div class="glass-card" style="margin-top: 16px;">
                        <span style="color: #94a3b8; font-size: 13px;">DUMP METRICS</span>
                        <h4 style="margin: 4px 0 0 0;">Total Rows Found: {len(df):,}</h4>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Check and validate required columns
                missing_columns = [
                    column for column in REQUIRED_COLUMNS if column not in df.columns
                ]

                if missing_columns:
                    st.markdown(
                        """
                        <div class="custom-error">
                            <strong>❌ Operational Halt!</strong> Required columns are missing. Yeh kya bawasir bana diye ho?
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.write("Missing structural variables from source:")
                    for column in missing_columns:
                        st.markdown(f"• `{column}`")
                    st.stop()

                # Success Alert
                st.markdown(
                    """
                    <div class="custom-success">
                        ✅ <strong>Bawaal Cheez Hai!</strong> File structure is perfectly valid. Look at the preview below.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Preview Data
                st.markdown("#### Schema Preview (Ek Jhalak)")
                st.dataframe(
                    df.head(10),
                    use_container_width=True,
                    hide_index=True,
                )

                st.warning(
                    "Attn: Uploading this file will completely replace the current database. "
                    "Are you sure you want to trigger this action? (Risk hai toh ishq hai!)"
                )

                # Active confirmation checkbox
                confirm = st.checkbox("I confirm this is today's complete order dump.")

                if confirm:
                    st.markdown(
                        '<div style="margin-top: 10px;"></div>', unsafe_allow_html=True
                    )
                    if st.button(
                        "💾 Replace Database (Karde Bhai!)",
                        type="primary",
                        use_container_width=True,
                    ):
                        with st.spinner(
                            "Processing transaction data... Sabra karo bhidu!"
                        ):
                            replace_orders(df, uploaded_file.name)

                        st.markdown(
                            f"""
                            <div class="custom-success">
                                🚀 Success: Uploaded {len(df):,} records successfully! (Paisa hi paisa!)
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.rerun()

            except Exception as e:
                st.markdown(
                    """
                    <div class="custom-error">
                        ❌ Parser processing failure on file.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.exception(e)

        # -------------------------------------------------
        # ARCHIVED HISTORY LOGS
        # -------------------------------------------------

        st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)
        st.markdown("### 📋 System Archive Log")

        latest_upload = get_last_upload()

        if latest_upload:
            st.markdown(
                f"""
                <div class="glass-card">
                    <div style="font-size: 13px; margin-bottom: 8px;"><strong>Record creation:</strong> {latest_upload[0]}</div>
                    <div style="font-size: 13px; margin-bottom: 8px;"><strong>Import filename:</strong> {latest_upload[1]}</div>
                    <div style="font-size: 13px;"><strong>Indexed structures:</strong> {latest_upload[2]:,}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="glass-card" style="text-align: center; color: #94a3b8;">
                    No recorded updates to system state history.
                </div>
                """,
                unsafe_allow_html=True,
            )
