"""
PostgreSQL Setup & Target Connection Onboarding Script.
Applies the demo schema to PostgreSQL, configures the dedicated read-only role,
registers the connection in SchemaSense with envelope encryption, and triggers
schema sync.
"""

import os
import sys
import argparse

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.models import Connection, generate_uuid, now_utc
from app.db.repository import repository
from app.db.target_db import TargetDatabaseManager
from app.security.crypto import envelope_encryptor


def read_sql_file(filename: str) -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def setup_target_postgres(host="localhost", port=5432, database="postgres", username="postgres", password="postgrespassword"):
    print(f"Connecting to PostgreSQL at {host}:{port}/{database}...")
    
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 is not installed. Run 'pip install psycopg2-binary' to execute automated schema provisioning.")
        print(f"Alternatively, you can manually apply the SQL files using psql:")
        print(f"  psql -h {host} -p {port} -U {username} -d {database} -f backend/sql/02_target_postgres_demo.sql")
        return

    try:
        # 1. Connect as admin to provision database and read-only role
        conn = psycopg2.connect(
            host=host, port=port, dbname=database, user=username, password=password
        )
        conn.autocommit = True
        cur = conn.cursor()

        print("Executing target database schema & mock data (02_target_postgres_demo.sql)...")
        demo_sql = read_sql_file("02_target_postgres_demo.sql")
        cur.execute(demo_sql)
        print(" Schema created, tables seeded, and read-only role 'schemasense_readonly' configured.")
        conn.close()

        # 2. Register target connection in SchemaSense using dedicated read-only role
        p_enc, d_enc = envelope_encryptor.encrypt_secret("readonly_secret")
        
        existing_conns = repository.list_connections()
        pg_conn = next((c for c in existing_conns if c.name == "PostgreSQL E-Commerce Production"), None)
        
        if not pg_conn:
            pg_conn = Connection(
                id=generate_uuid(),
                workspace_id="ws-default",
                name="PostgreSQL E-Commerce Production",
                dialect="postgres",
                host=host,
                port=port,
                database=database,
                username="schemasense_readonly",
                password_enc=p_enc,
                dek_enc=d_enc,
                ssl_mode="prefer",
                status="ready"
            )
            repository.create_connection(pg_conn)
            print(f" Registered connection '{pg_conn.name}' ({pg_conn.id}) in SchemaSense.")
        else:
            pg_conn.host = host
            pg_conn.port = port
            pg_conn.database = database
            pg_conn.username = "schemasense_readonly"
            pg_conn.password_enc = p_enc
            pg_conn.dek_enc = d_enc
            print(f" Updated existing connection '{pg_conn.name}' ({pg_conn.id}).")

        # 3. Trigger schema sync
        print("Introspecting schema catalog...")
        tables = TargetDatabaseManager.introspect_schema(pg_conn)
        repository.save_schema(pg_conn.id, tables)
        repository.update_connection_status(pg_conn.id, "ready", now_utc())
        print(f" Synchronized {len(tables)} PostgreSQL tables and column vectors into SchemaSense.")

        print("\nSetup complete! You can now ask questions against your PostgreSQL database in SchemaSense.")

    except Exception as e:
        print(f"Error provisioning PostgreSQL: {e}")
        print("\nIf you are using Docker, simply run:")
        print("  docker compose up -d target-db")
        print("The database will automatically initialize using backend/sql/02_target_postgres_demo.sql.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup PostgreSQL schema for SchemaSense")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", 5432)))
    parser.add_argument("--database", default=os.getenv("PGDATABASE", "postgres"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", "postgrespassword"))
    
    args = parser.parse_args()
    setup_target_postgres(host=args.host, port=args.port, database=args.database, username=args.user, password=args.password)

