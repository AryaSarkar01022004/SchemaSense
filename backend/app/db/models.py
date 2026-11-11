"""
App Database Data Models (Section 5.1).
Defines dataclasses and serialization for all entities:
Users, Workspaces, Connections, SchemaTables, SchemaColumns,
Conversations, Messages, SavedQueries, Metrics, MetricPoints,
Insights, EvalCases, and EvalRuns.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


def generate_uuid() -> str:
    return str(uuid.uuid4())


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class User:
    id: str = field(default_factory=generate_uuid)
    email: str = ""
    created_at: str = field(default_factory=now_utc)


@dataclass
class Workspace:
    id: str = field(default_factory=generate_uuid)
    name: str = ""
    owner_id: str = ""
    created_at: str = field(default_factory=now_utc)


@dataclass
class Connection:
    id: str = field(default_factory=generate_uuid)
    workspace_id: str = ""
    name: str = ""
    dialect: str = "postgres" # 'postgres' or 'mysql' or 'sqlite' (for fixtures)
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password_enc: bytes = b""
    dek_enc: bytes = b""
    ssl_mode: str = "prefer"
    last_synced_at: Optional[str] = None
    status: str = "pending" # pending, ready, error, syncing


@dataclass
class SchemaColumn:
    id: str = field(default_factory=generate_uuid)
    table_id: str = ""
    column_name: str = ""
    data_type: str = ""
    is_pk: bool = False
    is_nullable: bool = True
    fk_table_id: Optional[str] = None
    fk_table_name: Optional[str] = None
    fk_column: Optional[str] = None
    sample_values: List[Any] = field(default_factory=list)
    distinct_estimate: int = 0
    description: str = ""
    is_sensitive: bool = False
    embedding: Optional[List[float]] = None # vector(1536)


@dataclass
class SchemaTable:
    id: str = field(default_factory=generate_uuid)
    connection_id: str = ""
    schema_name: str = "public"
    table_name: str = ""
    description: str = ""
    row_estimate: int = 0
    embedding: Optional[List[float]] = None # vector(1536)
    columns: List[SchemaColumn] = field(default_factory=list)


@dataclass
class Conversation:
    id: str = field(default_factory=generate_uuid)
    workspace_id: str = ""
    connection_id: str = ""
    user_id: str = ""
    title: str = "New Conversation"
    created_at: str = field(default_factory=now_utc)


@dataclass
class Message:
    id: str = field(default_factory=generate_uuid)
    conversation_id: str = ""
    role: str = "user" # user, assistant, system
    question: Optional[str] = None
    generated_sql: Optional[str] = None
    validated_sql: Optional[str] = None
    status: str = "pending" # pending, running, completed, error
    error: Optional[str] = None
    row_count: int = 0
    exec_ms: int = 0
    chart_spec: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)
    feedback: Optional[int] = None # 1 (thumbs up) or -1 (thumbs down)
    corrected_sql: Optional[str] = None
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    created_at: str = field(default_factory=now_utc)


@dataclass
class SavedQuery:
    id: str = field(default_factory=generate_uuid)
    workspace_id: str = ""
    name: str = ""
    sql: str = ""
    chart_spec: Optional[Dict[str, Any]] = None
    created_by: str = ""
    created_at: str = field(default_factory=now_utc)


@dataclass
class Metric:
    id: str = field(default_factory=generate_uuid)
    connection_id: str = ""
    name: str = ""
    sql: str = ""
    schedule_cron: str = "0 0 * * *"
    enabled: bool = True
    created_at: str = field(default_factory=now_utc)


@dataclass
class MetricPoint:
    metric_id: str = ""
    ts: str = field(default_factory=now_utc)
    value: float = 0.0


@dataclass
class Insight:
    id: str = field(default_factory=generate_uuid)
    metric_id: str = ""
    detected_at: str = field(default_factory=now_utc)
    severity: str = "medium" # low, medium, high, critical
    summary: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalCase:
    id: str = field(default_factory=generate_uuid)
    suite: str = "default"
    question: str = ""
    gold_sql: str = ""
    schema_fixture: str = ""
    category: str = "basic" # multi_join, window_function, date_math, aggregate, adversarial


@dataclass
class EvalRun:
    id: str = field(default_factory=generate_uuid)
    git_sha: str = "HEAD"
    accuracy: float = 0.0
    pass_count: int = 0
    total_count: int = 0
    median_latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_utc)

