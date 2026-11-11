/**
 * Server-Sent Events (SSE) Client over Fetch POST.
 * Streams events: status, sql, rows, chart, explanation, error, done.
 */

export interface SSECallbacks {
  onStatus?: (stage: string, message: string) => void;
  onSql?: (sql: string, assumptions: string[], tablesUsed: string[]) => void;
  onRows?: (data: { columns: string[]; rows: any[]; row_count: number; exec_ms: number; truncated: boolean }) => void;
  onChart?: (spec: any) => void;
  onExplanation?: (explanation: string, needsClarification?: boolean) => void;
  onError?: (error: string, lastSql?: string) => void;
  onDone?: (data: { message_id: string; exec_ms?: number }) => void;
}

export async function streamAskQuestion(
  conversationId: string,
  question: string,
  callbacks: SSECallbacks,
  signal?: AbortSignal
) {
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
  const response = await fetch(`${baseUrl}/api/conversations/${conversationId}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    callbacks.onError?.(`HTTP ${response.status}: ${errorText}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.("ReadableStream not supported by browser.");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const chunk of parts) {
      if (!chunk.trim()) continue;
      const lines = chunk.split("\n");
      let eventType = "message";
      let dataStr = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.substring(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.substring(6).trim();
        }
      }

      if (!dataStr) continue;

      try {
        const parsed = JSON.parse(dataStr);
        switch (eventType) {
          case "status":
            callbacks.onStatus?.(parsed.stage, parsed.message);
            break;
          case "sql":
            callbacks.onSql?.(parsed.sql, parsed.assumptions || [], parsed.tables_used || []);
            break;
          case "rows":
            callbacks.onRows?.(parsed);
            break;
          case "chart":
            callbacks.onChart?.(parsed.spec);
            break;
          case "explanation":
            callbacks.onExplanation?.(parsed.explanation, parsed.needs_clarification);
            break;
          case "error":
            callbacks.onError?.(parsed.error, parsed.last_sql);
            break;
          case "done":
            callbacks.onDone?.(parsed);
            break;
        }
      } catch (err) {
        console.error("Error parsing SSE JSON payload:", err, dataStr);
      }
    }
  }
}

