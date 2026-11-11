"""
App Database Layer (Control Plane).
Manages persistence for users, workspaces, connections, schema metadata,
conversations, messages, saved queries, metrics, and insights.
Provides a unified interface with SQLite fallback and PostgreSQL readiness.
"""

import sqlite3
import json
import os
from typing import List, Optional, Dict, Any
from app.config import settings
from app.db.models import (
    User, Workspace, Connection, SchemaTable, SchemaColumn,
    Conversation, Message, SavedQuery, Metric, MetricPoint,
    Insight, EvalCase, EvalRun
)


class Database:
    def __init__(self, db_path: str = "schemasense_app.db"):
        self.db_path = db_path
        self._init_sqlite()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_sqlite(self):
        """Initializes tables matching Section 5.1 data model."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                created_at TEXT
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT,
                owner_id TEXT,
                created_at TEXT,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                name TEXT,
                dialect TEXT CHECK (dialect IN ('postgres', 'mysql', 'sqlite')),
                host TEXT,
                port INTEGER,
                database TEXT,
                username TEXT,
                password_enc BLOB,
                dek_enc BLOB,
                ssl_mode TEXT,
                last_synced_at TEXT,
                status TEXT
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_tables (
                id TEXT PRIMARY KEY,
                connection_id TEXT,
                schema_name TEXT,
                table_name TEXT,
                description TEXT,
                row_estimate INTEGER,
                embedding TEXT, -- JSON array of floats for sqlite, vector(1536) for pg
                UNIQUE (connection_id, schema_name, table_name),
                FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_columns (
                id TEXT PRIMARY KEY,
                table_id TEXT,
                column_name TEXT,
                data_type TEXT,
                is_pk BOOLEAN,
                is_nullable BOOLEAN,
                fk_table_id TEXT,
                fk_table_name TEXT,
                fk_column TEXT,
                sample_values TEXT, -- JSON array
                distinct_estimate INTEGER,
                description TEXT,
                is_sensitive BOOLEAN DEFAULT 0,
                embedding TEXT, -- JSON array of floats
                FOREIGN KEY (table_id) REFERENCES schema_tables(id) ON DELETE CASCADE
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                connection_id TEXT,
                user_id TEXT,
                title TEXT,
                created_at TEXT
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                role TEXT,
                question TEXT,
                generated_sql TEXT,
                validated_sql TEXT,
                status TEXT,
                error TEXT,
                row_count INTEGER,
                exec_ms INTEGER,
                chart_spec TEXT,
                explanation TEXT,
                assumptions TEXT,
                feedback INTEGER,
                corrected_sql TEXT,
                llm_tokens_in INTEGER,
                llm_tokens_out INTEGER,
                created_at TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at)")
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS saved_queries (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                name TEXT,
                sql TEXT,
                chart_spec TEXT,
                created_by TEXT,
                created_at TEXT
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id TEXT PRIMARY KEY,
                connection_id TEXT,
                name TEXT,
                sql TEXT,
                schedule_cron TEXT,
                enabled BOOLEAN,
                created_at TEXT
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS metric_points (
                metric_id TEXT,
                ts TEXT,
                value REAL,
                FOREIGN KEY (metric_id) REFERENCES metrics(id) ON DELETE CASCADE
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                metric_id TEXT,
                detected_at TEXT,
                severity TEXT,
                summary TEXT,
                detail TEXT,
                FOREIGN KEY (metric_id) REFERENCES metrics(id) ON DELETE CASCADE
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS eval_cases (
                id TEXT PRIMARY KEY,
                suite TEXT,
                question TEXT,
                gold_sql TEXT,
                schema_fixture TEXT,
                category TEXT
            )
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                id TEXT PRIMARY KEY,
                git_sha TEXT,
                accuracy REAL,
                pass_count INTEGER,
                total_count INTEGER,
                median_latency_ms REAL,
                details TEXT,
                created_at TEXT
            )
            """)
            
            # Seed default user and workspace if empty
            cur.execute("SELECT count(*) FROM users")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO users VALUES (?, ?, ?)", ("user-default", "admin@schemasense.io", models_now := models_now_val()))
                cur.execute("INSERT INTO workspaces VALUES (?, ?, ?, ?)", ("ws-default", "Default Workspace", "user-default", models_now))
                
            conn.commit()


def models_now_val():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# Global DB instance
db = Database()

