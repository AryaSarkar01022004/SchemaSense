"""
Demo Target Database Seeder (E-Commerce & SaaS Fixture).
Creates a realistic database with customers, products, orders, order_items, and subscriptions.
Registers the connection into SchemaSense and triggers automatic schema sync.
"""

import os
import sqlite3
import random
from datetime import datetime, timedelta, timezone

from app.db.models import Connection, generate_uuid, now_utc
from app.db.repository import repository
from app.db.target_db import TargetDatabaseManager
from app.security.crypto import envelope_encryptor


def seed_demo_database(db_path: str = "demo_target.db") -> str:
    print(f"Creating demo target database at {db_path}...")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Customers
    cur.execute("""
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        country TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # 2. Products
    cur.execute("""
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock_quantity INTEGER NOT NULL
    )
    """)

    # 3. Orders
    cur.execute("""
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        status TEXT CHECK (status IN ('pending', 'paid', 'shipped', 'refunded')),
        total_amount REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """)

    # 4. Order Items
    cur.execute("""
    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """)

    # 5. Subscriptions (SaaS MRR)
    cur.execute("""
    CREATE TABLE subscriptions (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        plan_name TEXT NOT NULL,
        monthly_mrr REAL NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """)

    # Seed Customers
    countries = ["USA", "Germany", "France", "Japan", "United Kingdom", "Canada", "Australia"]
    names = [
        "Alice Johnson", "Bob Smith", "Charlie Brown", "Diana Prince", "Evan Wright",
        "Fiona Gallagher", "George Clark", "Hannah Abbott", "Ian Malcolm", "Julia Roberts"
    ]
    for i, name in enumerate(names, start=1):
        email = f"{name.lower().replace(' ', '.')}@example.com"
        country = countries[i % len(countries)]
        created_at = (datetime.now(timezone.utc) - timedelta(days=random.randint(30, 365))).isoformat()
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", (i, name, email, country, created_at))

    # Seed Products
    products = [
        ("Cloud Analytics Pro", "Software", 299.00, 100),
        ("Database Firewall", "Security", 499.00, 50),
        ("API Gateway License", "Infrastructure", 149.00, 200),
        ("Storage Volume 1TB", "Storage", 25.00, 500),
        ("Developer Seat", "Software", 49.00, 1000)
    ]
    for i, (p_name, cat, price, stock) in enumerate(products, start=1):
        cur.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)", (i, p_name, cat, price, stock))

    # Seed Orders & Order Items
    statuses = ["paid", "paid", "paid", "shipped", "pending", "refunded"]
    for o_id in range(1, 41):
        cust_id = (o_id % len(names)) + 1
        st = statuses[o_id % len(statuses)]
        prod_id = (o_id % len(products)) + 1
        qty = (o_id % 3) + 1
        unit_price = products[prod_id - 1][2]
        tot = round(qty * unit_price, 2)
        created_at = (datetime.now(timezone.utc) - timedelta(days=o_id * 3)).isoformat()
        
        cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", (o_id, cust_id, st, tot, created_at))
        cur.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", (o_id, o_id, prod_id, qty, unit_price))

    # Seed Subscriptions
    plans = [("Starter", 49.0), ("Growth", 199.0), ("Enterprise", 999.0)]
    for s_id in range(1, 11):
        cust_id = s_id
        plan_name, mrr = plans[s_id % len(plans)]
        started_at = (datetime.now(timezone.utc) - timedelta(days=s_id * 20)).isoformat()
        cur.execute("INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?)", (s_id, cust_id, plan_name, mrr, "active", started_at))

    conn.commit()
    conn.close()
    print("Demo target database created successfully.")

    # Register into SchemaSense App Database
    existing_conns = repository.list_connections()
    demo_conn = next((c for c in existing_conns if c.name == "Demo E-Commerce Store"), None)
    
    if not demo_conn:
        p_enc, d_enc = envelope_encryptor.encrypt_secret("demo_password")
        demo_conn = Connection(
            id="conn-demo-ecommerce",
            workspace_id="ws-default",
            name="Demo E-Commerce Store",
            dialect="sqlite",
            host="localhost",
            port=0,
            database=os.path.abspath(db_path),
            username="admin",
            password_enc=p_enc,
            dek_enc=d_enc,
            ssl_mode="disable",
            status="ready"
        )
        repository.create_connection(demo_conn)
        print(f"Registered connection '{demo_conn.name}' ({demo_conn.id}).")
    else:
        demo_conn.database = os.path.abspath(db_path)
        print(f"Using existing connection '{demo_conn.name}' ({demo_conn.id}).")

    # Introspect schema and save
    tables = TargetDatabaseManager.introspect_schema(demo_conn)
    repository.save_schema(demo_conn.id, tables)
    repository.update_connection_status(demo_conn.id, "ready", now_utc())
    print(f"Introspected and synchronized {len(tables)} tables with vector embeddings.")

    # Seed metric points for Anomaly Detection test
    seed_anomaly_metric(demo_conn.id)

    return demo_conn.id


def seed_anomaly_metric(conn_id: str):
    metrics = repository.list_metrics(conn_id)
    metric = next((m for m in metrics if m.name == "Daily Revenue"), None)
    if not metric:
        from app.db.models import Metric, MetricPoint
        metric = Metric(
            id="metric-daily-revenue",
            connection_id=conn_id,
            name="Daily Revenue",
            sql="SELECT SUM(total_amount) FROM orders WHERE created_at >= date('now', '-1 day')",
            schedule_cron="0 0 * * *"
        )
        repository.create_metric(metric)

        # Generate 14 days of normal points around $1,200
        points = []
        base_time = datetime.now(timezone.utc) - timedelta(days=15)
        for i in range(14):
            t = (base_time + timedelta(days=i)).isoformat()
            val = round(random.uniform(1100, 1300), 2)
            points.append(MetricPoint(metric_id=metric.id, ts=t, value=val))

        # Add an anomalous spike on day 15 ($4,850)
        spike_time = datetime.now(timezone.utc).isoformat()
        points.append(MetricPoint(metric_id=metric.id, ts=spike_time, value=4850.0))
        repository.add_metric_points(points)
        print(f"Seeded 15 metric points for '{metric.name}' (including an anomaly spike).")


if __name__ == "__main__":
    seed_demo_database()

