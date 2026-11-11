import React from "react";
import { User, Sparkles, ThumbsUp, ThumbsDown, Loader2, AlertTriangle, Lightbulb } from "lucide-react";
import SqlViewer from "./SqlViewer";
import AssumptionChips from "./AssumptionChips";
import DataGrid from "../results/DataGrid";
import ChartPanel from "../results/ChartPanel";
import { submitFeedback } from "@/lib/api";

export interface ChatMessage {
  id: string;
  clientKey?: string;
  role: "user" | "assistant";
  question?: string;
  generated_sql?: string;
  validated_sql?: string;
  assumptions?: string[];
  explanation?: string;
  chart_spec?: any;
  result?: {
    columns: string[];
    rows: any[];
    row_count: number;
    exec_ms: number;
    truncated: boolean;
  };
  error?: string;
  status?: string;
  feedback?: number;
}

interface MessageListProps {
  messages: ChatMessage[];
  currentStage?: { stage: string; message: string } | null;
  onRunEditedSql?: (sql: string, messageId: string) => void;
}

export default function MessageList({ messages, currentStage, onRunEditedSql }: MessageListProps) {
  const handleFeedback = async (msgId: string, val: number) => {
    try {
      await submitFeedback(msgId, val);
      // Feedback saved
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    }
  };

  return (
    <div className="space-y-6 pb-6">
      {messages.map((msg, idx) => (
        <div key={msg.clientKey || msg.id} className="flex gap-3 text-sm">
          {/* Avatar */}
          <div className="shrink-0">
            {msg.role === "user" ? (
              <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center font-bold">
                <User className="w-4 h-4" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                <Sparkles className="w-4 h-4" />
              </div>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {msg.role === "user" ? (
              <div className="font-semibold text-slate-800 pt-1">
                {msg.question}
              </div>
            ) : (
              <div className="space-y-3">
                {msg.question && (idx === 0 || messages[idx - 1]?.role !== "user") && (
                  <div className="font-semibold text-slate-800 pt-1 pb-1 border-b border-slate-100">
                    {msg.question}
                  </div>
                )}
                {/* Assumptions */}
                {msg.assumptions && msg.assumptions.length > 0 && (
                  <AssumptionChips assumptions={msg.assumptions} />
                )}

                {/* Error Banner */}
                {msg.error && (
                  <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold text-xs">Query Error</div>
                      <div className="text-xs">{msg.error}</div>
                    </div>
                  </div>
                )}

                {/* SQL Viewer */}
                {(msg.validated_sql || msg.generated_sql) && (
                  <SqlViewer
                    initialSql={msg.validated_sql || msg.generated_sql || ""}
                    onRunSql={(editedSql) => onRunEditedSql?.(editedSql, msg.id)}
                  />
                )}

                {/* Visual Chart */}
                {msg.chart_spec && (
                  <ChartPanel spec={msg.chart_spec} rows={msg.result?.rows || []} />
                )}

                {/* Results Grid */}
                {msg.result && (
                  <DataGrid
                    columns={msg.result.columns}
                    rows={msg.result.rows}
                    rowCount={msg.result.row_count}
                    execMs={msg.result.exec_ms}
                    truncated={msg.result.truncated}
                    title={msg.chart_spec?.title || msg.question || "SchemaSense Query Results"}
                    sql={msg.validated_sql || msg.generated_sql || ""}
                    insight={msg.explanation || ""}
                  />
                )}

                {/* Plain-Language Explanation */}
                {msg.explanation && (
                  <div className="bg-gradient-to-r from-amber-50/70 to-slate-50 border border-amber-200/60 rounded-xl p-3.5 flex items-start gap-2.5 text-xs text-slate-700 animate-fade-in-up">
                    <Lightbulb className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <div className="leading-relaxed">
                      <span className="font-semibold text-slate-900">Insight: </span>
                      {msg.explanation}
                    </div>
                  </div>
                )}

                {/* Feedback Buttons */}
                <div className="flex items-center gap-2 pt-1 text-slate-400">
                  <span className="text-[11px]">Was this helpful?</span>
                  <button
                    onClick={() => handleFeedback(msg.id, 1)}
                    className="p-1 hover:text-emerald-600 hover:bg-emerald-50 rounded transition"
                    title="Good query (thumbs up feeds few-shot prompt)"
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleFeedback(msg.id, -1)}
                    className="p-1 hover:text-rose-600 hover:bg-rose-50 rounded transition"
                    title="Bad query"
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Real-time Streaming Pipeline Stepper */}
      {currentStage && (
        <div className="p-4 bg-white border border-indigo-100 rounded-2xl shadow-xs space-y-2.5 animate-fade-in-up">
          <div className="flex items-center gap-2.5 text-xs text-indigo-700 font-semibold">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-600 shrink-0" />
            <span>{currentStage.message}</span>
          </div>
          <div className="grid grid-cols-6 gap-1.5">
            {[
              { id: "resolving_context", label: "Context" },
              { id: "retrieving_schema", label: "Schema" },
              { id: "generating_sql", label: "SQL AI" },
              { id: "validating_safety", label: "Safety" },
              { id: "executing_query", label: "Execute" },
              { id: "synthesizing_insights", label: "Visualize" },
            ].map((step, i) => {
              const order = [
                "init",
                "resolving_context",
                "retrieving_schema",
                "building_prompt",
                "generating_sql",
                "validating_safety",
                "repair_loop",
                "executing_query",
                "synthesizing_insights",
              ];
              const currIdx = order.indexOf(currentStage.stage);
              const stepIdx = order.indexOf(step.id);
              const isActive = currentStage.stage === step.id || (step.id === "validating_safety" && currentStage.stage === "repair_loop");
              const isDone = currIdx > stepIdx && stepIdx !== -1;
              return (
                <div key={step.id} className="space-y-1">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      isDone
                        ? "bg-emerald-500"
                        : isActive
                        ? "bg-indigo-600 animate-pulse"
                        : "bg-slate-100"
                    }`}
                  />
                  <div
                    className={`text-[10px] font-medium truncate text-center ${
                      isDone ? "text-emerald-700" : isActive ? "text-indigo-700 font-bold" : "text-slate-400"
                    }`}
                  >
                    {i + 1}. {step.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

