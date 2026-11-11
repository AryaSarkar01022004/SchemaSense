"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, FileSpreadsheet, X, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { uploadFilesConnection } from "@/lib/api";

interface FileUploadPanelProps {
  onSuccess?: (result: any) => void;
  onCancel?: () => void;
  compact?: boolean;
}

export default function FileUploadPanel({ onSuccess, onCancel, compact = false }: FileUploadPanelProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [datasetName, setDatasetName] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptExt = [".csv", ".tsv", ".xls", ".xlsx"];

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setError(null);
    const valid: File[] = [];
    const rejected: string[] = [];
    Array.from(incoming).forEach((f) => {
      const lower = f.name.toLowerCase();
      if (acceptExt.some((ext) => lower.endsWith(ext))) {
        valid.push(f);
      } else {
        rejected.push(f.name);
      }
    });
    if (rejected.length > 0) {
      setError(`Unsupported file(s): ${rejected.join(", ")}. Please select .csv, .tsv, .xls, or .xlsx files.`);
    }
    if (valid.length > 0) {
      setFiles((prev) => [...prev, ...valid]);
    }
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUpload = async () => {
    if (files.length === 0 || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadFilesConnection(files, datasetName);
      setFiles([]);
      setDatasetName("");
      onSuccess?.(result);
    } catch (err: any) {
      setError(err?.message || "Failed to upload and parse files.");
    } finally {
      setUploading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl text-center cursor-pointer transition ${
          compact ? "p-5" : "p-8"
        } ${
          dragging
            ? "border-indigo-500 bg-indigo-50/70"
            : "border-slate-300 bg-slate-50/60 hover:border-indigo-400 hover:bg-indigo-50/30"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".csv,.tsv,.xls,.xlsx"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
          className="hidden"
        />
        <div className="flex flex-col items-center gap-2">
          <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
            <UploadCloud className="w-5 h-5" />
          </div>
          <div className="text-xs font-semibold text-slate-800">
            Drop CSV, XLS, or XLSX files here, or <span className="text-indigo-600 underline">browse</span>
          </div>
          <div className="text-[11px] text-slate-500">
            Each file or Excel worksheet is automatically indexed into SQL tables for natural language analysis.
          </div>
        </div>
      </div>

      {/* Selected Files List */}
      {files.length > 0 && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Dataset Name (optional)
            </label>
            <input
              type="text"
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              placeholder={files[0].name.replace(/\.(csv|tsv|xlsx|xls)$/i, "")}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-hidden focus:border-indigo-500"
            />
          </div>

          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {files.map((f, idx) => {
              const ext = f.name.split(".").pop()?.toUpperCase() || "FILE";
              return (
                <div
                  key={`${f.name}-${idx}`}
                  className="flex items-center justify-between px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs"
                >
                  <div className="flex items-center gap-2 truncate">
                    <FileSpreadsheet className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-medium text-slate-800 truncate">{f.name}</span>
                    <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-bold">
                      {ext}
                    </span>
                    <span className="text-slate-400 text-[11px]">{formatBytes(f.size)}</span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(idx);
                    }}
                    className="p-1 text-slate-400 hover:text-rose-600"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {error && (
        <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleUpload}
          disabled={files.length === 0 || uploading}
          className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-xs transition disabled:opacity-40"
        >
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
          {uploading ? "Ingesting & Indexing..." : `Import ${files.length > 0 ? `${files.length} File(s)` : "Files"}`}
        </button>
      </div>
    </div>
  );
}

