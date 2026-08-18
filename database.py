import os
from datetime import datetime

import pandas as pd
import psycopg
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()


# =========================================================
# DATABASE CONNECTION
# =========================================================


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    return database_url


def get_connection():
    """
    Connect to Supabase PostgreSQL through the pooler.

    prepare_threshold=None disables server-side prepared
    statements. This prevents DuplicatePreparedStatement
    errors when using the Supabase pooler.
    """

    return psycopg.connect(get_database_url(), prepare_threshold=None)


# =========================================================
# INITIALIZE DATABASE
# =========================================================


def initialize_database():

    with get_connection() as conn:

        with conn.cursor() as cur:

            # Check that required tables exist
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('orders', 'upload_history')
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

    # Work on a copy
    data = df.copy()

    # -----------------------------------------------------
    # CLEAN COLUMN NAMES
    # -----------------------------------------------------

    data.columns = data.columns.astype(str).str.strip()

    # -----------------------------------------------------
    # REQUIRED COLUMNS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # SELECT ONLY REQUIRED DATA
    # -----------------------------------------------------

    data = data[required_columns].copy()

    # -----------------------------------------------------
    # CLEAN NaN VALUES
    # -----------------------------------------------------

    data = data.where(pd.notna(data), None)

    # -----------------------------------------------------
    # DATA TYPE CLEANING
    # -----------------------------------------------------

    # Dates
    data["order_created_at"] = pd.to_datetime(data["order_created_at"], errors="coerce")

    # Quantity
    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")

    # Amount
    data["final_price"] = pd.to_numeric(data["final_price"], errors="coerce")

    # -----------------------------------------------------
    # CONVERT NaT / NaN TO NONE
    # -----------------------------------------------------

    data = data.astype(object)

    data = data.where(pd.notna(data), None)

    # -----------------------------------------------------
    # CONNECT
    # -----------------------------------------------------

    with get_connection() as conn:

        with conn.cursor() as cur:

            # =============================================
            # REPLACE ENTIRE DAILY DATASET
            # =============================================

            cur.execute("TRUNCATE TABLE orders RESTART IDENTITY")

            # =============================================
            # INSERT DATA
            # =============================================

            insert_query = """
                INSERT INTO orders (
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
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """

            rows = []

            for row in data.itertuples(index=False, name=None):
                rows.append(row)

            # Insert all rows
            cur.executemany(insert_query, rows)

            # =============================================
            # UPLOAD HISTORY
            # =============================================

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


def get_order_count():

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


def get_last_upload():

    query = """
        SELECT
            uploaded_at,
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
