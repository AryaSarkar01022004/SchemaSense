"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { MessageSquare, Plus, Database, Sparkles, UploadCloud, FileSpreadsheet, Cpu, Bot, BarChart3 } from "lucide-react";
import MessageList, { ChatMessage } from "@/components/chat/MessageList";
import QuestionInput from "@/components/chat/QuestionInput";
import FileUploadPanel from "@/components/FileUploadPanel";
import {
  fetchConnections,
  fetchConversations,
  createConversation,
  fetchMessages,
  runQuery,
  fetchSchema,
  fetchLLMSettings,
} from "@/lib/api";
import { streamAskQuestion } from "@/lib/sse";

export default function ChatPage() {
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnId, setSelectedConnId] = useState<string>("");
  const [conversations, setConversations] = useState<any[]>([]);
  const [activeConvId, setActiveConvId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [currentStage, setCurrentStage] = useState<{ stage: string; message: string } | null>(null);
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [activeTables, setActiveTables] = useState<any[]>([]);
  const [llmInfo, setLlmInfo] = useState<{ provider: string; model?: string } | null>(null);

  const loadMessages = async (convId: string) => {
    try {
      const msgs = await fetchMessages(convId);
      setMessages(msgs || []);
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  };

  const loadSchemaForConn = async (connId: string) => {
    if (!connId) return;
    try {
      const res = await fetchSchema(connId);
      setActiveTables(res.tables || []);
    } catch (err) {
      console.error("Failed to fetch schema:", err);
    }
  };

  const ensureConversationForConn = async (connId: string, existingConvs: any[]) => {
    const matching = existingConvs.filter((c) => c.connection_id === connId);
    if (matching.length > 0) {
      setActiveConvId(matching[0].id);
      await loadMessages(matching[0].id);
    } else {
      const targetConn = connections.find((c) => c.id === connId);
      const title = targetConn ? `${targetConn.name}` : "New Exploration";
      const newConv = await createConversation(connId, title);
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setMessages([]);
    }
  };

  const pendingAskRef = useRef<string | null>(null);
  const askHandlerRef = useRef<(q: string) => void>(() => {});

  // Load connections, conversations, URL connectionId & ask params, and LLM settings
  useEffect(() => {
    async function init() {
      try {
        const params = new URLSearchParams(window.location.search);
        const paramConnId = params.get("connectionId");
        const paramAsk = params.get("ask");
        if (paramAsk) {
          pendingAskRef.current = paramAsk;
        }

        const [conns, convs, llmCfg] = await Promise.all([
          fetchConnections(),
          fetchConversations(),
          fetchLLMSettings().catch(() => null),
        ]);

        const connList = conns || [];
        const convList = convs || [];
        setConnections(connList);
        setConversations(convList);
        if (llmCfg) {
          setLlmInfo({ provider: llmCfg.provider, model: llmCfg.model });
        }

        if (connList.length > 0) {
          const initialConnId =
            paramConnId && connList.some((c: any) => c.id === paramConnId)
              ? paramConnId
              : connList[0].id;
          setSelectedConnId(initialConnId);
          loadSchemaForConn(initialConnId);

          const matching = convList.filter((c: any) => c.connection_id === initialConnId);
          if (matching.length > 0 && !paramAsk) {
            setActiveConvId(matching[0].id);
            loadMessages(matching[0].id);
          } else {
            const target = connList.find((c: any) => c.id === initialConnId);
            const newConv = await createConversation(initialConnId, target?.name || "First Exploration");
            setConversations([newConv, ...convList]);
            setActiveConvId(newConv.id);
          }
        }
      } catch (err) {
        console.error("Initialization error:", err);
      }
    }
    init();
  }, []);

  const handleSelectConnection = async (newConnId: string) => {
    setSelectedConnId(newConnId);
    loadSchemaForConn(newConnId);
    await ensureConversationForConn(newConnId, conversations);
  };

  const handleSelectConv = (convId: string) => {
    setActiveConvId(convId);
    loadMessages(convId);
    const conv = conversations.find((c) => c.id === convId);
    if (conv && conv.connection_id && conv.connection_id !== selectedConnId) {
      setSelectedConnId(conv.connection_id);
      loadSchemaForConn(conv.connection_id);
    }
  };

  const handleNewConversation = async () => {
    if (!selectedConnId) return;
    try {
      const target = connections.find((c) => c.id === selectedConnId);
      const newConv = await createConversation(
        selectedConnId,
        `${target?.name || "Chat"} · ${new Date().toLocaleTimeString()}`
      );
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  };

  const handleFileUploaded = async (uploadRes: any) => {
    setShowUploadModal(false);
    const updatedConns = await fetchConnections();
    setConnections(updatedConns || []);
    if (uploadRes?.id) {
      setSelectedConnId(uploadRes.id);
      loadSchemaForConn(uploadRes.id);
      const newConv = await createConversation(uploadRes.id, uploadRes.name || "Spreadsheet Analysis");
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(newConv.id);
      setMessages([]);
    }
  };

  const handleAskQuestion = async (question: string) => {
    if (!activeConvId || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      question,
    };

    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      clientKey: assistantMsgId,
      role: "assistant",
      status: "running",
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setLoading(true);
    setCurrentStage({ stage: "init", message: "Starting pipeline..." });

    try {
      await streamAskQuestion(activeConvId, question, {
        onStatus: (stage, message) => {
          setCurrentStage({ stage, message });
        },
        onSql: (sql, assumptions, tablesUsed) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, validated_sql: sql, generated_sql: sql, assumptions }
                : m
            )
          );
        },
        onRows: (data) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    result: {
                      columns: data.columns,
                      rows: data.rows,
                      row_count: data.row_count,
                      exec_ms: data.exec_ms,
                      truncated: data.truncated,
                    },
                  }
                : m
            )
          );
        },
        onChart: (spec) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, chart_spec: spec } : m))
          );
        },
        onExplanation: (explanation) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, explanation } : m))
          );
        },
        onError: (error, lastSql) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, error, generated_sql: lastSql || m.generated_sql, status: "error" }
                : m
            )
          );
        },
        onDone: (data) => {
          setCurrentStage(null);
          setLoading(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, id: data.message_id, status: "completed" } : m
            )
          );
        },
      });
    } catch (err: any) {
      console.error("Stream ask error:", err);
      setCurrentStage(null);
      setLoading(false);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId ? { ...m, error: String(err), status: "error" } : m
        )
      );
    }
  };

  const handleRunEditedSql = async (sql: string, messageId: string) => {
    try {
      setLoading(true);
      setCurrentStage({ stage: "manual_run", message: "Validating & executing edited SQL..." });
      const res = await runQuery(selectedConnId, sql);
      if (res.error) {
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, error: res.error } : m))
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  validated_sql: res.sanitized_sql,
                  result: res.result,
                  chart_spec: res.chart_spec,
                  explanation: res.explanation,
                  error: undefined,
                }
              : m
          )
        );
      }
    } catch (err: any) {
      console.error("Run edited SQL error:", err);
    } finally {
      setLoading(false);
      setCurrentStage(null);
    }
  };

  const activeConn = connections.find((c) => c.id === selectedConnId);

  // Sync live context with Analysis Assistant Chat Window
  useEffect(() => {
    askHandlerRef.current = handleAskQuestion;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const latestWithSql = [...messages].reverse().find((m) => m.validated_sql || m.generated_sql);
    window.__schemasenseContext = {
      connectionId: selectedConnId || undefined,
      connectionName: activeConn?.name || undefined,
      activeSql: latestWithSql?.validated_sql || latestWithSql?.generated_sql || undefined,
      activeColumns: latestWithSql?.result?.columns || undefined,
      sampleRows: latestWithSql?.result?.rows?.slice(0, 5) || undefined,
    };
    window.dispatchEvent(new CustomEvent("schemasense:context-updated"));
  }, [selectedConnId, activeConn?.name, messages]);

  // Execute pending ?ask= question or questions sent from Analysis Assistant
  useEffect(() => {
    if (activeConvId && pendingAskRef.current) {
      const q = pendingAskRef.current;
      pendingAskRef.current = null;
      askHandlerRef.current(q);
    }
  }, [activeConvId]);

  useEffect(() => {
    const onRunQuestion = (e: Event) => {
      const custom = e as CustomEvent<{ question?: string }>;
      if (custom.detail?.question) {
        askHandlerRef.current(custom.detail.question);
      }
    };
    window.addEventListener("schemasense:run-question", onRunQuestion);
    return () => window.removeEventListener("schemasense:run-question", onRunQuestion);
  }, []);

  const isUploadedFile = activeConn?.host === "uploaded-file";
  const firstTableName = activeTables[0]?.table_name;
  const customSuggestions =
    isUploadedFile && firstTableName
      ? [
          `Show all rows from ${firstTableName}`,
          `How many rows are in ${firstTableName}?`,
          `Show top 10 rows in ${firstTableName}`,
          `Summarize totals in ${firstTableName}`,
        ]
      : undefined;

  return (
    <div className="flex h-[calc(100vh-7rem)] bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      {/* Sidebar - Data Source & Conversations */}
      <div className="w-72 border-r border-slate-200 bg-slate-50/50 flex flex-col p-4">
        {/* Data source selector */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Data Source
            </label>
            <button
              type="button"
              onClick={() => setShowUploadModal(true)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 hover:text-emerald-800"
            >
              <UploadCloud className="w-3 h-3" /> Upload CSV/XLS
            </button>
          </div>
          <div className="flex items-center gap-2 p-2 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-800">
            {isUploadedFile ? (
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
            ) : (
              <Database className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
            )}
            <select
              value={selectedConnId}
              onChange={(e) => handleSelectConnection(e.target.value)}
              className="bg-transparent border-none outline-hidden w-full cursor-pointer truncate"
            >
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.host === "uploaded-file" ? "File" : c.dialect})
                </option>
              ))}
            </select>
          </div>
          {activeTables.length > 0 && (
            <div className="mt-1.5 text-[10px] text-slate-500 truncate px-0.5">
              Tables: {activeTables.map((t) => t.table_name).join(", ")}
            </div>
          )}
        </div>

        <div className="space-y-2 mb-4">
          <button
            onClick={handleNewConversation}
            className="flex items-center justify-center gap-2 w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-xs transition"
          >
            <Plus className="w-4 h-4" /> New Question Thread
          </button>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new CustomEvent("schemasense:open-assistant"))}
            className="flex items-center justify-center gap-2 w-full py-1.5 px-3 bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-semibold shadow-2xs transition"
          >
            <Bot className="w-3.5 h-3.5" /> Open Analysis Assistant
          </button>
          <Link
            href={selectedConnId ? `/visualizer?connectionId=${encodeURIComponent(selectedConnId)}` : "/visualizer"}
            className="flex items-center justify-center gap-2 w-full py-1.5 px-3 bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-xl text-xs font-semibold shadow-2xs transition"
          >
            <BarChart3 className="w-3.5 h-3.5" /> Open Data Visualizer
          </Link>
        </div>

        <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
          Conversations
        </div>

        <div className="flex-1 overflow-y-auto space-y-1">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => handleSelectConv(c.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium truncate transition ${
                activeConvId === c.id
                  ? "bg-white text-indigo-700 shadow-2xs border border-slate-200"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <div className="flex items-center gap-2">
                <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-70" />
                <span className="truncate">{c.title || "Conversation"}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Active LLM status footer */}
        <Link
          href="/settings"
          className="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between text-[11px] text-slate-600 hover:text-indigo-600 transition"
        >
          <span className="flex items-center gap-1.5 truncate">
            <Cpu className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
            <span className="truncate">
              {llmInfo?.provider === "lmstudio"
                ? `LM Studio${llmInfo.model ? ` · ${llmInfo.model}` : ""}`
                : llmInfo?.provider === "openai"
                ? `OpenAI · ${llmInfo.model || "gpt-4o-mini"}`
                : llmInfo?.provider === "gemini"
                ? `Gemini · ${llmInfo.model || "flash"}`
                : "Offline Engine"}
            </span>
          </span>
          <span className="text-[10px] font-semibold text-indigo-600 shrink-0 ml-1">Switch</span>
        </Link>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full bg-slate-50/20">
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto space-y-5">
              <div className="p-4 bg-indigo-50 text-indigo-600 rounded-2xl shadow-2xs">
                <Sparkles className="w-8 h-8" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-slate-800">Natural Language Explorer</h2>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Ask questions about <strong>{activeConn?.name || "your data"}</strong> in plain English,
                  or drop a <strong>CSV, XLS, or XLSX</strong> file below for instant SQL and visual analysis.
                </p>
              </div>
              <div className="w-full text-left">
                <FileUploadPanel compact onSuccess={handleFileUploaded} />
              </div>
            </div>
          ) : (
            <MessageList
              messages={messages}
              currentStage={currentStage}
              onRunEditedSql={handleRunEditedSql}
            />
          )}
        </div>

        {/* Input area */}
        <div className="p-4 bg-white border-t border-slate-200">
          <QuestionInput
            onSend={handleAskQuestion}
            isLoading={loading}
            suggestions={customSuggestions}
          />
        </div>
      </div>

      {/* Upload CSV / Excel Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-base text-slate-900">Analyze CSV / Excel (.xls, .xlsx)</h3>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <FileUploadPanel
              onCancel={() => setShowUploadModal(false)}
              onSuccess={handleFileUploaded}
            />
          </div>
        </div>
      )}
    </div>
  );
}
