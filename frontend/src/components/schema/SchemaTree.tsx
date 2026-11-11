import React, { useState } from "react";
import { Table, Key, Link2, ShieldAlert, ChevronDown, ChevronRight, Edit3 } from "lucide-react";
import ColumnEditor from "./ColumnEditor";

interface SchemaTreeProps {
  tables: any[];
  onRefresh?: () => void;
}

export default function SchemaTree({ tables = [], onRefresh }: SchemaTreeProps) {
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [editingColumnId, setEditingColumnId] = useState<string | null>(null);

  const toggleTable = (id: string) => {
    setExpandedTables((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (!tables || tables.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-slate-500 bg-white border border-slate-200 rounded-xl">
        No schema discovered yet. Click &quot;Sync Schema&quot; to introspect the database.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tables.map((table) => {
        const isExpanded = expandedTables[table.id] ?? true;
        return (
          <div key={table.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
            {/* Table Header */}
            <div
              onClick={() => toggleTable(table.id)}
              className="flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100/70 cursor-pointer border-b border-slate-200/80 transition"
            >
              <div className="flex items-center gap-2.5">
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                )}
                <Table className="w-4 h-4 text-indigo-600" />
                <span className="font-semibold text-sm text-slate-900">{table.table_name}</span>
                {table.row_estimate > 0 && (
                  <span className="text-xs text-slate-500 font-mono">
                    (~{table.row_estimate.toLocaleString()} rows)
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-500 italic max-w-sm truncate">
                {table.description}
              </div>
            </div>

            {/* Column List */}
            {isExpanded && (
              <div className="divide-y divide-slate-100">
                {table.columns.map((col: any) => (
                  <div key={col.id} className="px-4 py-2.5 hover:bg-slate-50/50 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {col.is_pk && (
                          <span title="Primary Key">
                            <Key className="w-3.5 h-3.5 text-amber-500" />
                          </span>
                        )}
                        {col.fk_column && (
                          <span title={`Foreign Key -> ${col.fk_table_name || "table"}.${col.fk_column}`}>
                            <Link2 className="w-3.5 h-3.5 text-blue-500" />
                          </span>
                        )}
                        {col.is_sensitive && (
                          <span title="Restricted / Sensitive Data">
                            <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                          </span>
                        )}
                        <span className="font-mono font-medium text-slate-800">{col.column_name}</span>
                        <span className="text-[11px] font-mono text-slate-400">{col.data_type}</span>

                        {col.sample_values && col.sample_values.length > 0 && !col.is_sensitive && (
                          <span className="hidden sm:inline-block px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 font-mono truncate max-w-xs">
                            {`{${col.sample_values.slice(0, 4).join(", ")}}`}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="text-slate-500 text-[11px]">{col.description}</span>
                        <button
                          onClick={() => setEditingColumnId(editingColumnId === col.id ? null : col.id)}
                          className="p-1 text-slate-400 hover:text-indigo-600 transition"
                          title="Edit column metadata"
                        >
                          <Edit3 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>

                    {editingColumnId === col.id && (
                      <ColumnEditor
                        column={col}
                        onSaved={() => {
                          setEditingColumnId(null);
                          onRefresh?.();
                        }}
                        onCancel={() => setEditingColumnId(null)}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

