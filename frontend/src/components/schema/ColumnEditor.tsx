import React, { useState } from "react";
import { Shield, ShieldAlert, Check, X } from "lucide-react";
import { updateColumn } from "@/lib/api";

interface ColumnEditorProps {
  column: any;
  onSaved?: () => void;
  onCancel?: () => void;
}

export default function ColumnEditor({ column, onSaved, onCancel }: ColumnEditorProps) {
  const [description, setDescription] = useState(column.description || "");
  const [isSensitive, setIsSensitive] = useState(Boolean(column.is_sensitive));
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateColumn(column.id, {
        description,
        is_sensitive: isSensitive,
      });
      onSaved?.();
    } catch (err) {
      console.error("Failed to update column:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-3 mt-2 text-xs">
      <div>
        <label className="block font-semibold text-slate-700 mb-1">Column Description</label>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded text-xs text-slate-800 focus:outline-hidden focus:border-indigo-500"
          placeholder="Brief description for LLM context..."
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
          <input
            type="checkbox"
            checked={isSensitive}
            onChange={(e) => setIsSensitive(e.target.checked)}
            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span className="flex items-center gap-1">
            {isSensitive ? (
              <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
            ) : (
              <Shield className="w-3.5 h-3.5 text-slate-400" />
            )}
            Mark as Sensitive / PII (Restricted)
          </span>
        </label>
      </div>

      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          onClick={onCancel}
          className="px-2.5 py-1 text-slate-600 hover:bg-slate-200 rounded transition"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded transition disabled:opacity-50"
        >
          <Check className="w-3.5 h-3.5" /> {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}

