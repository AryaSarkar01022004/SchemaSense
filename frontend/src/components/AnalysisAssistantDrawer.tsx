"use client";

import React, { useState, useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Bot,
  Sparkles,
  X,
  Send,
  Loader2,
  PlayCircle,
  Trash2,
  Minimize2,
  Maximize2,
  Database,
} from "lucide-react";
import { fetchConnections, fetchLLMSettings, sendAssistantChat } from "@/lib/api";

interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  suggested_questions?: string[];
  model_label?: string;
}

declare global {
  interface Window {
    __schemasenseContext?: {
      connectionId?: string;
      connectionName?: string;
      activeSql?: string;
      activeColumns?: string[];
      sampleRows?: any[];
    };
  }
}

const STARTER_PROMPTS = [
  "Suggest 4 key analyses for this dataset",
  "Explain the tables, columns, and relationships",
  "What KPIs and charts should I look at first?",
  "Help me interpret my latest query results",
];

export default function AnalysisAssistantDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [contextInfo, setContextInfo] = useState<{
    connectionId?: string;
    connectionName?: string;
    activeSql?: string;
    activeColumns?: string[];
    sampleRows?: any[];
  }>({});
  const [llmBadge, setLlmBadge] = useState<string>("Gemini");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const router = useRouter();

  const syncContext = async () => {
    if (typeof window !== "undefined" && window.__schemasenseContext?.connectionId) {
      setContextInfo({ ...window.__schemasenseContext });
    } else {
      try {
        const conns = await fetchConnections();
        if (conns && conns.length > 0) {
          setContextInfo((prev) =>
            prev.connectionId
              ? prev
              : { connectionId: conns[0].id, connectionName: conns[0].name }
          );
        }
      } catch {
        // Ignore silent fetch error
      }
    }

    try {
      const cfg = await fetchLLMSettings();
      if (cfg?.provider === "gemini") {
        setLlmBadge(`Gemini · ${cfg.model || "flash-lite"}`);
      } else if (cfg?.provider === "lmstudio") {
        setLlmBadge(`LM Studio${cfg.model ? ` · ${cfg.model}` : ""}`);
      } else if (cfg?.provider === "openai") {
        setLlmBadge(`OpenAI · ${cfg.model || "gpt-4o-mini"}`);
      } else {
        setLlmBadge("Offline Assistant");
      }
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    syncContext();

    const onContextUpdated = () => {
      if (window.__schemasenseContext) {
        setContextInfo({ ...window.__schemasenseContext });
      }
    };
    const onOpenAssistant = () => {
      setIsOpen(true);
      syncContext();
    };

    window.addEventListener("schemasense:context-updated", onContextUpdated);
    window.addEventListener("schemasense:open-assistant", onOpenAssistant);
    return () => {
      window.removeEventListener("schemasense:context-updated", onContextUpdated);
      window.removeEventListener("schemasense:open-assistant", onOpenAssistant);
    };
  }, [pathname]);

  useEffect(() => {
    if (isOpen) {
      syncContext();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (promptText?: string) => {
    const text = (promptText ?? input).trim();
    if (!text || loading) return;

    const userMsg: AssistantMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
    };

    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    if (!promptText) setInput("");
    setLoading(true);

    try {
      const liveCtx = (typeof window !== "undefined" && window.__schemasenseContext) || contextInfo;
      const res = await sendAssistantChat({
        messages: nextHistory.map((m) => ({ role: m.role, content: m.content })),
        connection_id: liveCtx.connectionId || contextInfo.connectionId,
        active_sql: liveCtx.activeSql,
        active_columns: liveCtx.activeColumns,
        sample_rows: liveCtx.sampleRows,
      });

      const assistantMsg: AssistantMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: res.reply || "No response received.",
        suggested_questions: res.suggested_questions || [],
        model_label: res.model ? `${res.provider} · ${res.model}` : res.provider,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: `Could not reach Analysis Assistant: ${err?.message || err}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleRunSuggestedQuestion = (question: string) => {
    const connId =
      (typeof window !== "undefined" && window.__schemasenseContext?.connectionId) ||
      contextInfo.connectionId ||
      "";

    if (pathname === "/chat") {
      window.dispatchEvent(
        new CustomEvent("schemasense:run-question", { detail: { question } })
      );
    } else {
      const query = new URLSearchParams();
      if (connId) query.set("connectionId", connId);
      query.set("ask", question);
      router.push(`/chat?${query.toString()}`);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end">
      {/* Expanded Chat Drawer */}
      {isOpen && (
        <div
          className={`mb-3 bg-white border border-slate-200 rounded-2xl shadow-2xl flex flex-col overflow-hidden transition-all ${
            isExpanded ? "w-[540px] h-[660px]" : "w-[400px] h-[540px]"
          } max-w-[calc(100vw-2rem)] max-h-[82vh]`}
        >
          {/* Header */}
          <div className="px-4 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 text-white flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="p-1.5 bg-white/15 rounded-lg">
                <Bot className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="font-bold text-xs tracking-wide flex items-center gap-1.5">
                  Analysis Assistant
                  <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-white/20 rounded">
                    {llmBadge}
                  </span>
                </div>
                <div className="text-[10px] text-indigo-100 truncate flex items-center gap-1 mt-0.5">
                  <Database className="w-2.5 h-2.5 shrink-0" />
                  <span>{contextInfo.connectionName || "Ready to help"}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={() => setMessages([])}
                  title="Clear assistant conversation"
                  className="p-1.5 hover:bg-white/15 rounded-lg transition"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setIsExpanded((v) => !v)}
                title={isExpanded ? "Compact view" : "Expand view"}
                className="p-1.5 hover:bg-white/15 rounded-lg transition"
              >
                {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Close assistant"
                className="p-1.5 hover:bg-white/15 rounded-lg transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50 text-xs">
            {messages.length === 0 ? (
              <div className="space-y-4 py-2">
                <div className="bg-white border border-slate-200 rounded-xl p-3.5 space-y-1.5 shadow-2xs">
                  <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                    How can I help with your analysis?
                  </div>
                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    I can inspect your connected database or uploaded CSV/XLS schema, suggest metrics
                    to explore, interpret query results, or help refine SQL queries.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1">
                    Quick Starters
                  </div>
                  {STARTER_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSend(prompt)}
                      className="w-full text-left px-3 py-2 bg-white hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 rounded-xl text-[11px] font-medium text-slate-700 hover:text-indigo-700 transition shadow-2xs"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 leading-relaxed whitespace-pre-wrap shadow-2xs ${
                      m.role === "user"
                        ? "bg-indigo-600 text-white"
                        : "bg-white border border-slate-200 text-slate-700"
                    }`}
                  >
                    {m.content}
                  </div>

                  {/* Clickable SQL Explorer query suggestions */}
                  {m.role === "assistant" &&
                    m.suggested_questions &&
                    m.suggested_questions.length > 0 && (
                      <div className="mt-2 space-y-1 w-full max-w-[92%]">
                        <div className="text-[10px] font-semibold text-slate-400 px-1">
                          Click to run in SQL Explorer:
                        </div>
                        {m.suggested_questions.map((q, qIdx) => (
                          <button
                            key={qIdx}
                            type="button"
                            onClick={() => handleRunSuggestedQuestion(q)}
                            className="w-full flex items-center justify-between gap-2 text-left px-3 py-1.5 bg-indigo-50/80 hover:bg-indigo-100 text-indigo-700 border border-indigo-200/80 rounded-lg text-[11px] font-medium transition"
                          >
                            <span className="truncate">{q}</span>
                            <PlayCircle className="w-3.5 h-3.5 shrink-0 text-indigo-600" />
                          </button>
                        ))}
                      </div>
                    )}
                </div>
              ))
            )}

            {loading && (
              <div className="flex items-center gap-2 text-indigo-600 px-2 py-1 text-[11px]">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Thinking about your dataset...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="p-3 bg-white border-t border-slate-200 flex items-center gap-2 shrink-0"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask for analysis ideas, SQL help, or insights..."
              disabled={loading}
              className="flex-1 px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-hidden focus:border-indigo-500 focus:bg-white transition"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-xs transition disabled:opacity-40"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      )}

      {/* Floating Launcher Pill */}
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-center gap-2 px-4 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full shadow-lg hover:shadow-xl transition-all text-xs font-bold"
      >
        <Sparkles className="w-4 h-4" />
        <span>{isOpen ? "Hide Assistant" : "Analysis Assistant"}</span>
      </button>
    </div>
  );
}

