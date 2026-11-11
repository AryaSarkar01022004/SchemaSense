"use client";

import React, { useState, useMemo } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, Search, ArrowUpDown } from "lucide-react";
import ExportMenu from "./ExportMenu";

interface DataGridProps {
  columns: string[];
  rows: any[];
  rowCount?: number;
  execMs?: number;
  truncated?: boolean;
  title?: string;
  sql?: string;
  insight?: string;
}

export default function DataGrid({
  columns,
  rows = [],
  rowCount = 0,
  execMs = 0,
  truncated = false,
  title,
  sql,
  insight,
}: DataGridProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [filterText, setFilterText] = useState("");
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const pageSize = 15;

  const processedRows = useMemo(() => {
    let list = rows;
    if (filterText.trim()) {
      const q = filterText.trim().toLowerCase();
      list = list.filter((r) =>
        columns.some((c) => String(r[c] ?? "").toLowerCase().includes(q))
      );
    }
    if (sortCol) {
      list = [...list].sort((a, b) => {
        const va = a[sortCol];
        const vb = b[sortCol];
        if (va === vb) return 0;
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        if (typeof va === "number" && typeof vb === "number") {
          return sortAsc ? va - vb : vb - va;
        }
        return sortAsc
          ? String(va).localeCompare(String(vb))
          : String(vb).localeCompare(String(va));
      });
    }
    return list;
  }, [rows, columns, filterText, sortCol, sortAsc]);

  if (!columns || columns.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
        No results returned.
      </div>
    );
  }

  const totalPages = Math.ceil(processedRows.length / pageSize) || 1;
  const safePage = Math.min(currentPage, totalPages);
  const paginatedRows = processedRows.slice((safePage - 1) * pageSize, safePage * pageSize);

  const toggleSort = (col: string) => {
    if (sortCol === col) {
      setSortAsc((v) => !v);
    } else {
      setSortCol(col);
      setSortAsc(true);
    }
    setCurrentPage(1);
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl shadow-xs overflow-hidden my-4">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between px-4 py-3 bg-slate-50/80 border-b border-slate-200 gap-2.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-xs font-bold text-slate-700">
            {processedRows.length.toLocaleString()} {filterText ? `of ${rows.length.toLocaleString()} ` : ""}rows
          </span>
          {execMs > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-[10px] font-semibold text-slate-500">
              {execMs}ms
            </span>
          )}
          {truncated && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
              <AlertCircle className="w-3 h-3" /> Truncated to {rows.length} rows
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="w-3 h-3 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={filterText}
              onChange={(e) => {
                setFilterText(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Filter rows..."
              className="pl-7 pr-2.5 py-1 bg-white border border-slate-200 rounded-xl text-[11px] text-slate-700 placeholder-slate-400 focus:outline-hidden focus:border-indigo-400 w-36 transition"
            />
          </div>

          <ExportMenu
            columns={columns}
            rows={processedRows}
            title={title || "SchemaSense Query Results"}
            sql={sql}
            insight={insight}
          />
        </div>
      </div>

      {/* Table view */}
      <div className="overflow-x-auto max-h-96">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-100/80 border-b border-slate-200 sticky top-0 z-10">
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => toggleSort(col)}
                  className="px-4 py-2.5 font-semibold text-slate-700 tracking-wider cursor-pointer hover:bg-slate-200/60 select-none transition"
                >
                  <div className="inline-flex items-center gap-1">
                    <span>{col}</span>
                    <ArrowUpDown
                      className={`w-3 h-3 ${
                        sortCol === col ? "text-indigo-600" : "text-slate-300"
                      }`}
                    />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {paginatedRows.map((row, idx) => (
              <tr key={idx} className="hover:bg-indigo-50/35 transition-colors">
                {columns.map((col) => {
                  const val = row[col];
                  const displayVal =
                    val === null || val === undefined ? (
                      <span className="text-slate-300 italic">null</span>
                    ) : (
                      String(val)
                    );
                  return (
                    <td
                      key={col}
                      className="px-4 py-2 text-slate-600 font-mono text-[11px] max-w-xs truncate"
                      title={val !== null && val !== undefined ? String(val) : ""}
                    >
                      {displayVal}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-200 bg-slate-50/50 text-xs text-slate-500">
          <span>
            Page {safePage} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={safePage === 1}
              className="p-1 rounded-lg hover:bg-slate-200 disabled:opacity-30 transition"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage === totalPages}
              className="p-1 rounded-lg hover:bg-slate-200 disabled:opacity-30 transition"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
