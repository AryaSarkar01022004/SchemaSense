"""
Database Repository providing typed CRUD operations for SchemaSense.
"""

import json
import sqlite3
from typing import List, Optional, Dict, Any
from app.db.database import db
from app.db.models import (
    User, Workspace, Connection, SchemaTable, SchemaColumn,
    Conversation, Message, SavedQuery, Metric, MetricPoint,
    Insight, EvalCase, EvalRun, now_utc
)


class Repository:
    def __init__(self, database=db):
        self.db = database

    # --- Connections ---
    def create_connection(self, conn_obj: Connection) -> Connection:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO connections (id, workspace_id, name, dialect, host, port, database, username, password_enc, dek_enc, ssl_mode, last_synced_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conn_obj.id, conn_obj.workspace_id, conn_obj.name, conn_obj.dialect,
                conn_obj.host, conn_obj.port, conn_obj.database, conn_obj.username,
                conn_obj.password_enc, conn_obj.dek_enc, conn_obj.ssl_mode,
                conn_obj.last_synced_at, conn_obj.status
            ))
            conn.commit()
        return conn_obj

    def get_connection(self, conn_id: str) -> Optional[Connection]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM connections WHERE id = ?", (conn_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Connection(
                id=row["id"], workspace_id=row["workspace_id"], name=row["name"],
                dialect=row["dialect"], host=row["host"], port=row["port"],
                database=row["database"], username=row["username"],
                password_enc=row["password_enc"], dek_enc=row["dek_enc"],
                ssl_mode=row["ssl_mode"], last_synced_at=row["last_synced_at"],
                status=row["status"]
            )

    def list_connections(self, workspace_id: Optional[str] = None) -> List[Connection]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if workspace_id:
                cur.execute("SELECT * FROM connections WHERE workspace_id = ?", (workspace_id,))
            else:
                cur.execute("SELECT * FROM connections")
            rows = cur.fetchall()
            return [
                Connection(
                    id=r["id"], workspace_id=r["workspace_id"], name=r["name"],
                    dialect=r["dialect"], host=r["host"], port=r["port"],
                    database=r["database"], username=r["username"],
                    password_enc=r["password_enc"], dek_enc=r["dek_enc"],
                    ssl_mode=r["ssl_mode"], last_synced_at=r["last_synced_at"],
                    status=r["status"]
                ) for r in rows
            ]

    def update_connection_status(self, conn_id: str, status: str, last_synced_at: Optional[str] = None):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if last_synced_at:
                cur.execute("UPDATE connections SET status = ?, last_synced_at = ? WHERE id = ?", (status, last_synced_at, conn_id))
            else:
                cur.execute("UPDATE connections SET status = ? WHERE id = ?", (status, conn_id))
            conn.commit()

    # --- Schema Tables & Columns ---
    def save_schema(self, conn_id: str, tables: List[SchemaTable]):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            # Clear previous schema for this connection
            cur.execute("DELETE FROM schema_tables WHERE connection_id = ?", (conn_id,))
            
            for table in tables:
                embedding_str = json.dumps(table.embedding) if table.embedding else None
                cur.execute("""
                INSERT INTO schema_tables (id, connection_id, schema_name, table_name, description, row_estimate, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    table.id, conn_id, table.schema_name, table.table_name,
                    table.description, table.row_estimate, embedding_str
                ))
                
                for col in table.columns:
                    col_emb = json.dumps(col.embedding) if col.embedding else None
                    sample_vals = json.dumps(col.sample_values) if col.sample_values else "[]"
                    cur.execute("""
                    INSERT INTO schema_columns (id, table_id, column_name, data_type, is_pk, is_nullable, fk_table_id, fk_table_name, fk_column, sample_values, distinct_estimate, description, is_sensitive, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        col.id, table.id, col.column_name, col.data_type,
                        1 if col.is_pk else 0, 1 if col.is_nullable else 0,
                        col.fk_table_id, col.fk_table_name, col.fk_column,
                        sample_vals, col.distinct_estimate, col.description,
                        1 if col.is_sensitive else 0, col_emb
                    ))
            conn.commit()

    def get_schema(self, conn_id: str) -> List[SchemaTable]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM schema_tables WHERE connection_id = ? ORDER BY table_name", (conn_id,))
            table_rows = cur.fetchall()
            
            tables: List[SchemaTable] = []
            for tr in table_rows:
                t_id = tr["id"]
                cur.execute("SELECT * FROM schema_columns WHERE table_id = ? ORDER BY is_pk DESC, column_name", (t_id,))
                col_rows = cur.fetchall()
                
                cols = [
                    SchemaColumn(
                        id=cr["id"],
                        table_id=cr["table_id"],
                        column_name=cr["column_name"],
                        data_type=cr["data_type"],
                        is_pk=bool(cr["is_pk"]),
                        is_nullable=bool(cr["is_nullable"]),
                        fk_table_id=cr["fk_table_id"],
                        fk_table_name=cr["fk_table_name"] if "fk_table_name" in cr.keys() else None,
                        fk_column=cr["fk_column"],
                        sample_values=json.loads(cr["sample_values"]) if cr["sample_values"] else [],
                        distinct_estimate=cr["distinct_estimate"] or 0,
                        description=cr["description"] or "",
                        is_sensitive=bool(cr["is_sensitive"]),
                        embedding=json.loads(cr["embedding"]) if cr["embedding"] else None
                    ) for cr in col_rows
                ]
                
                tables.append(SchemaTable(
                    id=tr["id"],
                    connection_id=tr["connection_id"],
                    schema_name=tr["schema_name"],
                    table_name=tr["table_name"],
                    description=tr["description"] or "",
                    row_estimate=tr["row_estimate"] or 0,
                    embedding=json.loads(tr["embedding"]) if tr["embedding"] else None,
                    columns=cols
                ))
            return tables

    def update_column(self, column_id: str, description: Optional[str] = None, is_sensitive: Optional[bool] = None):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if description is not None and is_sensitive is not None:
                cur.execute("UPDATE schema_columns SET description = ?, is_sensitive = ? WHERE id = ?", (description, 1 if is_sensitive else 0, column_id))
            elif description is not None:
                cur.execute("UPDATE schema_columns SET description = ? WHERE id = ?", (description, column_id))
            elif is_sensitive is not None:
                cur.execute("UPDATE schema_columns SET is_sensitive = ? WHERE id = ?", (1 if is_sensitive else 0, column_id))
            conn.commit()

    # --- Conversations & Messages ---
    def create_conversation(self, conv: Conversation) -> Conversation:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO conversations (id, workspace_id, connection_id, user_id, title, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (conv.id, conv.workspace_id, conv.connection_id, conv.user_id, conv.title, conv.created_at))
            conn.commit()
        return conv

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Conversation(
                id=row["id"], workspace_id=row["workspace_id"],
                connection_id=row["connection_id"], user_id=row["user_id"],
                title=row["title"], created_at=row["created_at"]
            )

    def list_conversations(self, workspace_id: Optional[str] = None, connection_id: Optional[str] = None) -> List[Conversation]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM conversations WHERE 1=1"
            params = []
            if workspace_id:
                query += " AND workspace_id = ?"
                params.append(workspace_id)
            if connection_id:
                query += " AND connection_id = ?"
                params.append(connection_id)
            query += " ORDER BY created_at DESC"
            cur.execute(query, tuple(params))
            return [
                Conversation(
                    id=r["id"], workspace_id=r["workspace_id"],
                    connection_id=r["connection_id"], user_id=r["user_id"],
                    title=r["title"], created_at=r["created_at"]
                ) for r in cur.fetchall()
            ]

    def create_message(self, msg: Message) -> Message:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO messages (
                id, conversation_id, role, question, generated_sql, validated_sql,
                status, error, row_count, exec_ms, chart_spec, explanation,
                assumptions, feedback, corrected_sql, llm_tokens_in, llm_tokens_out, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg.id, msg.conversation_id, msg.role, msg.question, msg.generated_sql,
                msg.validated_sql, msg.status, msg.error, msg.row_count, msg.exec_ms,
                json.dumps(msg.chart_spec) if msg.chart_spec else None,
                msg.explanation,
                json.dumps(msg.assumptions) if msg.assumptions else "[]",
                msg.feedback, msg.corrected_sql, msg.llm_tokens_in, msg.llm_tokens_out, msg.created_at
            ))
            conn.commit()
        return msg

    def update_message(self, msg_id: str, **kwargs):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            updates = []
            params = []
            for k, v in kwargs.items():
                if k in ("chart_spec", "assumptions") and v is not None:
                    v = json.dumps(v)
                updates.append(f"{k} = ?")
                params.append(v)
            params.append(msg_id)
            cur.execute(f"UPDATE messages SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()

    def get_messages(self, conv_id: str, limit: int = 50) -> List[Message]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?
            """, (conv_id, limit))
            return [self._row_to_message(r) for r in cur.fetchall()]

    def _row_to_message(self, r: sqlite3.Row) -> Message:
        return Message(
            id=r["id"], conversation_id=r["conversation_id"], role=r["role"],
            question=r["question"], generated_sql=r["generated_sql"],
            validated_sql=r["validated_sql"], status=r["status"],
            error=r["error"], row_count=r["row_count"] or 0,
            exec_ms=r["exec_ms"] or 0,
            chart_spec=json.loads(r["chart_spec"]) if r["chart_spec"] else None,
            explanation=r["explanation"],
            assumptions=json.loads(r["assumptions"]) if r["assumptions"] else [],
            feedback=r["feedback"], corrected_sql=r["corrected_sql"],
            llm_tokens_in=r["llm_tokens_in"] or 0, llm_tokens_out=r["llm_tokens_out"] or 0,
            created_at=r["created_at"]
        )

    def get_past_feedback_examples(self, connection_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """Retrieves past thumbs-up queries for this connection to feed few-shot prompts (Section 5.3 Stage 3)."""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT m.question, COALESCE(m.corrected_sql, m.validated_sql, m.generated_sql) as final_sql
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.connection_id = ? AND m.feedback = 1 AND m.question IS NOT NULL AND m.validated_sql IS NOT NULL
            ORDER BY m.created_at DESC
            LIMIT ?
            """, (connection_id, limit))
            return [{"question": r["question"], "sql": r["final_sql"]} for r in cur.fetchall()]

    # --- Metrics & Insights ---
    def create_metric(self, metric: Metric) -> Metric:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO metrics (id, connection_id, name, sql, schedule_cron, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (metric.id, metric.connection_id, metric.name, metric.sql, metric.schedule_cron, 1 if metric.enabled else 0, metric.created_at))
            conn.commit()
        return metric

    def list_metrics(self, connection_id: Optional[str] = None) -> List[Metric]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            if connection_id:
                cur.execute("SELECT * FROM metrics WHERE connection_id = ?", (connection_id,))
            else:
                cur.execute("SELECT * FROM metrics")
            return [
                Metric(
                    id=r["id"], connection_id=r["connection_id"], name=r["name"],
                    sql=r["sql"], schedule_cron=r["schedule_cron"],
                    enabled=bool(r["enabled"]), created_at=r["created_at"]
                ) for r in cur.fetchall()
            ]

    def add_metric_points(self, points: List[MetricPoint]):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            for p in points:
                cur.execute("INSERT INTO metric_points (metric_id, ts, value) VALUES (?, ?, ?)", (p.metric_id, p.ts, p.value))
            conn.commit()

    def get_metric_points(self, metric_id: str, limit: int = 100) -> List[MetricPoint]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM metric_points WHERE metric_id = ? ORDER BY ts ASC LIMIT ?", (metric_id, limit))
            return [MetricPoint(metric_id=r["metric_id"], ts=r["ts"], value=r["value"]) for r in cur.fetchall()]

    def create_insight(self, insight: Insight) -> Insight:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO insights (id, metric_id, detected_at, severity, summary, detail)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (insight.id, insight.metric_id, insight.detected_at, insight.severity, insight.summary, json.dumps(insight.detail)))
            conn.commit()
        return insight

    def list_insights(self, limit: int = 50) -> List[Insight]:
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM insights ORDER BY detected_at DESC LIMIT ?", (limit,))
            return [
                Insight(
                    id=r["id"], metric_id=r["metric_id"], detected_at=r["detected_at"],
                    severity=r["severity"], summary=r["summary"],
                    detail=json.loads(r["detail"]) if r["detail"] else {}
                ) for r in cur.fetchall()
            ]


repository = Repository()
