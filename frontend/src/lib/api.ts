/**
 * SchemaSense API Client (Section 5.11)
 */

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function fetchConnections() {
  const res = await fetch(`${BASE_URL}/api/connections`);
  return res.json();
}

export async function createConnection(data: {
  name: string;
  dialect: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password?: string;
  ssl_mode?: string;
}) {
  const res = await fetch(`${BASE_URL}/api/connections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function syncConnection(connId: string) {
  const res = await fetch(`${BASE_URL}/api/connections/${connId}/sync`, {
    method: "POST",
  });
  return res.json();
}

export async function fetchSchema(connId: string) {
  const res = await fetch(`${BASE_URL}/api/connections/${connId}/schema`);
  return res.json();
}

export async function updateColumn(columnId: string, data: { description?: string; is_sensitive?: boolean }) {
  const res = await fetch(`${BASE_URL}/api/schema/columns/${columnId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fetchConversations() {
  const res = await fetch(`${BASE_URL}/api/conversations`);
  return res.json();
}

export async function createConversation(connectionId: string, title?: string) {
  const res = await fetch(`${BASE_URL}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ connection_id: connectionId, title }),
  });
  return res.json();
}

export async function fetchMessages(conversationId: string) {
  const res = await fetch(`${BASE_URL}/api/conversations/${conversationId}/messages`);
  return res.json();
}

export async function runQuery(connectionId: string, sql: string) {
  const res = await fetch(`${BASE_URL}/api/queries/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ connection_id: connectionId, sql }),
  });
  return res.json();
}

export async function submitFeedback(messageId: string, feedback: number, correctedSql?: string) {
  const res = await fetch(`${BASE_URL}/api/messages/${messageId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback, corrected_sql: correctedSql }),
  });
  return res.json();
}

export async function fetchInsights() {
  const res = await fetch(`${BASE_URL}/api/insights`);
  return res.json();
}

export async function uploadFilesConnection(files: File[], name?: string) {
  const formData = new FormData();
  if (name && name.trim()) {
    formData.append("name", name.trim());
  }
  for (const file of files) {
    formData.append("files", file);
  }
  const res = await fetch(`${BASE_URL}/api/connections/upload`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "File upload failed");
  }
  return data;
}

export async function fetchLLMSettings() {
  const res = await fetch(`${BASE_URL}/api/settings/llm`);
  return res.json();
}

export async function saveLLMSettings(payload: {
  provider: string;
  model?: string;
  lmstudio_base_url?: string;
  lmstudio_api_key?: string;
  openai_api_key?: string;
  gemini_api_key?: string;
}) {
  const res = await fetch(`${BASE_URL}/api/settings/llm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function fetchLMStudioModels(baseUrl?: string) {
  const query = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : "";
  const res = await fetch(`${BASE_URL}/api/settings/llm/lmstudio/models${query}`);
  return res.json();
}

export async function fetchGeminiModels() {
  const res = await fetch(`${BASE_URL}/api/settings/llm/gemini/models`);
  return res.json();
}

export async function testLLMSettings(payload?: any) {
  const res = await fetch(`${BASE_URL}/api/settings/llm/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return res.json();
}

export async function sendAssistantChat(payload: {
  messages: { role: string; content: string }[];
  connection_id?: string;
  active_sql?: string;
  active_columns?: string[];
  sample_rows?: any[];
}) {
  const res = await fetch(`${BASE_URL}/api/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function runVisualizerQuery(payload: {
  connection_id: string;
  table_name: string;
  x_col: string;
  y_col?: string;
  aggregation: string;
  chart_type: string;
  limit?: number;
  sort_dir?: string;
}) {
  const res = await fetch(`${BASE_URL}/api/visualizer/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function discoverVisualizerCharts(connectionId: string, tableName?: string) {
  const res = await fetch(`${BASE_URL}/api/visualizer/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ connection_id: connectionId, table_name: tableName }),
  });
  return res.json();
}

export async function exportToEmail(payload: {
  to: string;
  subject: string;
  note?: string;
  insight?: string;
  sql?: string;
  columns?: string[];
  rows?: any[];
  attachment_filename?: string;
  send_direct?: boolean;
}) {
  const res = await fetch(`${BASE_URL}/api/export/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function fetchEmailSettings() {
  const res = await fetch(`${BASE_URL}/api/settings/email`);
  return res.json();
}

export async function saveEmailSettings(payload: {
  smtp_host?: string;
  smtp_port?: number;
  smtp_user?: string;
  smtp_password?: string;
}) {
  const res = await fetch(`${BASE_URL}/api/settings/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

