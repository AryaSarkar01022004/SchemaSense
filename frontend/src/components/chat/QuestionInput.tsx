import React, { useState } from "react";
import { Send, Sparkles } from "lucide-react";

interface QuestionInputProps {
  onSend: (question: string) => void;
  isLoading: boolean;
  suggestions?: string[];
}

const DEFAULT_PROMPTS = [
  "What is our total revenue by status?",
  "Show top 5 highest value orders",
  "Show total spending per customer",
  "Show all products with their price and stock",
];

export default function QuestionInput({ onSend, isLoading, suggestions }: QuestionInputProps) {
  const [input, setInput] = useState("");
  const activePrompts = suggestions && suggestions.length > 0 ? suggestions : DEFAULT_PROMPTS;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div className="w-full space-y-3">
      {/* Sample suggestion chips */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1 mr-1">
          <Sparkles className="w-3 h-3 text-indigo-500" /> Suggestions:
        </span>
        {activePrompts.map((p, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => onSend(p)}
            disabled={isLoading}
            className="text-[11px] px-2.5 py-1 bg-white hover:bg-indigo-50 text-slate-600 hover:text-indigo-600 border border-slate-200 hover:border-indigo-200 rounded-full shadow-2xs transition disabled:opacity-40"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Main input form */}
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question in plain English (e.g. 'Show total revenue by country')..."
          disabled={isLoading}
          className="w-full pl-4 pr-12 py-3.5 bg-white border border-slate-300 rounded-xl shadow-xs text-sm text-slate-900 placeholder-slate-400 focus:outline-hidden focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="absolute right-2 p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-sm transition disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

