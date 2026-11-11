import React, { useState } from "react";
import { Play, Copy, Check, Terminal, Shield } from "lucide-react";

interface SqlViewerProps {
  initialSql: string;
  onRunSql?: (editedSql: string) => void;
  isLoading?: boolean;
}

export default function SqlViewer({ initialSql, onRunSql, isLoading }: SqlViewerProps) {
  const [sql, setSql] = useState(initialSql);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900 text-slate-100 shadow-md overflow-hidden my-3">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800/80 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <span className="text-xs font-mono font-medium text-slate-300">Generated SQL</span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Shield className="w-3 h-3" /> Validated Read-Only
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>

          {onRunSql && (
            <button
              onClick={() => onRunSql(sql)}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded transition disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {isLoading ? "Running..." : "Run SQL"}
            </button>
          )}
        </div>
      </div>

      <textarea
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        className="w-full p-4 font-mono text-sm bg-transparent text-emerald-300 border-none outline-hidden resize-y min-h-[90px] focus:ring-0 selection:bg-indigo-600"
        spellCheck={false}
      />
    </div>
  );
}

