"use client";

import React, { useState } from "react";
import { FileSpreadsheet, FileJson, Mail } from "lucide-react";
import GmailExportModal from "./GmailExportModal";

interface ExportMenuProps {
  columns: string[];
  rows: any[];
  filename?: string;
  title?: string;
  sql?: string;
  insight?: string;
}

export default function ExportMenu({
  columns,
  rows,
  filename = "schemasense_export",
  title = "SchemaSense Analysis Report",
  sql = "",
  insight = "",
}: ExportMenuProps) {
  const [gmailOpen, setGmailOpen] = useState(false);

  const exportCSV = () => {
    if (!rows || rows.length === 0) return;
    const header = columns.join(",");
    const body = rows
      .map((r) =>
        columns
          .map((col) => {
            const val = r[col];
            if (val === null || val === undefined) return "";
            const str = String(val).replace(/"/g, '""');
            return `"${str}"`;
          })
          .join(",")
      )
      .join("\n");

    const blob = new Blob([`${header}\n${body}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${filename}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const exportJSON = () => {
    if (!rows || rows.length === 0) return;
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${filename}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <>
      <div className="inline-flex items-center rounded-xl border border-slate-200 bg-white p-0.5 shadow-2xs gap-0.5">
        <button
          type="button"
          onClick={exportCSV}
          disabled={!rows || rows.length === 0}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 rounded-lg transition disabled:opacity-40"
        >
          <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" /> CSV
        </button>

        <button
          type="button"
          onClick={exportJSON}
          disabled={!rows || rows.length === 0}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 rounded-lg transition disabled:opacity-40"
        >
          <FileJson className="w-3.5 h-3.5 text-indigo-600" /> JSON
        </button>

        <button
          type="button"
          onClick={() => setGmailOpen(true)}
          disabled={(!rows || rows.length === 0) && !sql && !insight}
          className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold text-rose-600 hover:bg-rose-50 rounded-lg transition disabled:opacity-40"
        >
          <Mail className="w-3.5 h-3.5" /> Gmail
        </button>
      </div>

      <GmailExportModal
        isOpen={gmailOpen}
        onClose={() => setGmailOpen(false)}
        title={title}
        sql={sql}
        insight={insight}
        columns={columns}
        rows={rows}
        onDownloadCsv={exportCSV}
      />
    </>
  );
}
