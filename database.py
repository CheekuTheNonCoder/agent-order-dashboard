import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# DATABASE CONNECTION
# =========================================================


def get_database_url():

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    return database_url


@st.cache_resource(show_spinner=False)
def _get_pool():
    """
    A small connection pool, cached for the lifetime of the app process
    via st.cache_resource -- created once, shared by every user session
    instead of opening a brand new TCP/TLS/auth handshake (and a trip
    through the Supabase Pooler) on every single query.

    A *pool* (rather than one shared raw connection) is used so this
    stays safe when multiple agents use the dashboard at the same
    time -- each concurrent request is handed its own connection
    instead of contending over a single shared one.

    prepare_threshold=None is applied to every pooled connection --
    this is the existing Supabase Pooler fix (avoids
    "DuplicatePreparedStatement: prepared statement already exists"),
    unchanged from before.
    """

    return ConnectionPool(
        get_database_url(),
        min_size=1,
        max_size=5,
        kwargs={"prepare_threshold": None},
        open=True,
    )


def get_connection():
    """
    Returns a context manager for a pooled connection:

        with get_connection() as conn:
            ...

    On exit, the transaction is committed (or rolled back on
    exception) and the connection is returned to the pool for reuse --
    it is NOT closed, unlike a plain psycopg.connect(...) used the
    same way (psycopg 3 closes a bare connection on `with` exit, which
    is why pooling -- not just caching one connection object -- is
    required to actually get reuse). Every call site in this file
    already uses `with get_connection() as conn:`, so nothing else
    needed to change at the call sites.
    """

    return _get_pool().connection()


# =========================================================
# INITIALIZE DATABASE
# =========================================================


@st.cache_resource(show_spinner=False)
def initialize_database():
    """
    Verifies the required tables exist. Cached with st.cache_resource
    so this schema check runs only once per app process instead of on
    every single Streamlit rerun (previously this fired on every
    button click / checkbox toggle across the whole app).
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN (
                    'orders',
                    'upload_history'
                )
            """)

            tables = {row[0] for row in cur.fetchall()}

            if "orders" not in tables:

                raise RuntimeError("orders table does not exist in PostgreSQL.")

            if "upload_history" not in tables:

                raise RuntimeError("upload_history table does not exist in PostgreSQL.")


# =========================================================
# REPLACE ORDERS
# =========================================================


def replace_orders(df, file_name):

    if df is None or df.empty:

        raise ValueError("Uploaded file contains no records.")

    data = df.copy()

    # =====================================================
    # CLEAN COLUMN NAMES
    # =====================================================

    data.columns = data.columns.astype(str).str.strip()

    # =====================================================
    # REQUIRED COLUMNS
    # =====================================================

    required_columns = [
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

    missing = [column for column in required_columns if column not in data.columns]

    if missing:

        raise ValueError("Missing required columns: " + ", ".join(missing))

    # =====================================================
    # SELECT ONLY REQUIRED DATA
    # =====================================================

    data = data[required_columns].copy()

    # =====================================================
    # CLEAN NaN VALUES
    # =====================================================

    data = data.where(pd.notna(data), None)

    # =====================================================
    # DATA TYPE CLEANING
    # =====================================================

    data["order_created_at"] = pd.to_datetime(data["order_created_at"], errors="coerce")

    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")

    data["final_price"] = pd.to_numeric(data["final_price"], errors="coerce")

    # =====================================================
    # CONVERT NaT / NaN TO NONE
    # =====================================================

    data = data.astype(object)

    data = data.where(pd.notna(data), None)

    # =====================================================
    # DATABASE CONNECTION
    # =====================================================

    with get_connection() as conn:

        with conn.cursor() as cur:

            # =================================================
            # REPLACE ENTIRE DAILY DATASET
            # =================================================

            cur.execute("TRUNCATE TABLE orders RESTART IDENTITY")

            # =================================================
            # BULK LOAD ORDERS VIA COPY (STREAMED, NOT
            # MATERIALIZED AS A LIST OF ROWS)
            # =================================================

            copy_query = """

                COPY orders (

                    order_created_at,
                    zop_order_id,
                    zop_id,
                    seller_order_id,
                    company_id,
                    company_name,
                    sr_channel_id,
                    order_status,
                    awb,
                    variant_id,
                    product_id,
                    quantity,
                    title,
                    final_price

                )

                FROM STDIN

            """

            with cur.copy(copy_query) as copy:

                for row in data.itertuples(index=False, name=None):

                    copy.write_row(row)

            # =================================================
            # UPLOAD HISTORY
            # =================================================

            cur.execute(
                """

                INSERT INTO upload_history (

                    file_name,
                    record_count

                )

                VALUES (%s, %s)

                """,
                (file_name, len(data)),
            )

        conn.commit()

    # =====================================================
    # INVALIDATE CACHED ADMIN STATS
    # =====================================================
    # get_order_count() and get_last_upload() are cached below (see
    # their @st.cache_data decorators) so the Admin panel doesn't hit
    # the database on every rerun. Clearing them here means the
    # Control Center reflects this upload immediately instead of
    # waiting out the cache TTL.

    get_order_count.clear()
    get_last_upload.clear()


# =========================================================
# UNIVERSAL SEARCH
# =========================================================


def search_orders(search_value):

    search_value = str(search_value).strip()

    if not search_value:

        return pd.DataFrame()

    query = """

        SELECT

            order_created_at,
            zop_order_id,
            zop_id,
            seller_order_id,
            company_id,
            company_name,
            sr_channel_id,
            order_status,
            awb,
            variant_id,
            product_id,
            quantity,
            title,
            final_price

        FROM orders

        WHERE

            CAST(zop_order_id AS TEXT) ILIKE %s

            OR CAST(zop_id AS TEXT) ILIKE %s

            OR CAST(seller_order_id AS TEXT) ILIKE %s

            OR CAST(awb AS TEXT) ILIKE %s

        ORDER BY

            order_created_at DESC NULLS LAST

    """

    pattern = f"%{search_value}%"

    with get_connection() as conn:

        return pd.read_sql_query(
            query,
            conn,
            params=[
                pattern,
                pattern,
                pattern,
                pattern,
            ],
        )


# =========================================================
# ORDER COUNT
# =========================================================


@st.cache_data(ttl=30, show_spinner=False)
def get_order_count():
    """
    Cached for 30 seconds so the Admin panel doesn't re-hit the
    database on every rerun (every checkbox toggle, etc). Explicitly
    cleared by replace_orders() right after a successful upload, so
    the count is never stale after the action that actually changes it.
    """

    query = """

        SELECT COUNT(*)
        FROM orders

    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(query)

            result = cur.fetchone()

            return result[0] if result else 0


# =========================================================
# LAST UPLOAD
# =========================================================


@st.cache_data(ttl=30, show_spinner=False)
def get_last_upload():
    """
    Cached for 30 seconds for the same reason as get_order_count().
    Explicitly cleared by replace_orders() right after a successful
    upload.
    """

    query = """

        SELECT

            uploaded_at AT TIME ZONE 'Asia/Kolkata'
                AS uploaded_at,

            file_name,

            record_count

        FROM upload_history

        ORDER BY uploaded_at DESC

        LIMIT 1

    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(query)

            return cur.fetchone()
