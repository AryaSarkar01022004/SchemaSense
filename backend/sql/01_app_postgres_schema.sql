-- =====================================================================
-- SchemaSense App Database Schema (Control Plane)
-- Matching Section 5.1 & Section 5.2 of SchemaSense Technical Design
-- =====================================================================

-- 1. Enable pgvector extension for semantic table & column search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Workspaces table
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Target Database Connections table
-- Implements envelope encryption fields (password_enc, dek_enc)
CREATE TABLE IF NOT EXISTS connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    dialect TEXT NOT NULL CHECK (dialect IN ('postgres', 'mysql', 'sqlite')),
    host TEXT NOT NULL,
    port INT NOT NULL DEFAULT 5432,
    database TEXT NOT NULL,
    username TEXT NOT NULL,
    password_enc BYTEA NOT NULL, -- Ciphertext encrypted with DEK
    dek_enc BYTEA NOT NULL,      -- DEK encrypted with Master Key (KEK)
    ssl_mode TEXT NOT NULL DEFAULT 'prefer',
    last_synced_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending'
);

-- 5. Introspected Tables Metadata & Vector Embeddings
CREATE TABLE IF NOT EXISTS schema_tables (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    schema_name TEXT NOT NULL DEFAULT 'public',
    table_name TEXT NOT NULL,
    description TEXT,
    row_estimate BIGINT DEFAULT 0,
    embedding VECTOR(1536), -- Dense vector for cosine similarity retrieval
    UNIQUE (connection_id, schema_name, table_name)
);

-- 6. Introspected Columns Metadata & Vector Embeddings
CREATE TABLE IF NOT EXISTS schema_columns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_id UUID NOT NULL REFERENCES schema_tables(id) ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    is_pk BOOLEAN NOT NULL DEFAULT FALSE,
    is_nullable BOOLEAN NOT NULL DEFAULT TRUE,
    fk_table_id UUID REFERENCES schema_tables(id) ON DELETE SET NULL,
    fk_table_name TEXT,
    fk_column TEXT,
    sample_values JSONB DEFAULT '[]'::jsonb, -- Low-cardinality non-PII values
    distinct_estimate BIGINT DEFAULT 0,
    description TEXT,
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE, -- PII / Sensitive data lock
    embedding VECTOR(1536)
);

-- 7. Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES connections(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Messages & Query History
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    question TEXT,
    generated_sql TEXT,
    validated_sql TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    error TEXT,
    row_count INT DEFAULT 0,
    exec_ms INT DEFAULT 0,
    chart_spec JSONB,
    explanation TEXT,
    assumptions JSONB DEFAULT '[]'::jsonb,
    feedback SMALLINT, -- +1 (thumbs up feeds few-shot) or -1 (thumbs down)
    corrected_sql TEXT,
    llm_tokens_in INT DEFAULT 0,
    llm_tokens_out INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Saved Queries
CREATE TABLE IF NOT EXISTS saved_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sql TEXT NOT NULL,
    chart_spec JSONB,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Monitored Metrics
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sql TEXT NOT NULL,
    schedule_cron TEXT NOT NULL DEFAULT '0 0 * * *',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. Metric Points Time-Series
CREATE TABLE IF NOT EXISTS metric_points (
    metric_id UUID NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    value DOUBLE PRECISION NOT NULL
);

-- 12. Statistical Anomaly Insights
CREATE TABLE IF NOT EXISTS insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_id UUID NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    summary TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- 13. Evaluation Cases & CI Runs (Section 6)
CREATE TABLE IF NOT EXISTS eval_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    suite TEXT NOT NULL DEFAULT 'default',
    question TEXT NOT NULL,
    gold_sql TEXT NOT NULL,
    schema_fixture TEXT,
    category TEXT NOT NULL DEFAULT 'general'
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    git_sha TEXT NOT NULL DEFAULT 'HEAD',
    accuracy NUMERIC(5, 2) NOT NULL,
    pass_count INT NOT NULL DEFAULT 0,
    total_count INT NOT NULL DEFAULT 0,
    median_latency_ms NUMERIC(8, 2) NOT NULL DEFAULT 0.0,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================================
-- Performance & Vector Retrieval Indexes (Section 5.1)
-- =====================================================================

-- HNSW Vector Cosine Distance Indexes for sub-second retrieval
CREATE INDEX IF NOT EXISTS idx_schema_tables_embedding 
    ON schema_tables USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_schema_columns_embedding 
    ON schema_columns USING hnsw (embedding vector_cosine_ops);

-- B-Tree Index on messages for rapid thread retrieval
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created 
    ON messages (conversation_id, created_at DESC);

-- Metric time-series index
CREATE INDEX IF NOT EXISTS idx_metric_points_metric_ts 
    ON metric_points (metric_id, ts DESC);

-- =====================================================================
-- Seed Initial User & Workspace
-- =====================================================================
INSERT INTO users (id, email)
VALUES ('00000000-0000-0000-0000-000000000001', 'admin@schemasense.io')
ON CONFLICT (email) DO NOTHING;

INSERT INTO workspaces (id, name, owner_id)
VALUES ('00000000-0000-0000-0000-000000000002', 'Default Workspace', '00000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

