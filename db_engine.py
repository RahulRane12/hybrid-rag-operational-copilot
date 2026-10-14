"""
Operational Database Engine for Root-Cause Diagnostic Copilot.
Handles SQLite schema definition, transaction management, metric aggregations,
and hybrid SQL queries reconciling operational logistics metrics (transit latency,
return rates, lost GMV) with SKU metadata.
"""

import sqlite3
import os
from typing import Dict, List, Any, Optional
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "ops_diagnostic.db")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Creates and returns a connection to the SQLite operational database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes the operational tables, indexes, and analytical views."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. SKUs Catalog Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skus (
        sku_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        cogs REAL NOT NULL,
        baseline_return_threshold REAL DEFAULT 0.08,
        catalog_specs TEXT,
        supplier TEXT,
        launch_date TEXT
    );
    """)

    # 2. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        sku_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        unit_price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        gmv REAL NOT NULL,
        carrier TEXT NOT NULL,
        origin_hub TEXT NOT NULL,
        destination_city TEXT NOT NULL,
        destination_state TEXT NOT NULL,
        FOREIGN KEY (sku_id) REFERENCES skus (sku_id)
    );
    """)

    # 3. Fulfillment & Transit Logistics Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fulfillments (
        order_id TEXT PRIMARY KEY,
        dispatched_date TEXT NOT NULL,
        delivered_date TEXT,
        target_transit_days INTEGER NOT NULL,
        actual_transit_days REAL,
        transit_latency_days REAL,
        transit_status TEXT NOT NULL, -- 'DELIVERED', 'TRANSIT_DELAY', 'LOST'
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
    );
    """)

    # 4. Returns & Financial Impact Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS returns (
        return_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        sku_id TEXT NOT NULL,
        return_date TEXT NOT NULL,
        refund_amount REAL NOT NULL,
        return_reason_code TEXT NOT NULL, -- 'SIZE_FIT', 'TRANSIT_DAMAGE', 'LATE_DELIVERY', 'QUALITY_DEFECT', 'NOT_AS_DESCRIBED', 'BUYERS_REMORSE'
        customer_comment TEXT,
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
        FOREIGN KEY (sku_id) REFERENCES skus (sku_id)
    );
    """)

    # 5. Customer Support Tickets / Chat Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_tickets (
        ticket_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        sku_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        channel TEXT NOT NULL, -- 'Chat', 'Email', 'Voice'
        raw_text TEXT NOT NULL,
        sentiment_score REAL,
        sentiment_label TEXT, -- 'NEGATIVE', 'NEUTRAL', 'POSITIVE'
        tagged_issue_category TEXT,
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
        FOREIGN KEY (sku_id) REFERENCES skus (sku_id)
    );
    """)

    # 6. Customer Reviews Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        review_id TEXT PRIMARY KEY,
        sku_id TEXT NOT NULL,
        order_id TEXT NOT NULL,
        rating INTEGER NOT NULL,
        review_title TEXT,
        review_text TEXT NOT NULL,
        review_date TEXT NOT NULL,
        FOREIGN KEY (sku_id) REFERENCES skus (sku_id),
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
    );
    """)

    # Helpful Indexes for fast analytical slicing
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_sku ON orders (sku_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_carrier ON orders (carrier);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_returns_sku ON returns (sku_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_sku ON customer_tickets (sku_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_sku ON reviews (sku_id);")

    conn.commit()
    conn.close()


def get_sku_operational_metrics(db_path: str = DB_PATH) -> pd.DataFrame:
    """
    Computes aggregated SKU-level operational metrics:
    - Total Orders, Total Units, Gross GMV
    - Total Returns, Return Rate (%)
    - Lost GMV from Returns ($)
    - Average Transit Latency (days)
    - Return Threshold Baseline and Anomaly Alert
    """
    query = """
    SELECT 
        s.sku_id,
        s.name AS sku_name,
        s.category,
        s.price,
        s.baseline_return_threshold,
        COALESCE(o_agg.total_orders, 0) AS total_orders,
        ROUND(COALESCE(o_agg.total_gmv, 0.0), 2) AS total_gmv,
        COALESCE(r_agg.total_returns, 0) AS total_returns,
        ROUND(CAST(COALESCE(r_agg.total_returns, 0) AS REAL) / NULLIF(o_agg.total_orders, 0) * 100, 2) AS return_rate_pct,
        ROUND(COALESCE(r_agg.lost_return_gmv, 0.0), 2) AS lost_return_gmv,
        ROUND(COALESCE(f_agg.avg_transit_latency_days, 0.0), 2) AS avg_transit_latency_days,
        ROUND(COALESCE(f_agg.avg_actual_transit_days, 0.0), 2) AS avg_actual_transit_days,
        ROUND(COALESCE(rev_agg.avg_review_rating, 0.0), 2) AS avg_review_rating,
        COALESCE(t_agg.support_ticket_count, 0) AS support_ticket_count
    FROM skus s
    LEFT JOIN (
        SELECT sku_id, COUNT(order_id) AS total_orders, SUM(gmv) AS total_gmv
        FROM orders
        GROUP BY sku_id
    ) o_agg ON s.sku_id = o_agg.sku_id
    LEFT JOIN (
        SELECT o.sku_id, AVG(f.transit_latency_days) AS avg_transit_latency_days, AVG(f.actual_transit_days) AS avg_actual_transit_days
        FROM orders o
        JOIN fulfillments f ON o.order_id = f.order_id
        GROUP BY o.sku_id
    ) f_agg ON s.sku_id = f_agg.sku_id
    LEFT JOIN (
        SELECT sku_id, COUNT(return_id) AS total_returns, SUM(refund_amount) AS lost_return_gmv
        FROM returns
        GROUP BY sku_id
    ) r_agg ON s.sku_id = r_agg.sku_id
    LEFT JOIN (
        SELECT sku_id, AVG(rating) AS avg_review_rating
        FROM reviews
        GROUP BY sku_id
    ) rev_agg ON s.sku_id = rev_agg.sku_id
    LEFT JOIN (
        SELECT sku_id, COUNT(ticket_id) AS support_ticket_count
        FROM customer_tickets
        GROUP BY sku_id
    ) t_agg ON s.sku_id = t_agg.sku_id
    ORDER BY lost_return_gmv DESC;
    """
    conn = get_db_connection(db_path)
    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        # Flag anomalies where return rate exceeds baseline threshold
        df["return_threshold_pct"] = df["baseline_return_threshold"] * 100
        df["baseline_threshold_pct"] = df["return_threshold_pct"]
        df["return_rate_anomaly"] = df["return_rate_pct"] > (df["return_threshold_pct"] * 1.5)
        df["latency_anomaly"] = df["avg_transit_latency_days"] > 1.5
    return df


def get_carrier_logistics_metrics(db_path: str = DB_PATH) -> pd.DataFrame:
    """Aggregates carrier performance, transit latencies, SLA compliance, and transit-related return rates."""
    query = """
    SELECT 
        o.carrier,
        COUNT(DISTINCT o.order_id) AS total_shipments,
        ROUND(AVG(f.target_transit_days), 1) AS target_days,
        ROUND(AVG(f.actual_transit_days), 2) AS avg_transit_days,
        ROUND(AVG(f.transit_latency_days), 2) AS avg_latency_days,
        ROUND(CAST(SUM(CASE WHEN f.transit_latency_days > 1.0 THEN 1 ELSE 0 END) AS REAL) / COUNT(o.order_id) * 100, 2) AS delayed_shipment_pct,
        ROUND(CAST(COUNT(DISTINCT r.return_id) AS REAL) / COUNT(o.order_id) * 100, 2) AS return_rate_pct,
        COALESCE(SUM(r.refund_amount), 0) AS total_return_gmv
    FROM orders o
    JOIN fulfillments f ON o.order_id = f.order_id
    LEFT JOIN returns r ON o.order_id = r.order_id
    GROUP BY o.carrier
    ORDER BY avg_latency_days DESC;
    """
    conn = get_db_connection(db_path)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_route_latency_metrics(db_path: str = DB_PATH) -> pd.DataFrame:
    """Aggregates transit latency across Origin Hub to Destination City routes."""
    query = """
    SELECT 
        o.origin_hub,
        o.destination_city || ', ' || o.destination_state AS destination,
        o.carrier,
        COUNT(o.order_id) AS volume,
        ROUND(AVG(f.actual_transit_days), 2) AS avg_transit_days,
        ROUND(AVG(f.transit_latency_days), 2) AS avg_latency_days,
        ROUND(CAST(SUM(CASE WHEN f.transit_latency_days > 1.5 THEN 1 ELSE 0 END) AS REAL) / COUNT(o.order_id) * 100, 1) AS severe_delay_pct
    FROM orders o
    JOIN fulfillments f ON o.order_id = f.order_id
    GROUP BY o.origin_hub, o.destination_city, o.destination_state, o.carrier
    HAVING volume >= 10
    ORDER BY avg_latency_days DESC;
    """
    conn = get_db_connection(db_path)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_sku_detail(sku_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetches high-level metadata for a specific SKU."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skus WHERE sku_id = ?", (sku_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def execute_custom_query(sql_query: str, db_path: str = DB_PATH) -> pd.DataFrame:
    """Executes a safe read-only SQL query for the copilot query engine."""
    conn = get_db_connection(db_path)
    try:
        df = pd.read_sql_query(sql_query, conn)
    finally:
        conn.close()
    return df
