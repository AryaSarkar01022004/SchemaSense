"""
SchemaSense API Server (Section 5.11).
Implements all required REST & SSE endpoints:
- POST  /api/connections
- POST  /api/connections/upload (CSV, TSV, XLS, XLSX file upload)
- GET   /api/connections
- POST  /api/connections/{id}/sync
- GET   /api/connections/{id}/schema
- PATCH /api/schema/columns/{id}
- POST  /api/conversations
- GET   /api/conversations
- GET   /api/conversations/{id}/messages
- POST  /api/conversations/{id}/ask (SSE Stream)
- POST  /api/queries/run
- POST  /api/messages/{id}/feedback
- POST  /api/metrics
- GET   /api/metrics
- GET   /api/insights
- GET   /api/settings/llm
- POST  /api/settings/llm
- GET   /api/settings/llm/lmstudio/models
- GET   /api/settings/llm/gemini/models
- POST  /api/settings/llm/test
- POST  /api/assistant/chat
- GET   /api/health
"""

import os
import json
import asyncio
import http.server
import socketserver
import urllib.parse
from email.parser import BytesParser
from email.policy import default as email_default_policy
from typing import Dict, Any, Optional, List, Tuple

from app.config import settings
from app.db.models import Connection, Conversation, Message, Metric, generate_uuid, now_utc
from app.db.repository import repository
from app.db.target_db import TargetDatabaseManager
from app.security.crypto import envelope_encryptor
from app.safety.validator import SQLValidator
from app.orchestrator.pipeline import orchestrator
from app.services.explanation import query_explainer
from app.services.viz_recommender import viz_recommender
from app.services.llm_client import llm_client
from app.services.file_ingest import file_ingestor
from app.services.schema_retriever import SchemaRetriever
from app.services.visualizer import visualizer_service
from app.services.export_email import email_export_service


class SchemaSenseAPIHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data: Any):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_raw_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return b""
        return self.rfile.read(content_length)

    def _read_json(self) -> Dict[str, Any]:
        raw = self._read_raw_body()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _parse_multipart(self) -> Tuple[Dict[str, str], List[Tuple[str, bytes]]]:
        content_type = self.headers.get("Content-Type", "")
        raw_body = self._read_raw_body()
        if "multipart/form-data" not in content_type.lower():
            raise ValueError("Expected multipart/form-data Content-Type")
        msg = BytesParser(policy=email_default_policy).parsebytes(
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8") + raw_body
        )
        fields: Dict[str, str] = {}
        files: List[Tuple[str, bytes]] = []
        for part in msg.iter_parts():
            field_name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files.append((filename, payload))
            elif field_name:
                fields[field_name] = payload.decode("utf-8", errors="replace")
        return fields, files

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("", "/api/health"):
            self._send_json(200, {"status": "ok", "service": "SchemaSense API", "version": "1.0.0"})
            return

        # GET /api/settings/llm
        if path == "/api/settings/llm":
            self._send_json(200, {
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL,
                "lmstudio_base_url": settings.LMSTUDIO_BASE_URL,
                "lmstudio_api_key": settings.LMSTUDIO_API_KEY,
                "has_openai_key": bool(settings.OPENAI_API_KEY),
                "has_gemini_key": bool(settings.GEMINI_API_KEY),
                "timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
            })
            return

        # GET /api/settings/llm/lmstudio/models
        if path == "/api/settings/llm/lmstudio/models":
            base_url = query.get("base_url", [None])[0]
            result = llm_client.list_lmstudio_models(base_url=base_url)
            self._send_json(200, result)
            return

        # GET /api/settings/llm/gemini/models
        if path == "/api/settings/llm/gemini/models":
            result = llm_client.list_gemini_models()
            self._send_json(200, result)
            return

        # GET /api/settings/email
        if path == "/api/settings/email":
            self._send_json(200, {
                "smtp_host": settings.SMTP_HOST,
                "smtp_port": settings.SMTP_PORT,
                "smtp_user": settings.SMTP_USER or "",
                "has_smtp_password": bool(settings.SMTP_PASSWORD),
                "smtp_configured": email_export_service.is_smtp_configured(),
            })
            return

        # GET /api/connections
        if path == "/api/connections":
            conns = repository.list_connections()
            data = [
                {
                    "id": c.id, "name": c.name, "dialect": c.dialect,
                    "host": c.host, "port": c.port, "database": c.database,
                    "username": c.username, "status": c.status,
                    "last_synced_at": c.last_synced_at
                } for c in conns
            ]
            self._send_json(200, data)
            return

        # GET /api/connections/{id}/schema
        if path.startswith("/api/connections/") and path.endswith("/schema"):
            conn_id = path.split("/")[3]
            tables = repository.get_schema(conn_id)
            tables_data = [
                {
                    "id": t.id, "schema_name": t.schema_name, "table_name": t.table_name,
                    "description": t.description, "row_estimate": t.row_estimate,
                    "columns": [
                        {
                            "id": c.id, "column_name": c.column_name, "data_type": c.data_type,
                            "is_pk": c.is_pk, "is_nullable": c.is_nullable,
                            "fk_column": c.fk_column, "fk_table_name": c.fk_table_name,
                            "sample_values": c.sample_values, "distinct_estimate": c.distinct_estimate,
                            "description": c.description, "is_sensitive": c.is_sensitive
                        } for c in t.columns
                    ]
                } for t in tables
            ]
            self._send_json(200, {"tables": tables_data})
            return

        # GET /api/conversations
        if path == "/api/conversations":
            convs = repository.list_conversations()
            data = [{"id": c.id, "title": c.title, "connection_id": c.connection_id, "created_at": c.created_at} for c in convs]
            self._send_json(200, data)
            return

        # GET /api/conversations/{id}/messages
        if path.startswith("/api/conversations/") and path.endswith("/messages"):
            conv_id = path.split("/")[3]
            msgs = repository.get_messages(conv_id)
            data = [
                {
                    "id": m.id, "role": m.role, "question": m.question,
                    "generated_sql": m.generated_sql, "validated_sql": m.validated_sql,
                    "status": m.status, "error": m.error, "row_count": m.row_count,
                    "exec_ms": m.exec_ms, "chart_spec": m.chart_spec,
                    "explanation": m.explanation, "assumptions": m.assumptions,
                    "feedback": m.feedback, "created_at": m.created_at
                } for m in msgs
            ]
            self._send_json(200, data)
            return

        # GET /api/metrics
        if path == "/api/metrics":
            metrics = repository.list_metrics()
            data = [{"id": m.id, "name": m.name, "sql": m.sql, "cron": m.schedule_cron, "enabled": m.enabled} for m in metrics]
            self._send_json(200, data)
            return

        # GET /api/insights
        if path == "/api/insights":
            insights = repository.list_insights()
            data = [
                {
                    "id": i.id, "metric_id": i.metric_id, "detected_at": i.detected_at,
                    "severity": i.severity, "summary": i.summary, "detail": i.detail
                } for i in insights
            ]
            self._send_json(200, data)
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        # POST /api/connections/upload (CSV, TSV, XLS, XLSX ingestion)
        if path == "/api/connections/upload":
            try:
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" in content_type.lower():
                    fields, files = self._parse_multipart()
                    conn_name = fields.get("name", "").strip()
                else:
                    # JSON base64 fallback
                    import base64
                    payload = self._read_json()
                    conn_name = (payload.get("name") or "").strip()
                    files = [
                        (f["filename"], base64.b64decode(f["content_base64"]))
                        for f in payload.get("files", [])
                    ]

                if not files:
                    self._send_json(400, {"error": "No CSV or Excel (.xls, .xlsx) files provided."})
                    return

                conn_id = generate_uuid()
                if not conn_name:
                    first_base = os.path.splitext(os.path.basename(files[0][0]))[0]
                    conn_name = first_base if len(files) == 1 else f"{first_base} (+{len(files)-1} files)"

                db_path = os.path.join(settings.UPLOAD_DIR, f"{conn_id}.db")
                ingested_tables = file_ingestor.ingest_files_to_sqlite(files, db_path)

                password_enc, dek_enc = envelope_encryptor.encrypt_secret("")
                conn_obj = Connection(
                    id=conn_id,
                    workspace_id="ws-default",
                    name=conn_name,
                    dialect="sqlite",
                    host="uploaded-file",
                    port=0,
                    database=db_path,
                    username="file-upload",
                    password_enc=password_enc,
                    dek_enc=dek_enc,
                    ssl_mode="disable",
                    last_synced_at=now_utc(),
                    status="ready",
                )
                repository.create_connection(conn_obj)

                tables = TargetDatabaseManager.introspect_schema(conn_obj)
                if tables:
                    repository.save_schema(conn_obj.id, tables)
                    repository.update_connection_status(conn_obj.id, "ready", now_utc())

                self._send_json(201, {
                    "id": conn_obj.id,
                    "name": conn_obj.name,
                    "dialect": conn_obj.dialect,
                    "status": conn_obj.status,
                    "tables_discovered": len(tables),
                    "ingested_tables": ingested_tables,
                })
            except Exception as e:
                self._send_json(400, {"error": f"File ingestion failed: {str(e)}"})
            return

        body = self._read_json()

        # POST /api/settings/llm
        if path == "/api/settings/llm":
            settings.save_llm_settings(body)
            self._send_json(200, {
                "status": "saved",
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL,
                "lmstudio_base_url": settings.LMSTUDIO_BASE_URL,
                "has_openai_key": bool(settings.OPENAI_API_KEY),
                "has_gemini_key": bool(settings.GEMINI_API_KEY),
            })
            return

        # POST /api/settings/llm/test
        if path == "/api/settings/llm/test":
            try:
                if body:
                    settings.save_llm_settings(body)
                result = llm_client.test_connection()
                status_code = 200 if result.get("ok") else 400
                self._send_json(status_code, result)
            except Exception as e:
                self._send_json(400, {"ok": False, "error": str(e)})
            return

        # POST /api/assistant/chat (Interactive Analysis Assistant Chat Window)
        if path == "/api/assistant/chat":
            try:
                messages = body.get("messages", [])
                conn_id = body.get("connection_id")
                active_sql = body.get("active_sql", "")
                active_columns = body.get("active_columns") or []
                sample_rows = body.get("sample_rows") or []

                conn_obj = repository.get_connection(conn_id) if conn_id else None
                if not conn_obj:
                    conns = repository.list_connections()
                    conn_obj = conns[0] if conns else None

                schema_context = ""
                conn_name = ""
                if conn_obj:
                    conn_name = f"{conn_obj.name} ({conn_obj.dialect})"
                    tables = repository.get_schema(conn_obj.id)
                    if not tables:
                        tables = TargetDatabaseManager.introspect_schema(conn_obj)
                    if tables:
                        schema_context = SchemaRetriever.format_compact_schema(tables[:15])

                insights = repository.list_insights(limit=3)
                insights_summary = "\n".join(
                    f"- [{ins.severity.upper()}] {ins.summary}" for ins in insights
                ) if insights else ""

                result = llm_client.assistant_chat(
                    messages=messages,
                    schema_context=schema_context,
                    connection_name=conn_name,
                    active_sql=active_sql,
                    active_columns=active_columns,
                    sample_rows=sample_rows,
                    insights_summary=insights_summary,
                )
                self._send_json(200, result)
            except Exception as e:
                self._send_json(500, {"error": str(e), "reply": f"Assistant error: {e}", "suggested_questions": []})
            return

        # POST /api/settings/email
        if path == "/api/settings/email":
            settings.save_llm_settings({
                "smtp_host": body.get("smtp_host", settings.SMTP_HOST),
                "smtp_port": body.get("smtp_port", settings.SMTP_PORT),
                "smtp_user": body.get("smtp_user", ""),
                "smtp_password": body.get("smtp_password", ""),
            })
            self._send_json(200, {
                "status": "saved",
                "smtp_host": settings.SMTP_HOST,
                "smtp_port": settings.SMTP_PORT,
                "smtp_user": settings.SMTP_USER or "",
                "has_smtp_password": bool(settings.SMTP_PASSWORD),
                "smtp_configured": email_export_service.is_smtp_configured(),
            })
            return

        # POST /api/visualizer/query
        if path == "/api/visualizer/query":
            try:
                res = visualizer_service.run_visual_query(
                    connection_id=body.get("connection_id", ""),
                    table_name=body.get("table_name", ""),
                    x_col=body.get("x_col", ""),
                    y_col=body.get("y_col"),
                    aggregation=body.get("aggregation", "COUNT"),
                    chart_type=body.get("chart_type", "bar"),
                    limit=int(body.get("limit", 15)),
                    sort_dir=body.get("sort_dir", "DESC"),
                )
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        # POST /api/visualizer/discover
        if path == "/api/visualizer/discover":
            try:
                res = visualizer_service.discover_charts(
                    connection_id=body.get("connection_id", ""),
                    table_name=body.get("table_name"),
                )
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        # POST /api/export/email (Gmail Web Compose URL or Direct SMTP with CSV attachment)
        if path == "/api/export/email":
            try:
                res = email_export_service.export_email(
                    to=body.get("to", ""),
                    subject=body.get("subject", "SchemaSense Data Report"),
                    note=body.get("note", ""),
                    insight=body.get("insight", ""),
                    sql=body.get("sql", ""),
                    columns=body.get("columns"),
                    rows=body.get("rows"),
                    attachment_filename=body.get("attachment_filename", "schemasense_report.csv"),
                    send_direct=bool(body.get("send_direct", False)),
                )
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e), "sent": False})
            return

        # POST /api/connections
        if path == "/api/connections":
            name = body.get("name", "New Connection")
            dialect = body.get("dialect", "postgres").lower()
            host = body.get("host", "localhost")
            port = int(body.get("port", 5432))
            database = body.get("database", "")
            username = body.get("username", "")
            password = body.get("password", "")

            # Envelope encryption (Section 5.1 & 5.13)
            password_enc, dek_enc = envelope_encryptor.encrypt_secret(password)

            conn_obj = Connection(
                id=generate_uuid(),
                workspace_id="ws-default",
                name=name,
                dialect=dialect,
                host=host,
                port=port,
                database=database,
                username=username,
                password_enc=password_enc,
                dek_enc=dek_enc,
                ssl_mode=body.get("ssl_mode", "prefer"),
                status="ready"
            )
            repository.create_connection(conn_obj)
            
            # Immediately trigger initial schema introspection
            tables = TargetDatabaseManager.introspect_schema(conn_obj)
            if tables:
                repository.save_schema(conn_obj.id, tables)
                repository.update_connection_status(conn_obj.id, "ready", now_utc())

            self._send_json(201, {
                "id": conn_obj.id, "name": conn_obj.name, "dialect": conn_obj.dialect,
                "status": conn_obj.status, "tables_discovered": len(tables)
            })
            return

        # POST /api/connections/{id}/sync
        if path.startswith("/api/connections/") and path.endswith("/sync"):
            conn_id = path.split("/")[3]
            conn_obj = repository.get_connection(conn_id)
            if not conn_obj:
                self._send_json(404, {"error": "Connection not found"})
                return

            tables = TargetDatabaseManager.introspect_schema(conn_obj)
            repository.save_schema(conn_id, tables)
            repository.update_connection_status(conn_id, "ready", now_utc())
            self._send_json(200, {
                "status": "synced",
                "tables_count": len(tables),
                "synced_at": now_utc()
            })
            return

        # POST /api/conversations
        if path == "/api/conversations":
            connection_id = body.get("connection_id")
            title = body.get("title", "Database Q&A")
            conv = Conversation(
                id=generate_uuid(),
                workspace_id="ws-default",
                connection_id=connection_id or "",
                title=title
            )
            repository.create_conversation(conv)
            self._send_json(201, {"id": conv.id, "title": conv.title, "connection_id": conv.connection_id})
            return

        # POST /api/conversations/{id}/ask (SSE Streaming Endpoint)
        if path.startswith("/api/conversations/") and path.endswith("/ask"):
            conv_id = path.split("/")[3]
            question = body.get("question", "").strip()
            if not question:
                self._send_json(400, {"error": "Question is required"})
                return

            conv = repository.get_conversation(conv_id)
            if not conv:
                self._send_json(404, {"error": "Conversation not found"})
                return

            conn_obj = repository.get_connection(conv.connection_id)
            if not conn_obj:
                # Fallback to first available connection
                conns = repository.list_connections()
                if conns:
                    conn_obj = conns[0]
                else:
                    self._send_json(400, {"error": "No database connection available"})
                    return

            # Start SSE Stream Response
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self._send_cors_headers()
            self.end_headers()

            async def run_pipeline():
                async for chunk in orchestrator.process_question_stream(conv_id, question, conn_obj):
                    try:
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break

            asyncio.run(run_pipeline())
            return

        # POST /api/queries/run (User-edited SQL execution with validator)
        if path == "/api/queries/run":
            conn_id = body.get("connection_id")
            sql = body.get("sql", "").strip()
            
            conn_obj = repository.get_connection(conn_id) if conn_id else None
            if not conn_obj:
                conns = repository.list_connections()
                conn_obj = conns[0] if conns else None
                
            if not conn_obj:
                self._send_json(400, {"error": "Database connection not found"})
                return

            # Validate safety
            tables = repository.get_schema(conn_obj.id)
            allowed_tables = {t.table_name.lower() for t in tables}
            validator = SQLValidator(allowed_tables=allowed_tables)
            val_res = validator.validate(sql, dialect=conn_obj.dialect)
            
            if not val_res:
                self._send_json(400, {"error": val_res.error_message, "is_valid": False})
                return

            try:
                exec_res = TargetDatabaseManager.execute_query(conn_obj, val_res.sanitized_sql)
                chart_spec = viz_recommender.profile_and_recommend(exec_res.columns, exec_res.rows)
                explanation = query_explainer.explain_query(val_res.sanitized_sql)
                
                self._send_json(200, {
                    "is_valid": True,
                    "sanitized_sql": val_res.sanitized_sql,
                    "result": exec_res.to_dict(),
                    "chart_spec": chart_spec,
                    "explanation": explanation
                })
            except Exception as e:
                self._send_json(500, {"error": str(e), "is_valid": True})
            return

        # POST /api/messages/{id}/feedback
        if path.startswith("/api/messages/") and path.endswith("/feedback"):
            msg_id = path.split("/")[3]
            feedback = int(body.get("feedback", 0)) # 1 for thumbs up, -1 for thumbs down
            corrected_sql = body.get("corrected_sql")
            repository.update_message(msg_id, feedback=feedback, corrected_sql=corrected_sql)
            self._send_json(200, {"status": "feedback_saved", "message_id": msg_id, "feedback": feedback})
            return

        # POST /api/metrics
        if path == "/api/metrics":
            metric = Metric(
                id=generate_uuid(),
                connection_id=body.get("connection_id", ""),
                name=body.get("name", "Metric"),
                sql=body.get("sql", ""),
                schedule_cron=body.get("schedule_cron", "0 0 * * *")
            )
            repository.create_metric(metric)
            self._send_json(201, {"id": metric.id, "name": metric.name})
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_json()

        # PATCH /api/schema/columns/{id}
        if path.startswith("/api/schema/columns/"):
            col_id = path.split("/")[4]
            desc = body.get("description")
            is_sensitive = body.get("is_sensitive")
            repository.update_column(col_id, description=desc, is_sensitive=is_sensitive)
            self._send_json(200, {"status": "updated", "column_id": col_id})
            return

        self._send_json(404, {"error": "Endpoint not found"})


def run_server(host: str = "0.0.0.0", port: int = 8000):
    socketserver.TCPServer.allow_reuse_address = True
    server_address = (host, port)
    try:
        httpd = socketserver.ThreadingTCPServer(server_address, SchemaSenseAPIHandler)
    except OSError as e:
        if e.errno == 48:
            print(f"\n❌ Port {port} is already in use by another running process.")
            print(f"👉 To stop the old process and free port {port}, run in your terminal:")
            print(f"   kill -9 $(lsof -ti :{port})")
            print(f"\nOr start the API on an alternative port by passing PORT:")
            print(f"   PORT=8001 PYTHONPATH=backend python3 backend/run_api.py\n")
            return
        raise e

    print(f"SchemaSense API Server listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server(host=settings.HOST, port=settings.PORT)

