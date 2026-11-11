"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Database, Plus, RefreshCw, Shield, CheckCircle2, FileSpreadsheet, UploadCloud, ArrowRight } from "lucide-react";
import SchemaTree from "@/components/schema/SchemaTree";
import FileUploadPanel from "@/components/FileUploadPanel";
import { fetchConnections, createConnection, syncConnection, fetchSchema } from "@/lib/api";

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnId, setSelectedConnId] = useState<string>("");
  const [schemaTables, setSchemaTables] = useState<any[]>([]);
  const [loadingSchema, setLoadingSchema] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);

  // Form state
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [name, setName] = useState("");
  const [dialect, setDialect] = useState("postgres");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState(5432);
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const loadData = async () => {
    try {
      const conns = await fetchConnections();
      setConnections(conns || []);
      if (conns && conns.length > 0 && !selectedConnId) {
        setSelectedConnId(conns[0].id);
        loadSchema(conns[0].id);
      } else if (selectedConnId) {
        loadSchema(selectedConnId);
      }
    } catch (err) {
      console.error("Failed to load connections:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadSchema = async (connId: string) => {
    setLoadingSchema(true);
    try {
      const res = await fetchSchema(connId);
      setSchemaTables(res.tables || []);
    } catch (err) {
      console.error("Failed to load schema:", err);
    } finally {
      setLoadingSchema(false);
    }
  };

  const handleSelectConn = (id: string) => {
    setSelectedConnId(id);
    loadSchema(id);
  };

  const handleSync = async () => {
    if (!selectedConnId || syncing) return;
    setSyncing(true);
    try {
      await syncConnection(selectedConnId);
      await loadSchema(selectedConnId);
      await loadData();
    } catch (err) {
      console.error("Sync error:", err);
    } finally {
      setSyncing(false);
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await createConnection({
        name,
        dialect,
        host,
        port: Number(port),
        database,
        username,
        password,
      });
      setShowAddForm(false);
      setName("");
      setPassword("");
      await loadData();
      if (res.id) {
        setSelectedConnId(res.id);
        loadSchema(res.id);
      }
    } catch (err) {
      console.error("Failed to add connection:", err);
    }
  };

  const activeConn = connections.find((c) => c.id === selectedConnId);

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Data Sources & Connections</h1>
          <p className="text-xs text-slate-500 mt-1">
            Connect PostgreSQL/MySQL databases or upload CSV, XLS, and XLSX files for instant natural-language analysis.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleSync}
            disabled={!selectedConnId || syncing}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-300 rounded-xl shadow-2xs transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-indigo-600 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Syncing Schema..." : "Sync Schema"}
          </button>

          <button
            onClick={() => setShowUploadModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl shadow-xs transition"
          >
            <UploadCloud className="w-4 h-4" /> Upload CSV / XLS
          </button>

          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-xs transition"
          >
            <Plus className="w-4 h-4" /> Add Database
          </button>
        </div>
      </div>

      {/* Connection Selection Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {connections.map((c) => {
          const isSelected = c.id === selectedConnId;
          const isUploadedFile = c.host === "uploaded-file";
          return (
            <div
              key={c.id}
              onClick={() => handleSelectConn(c.id)}
              className={`p-4 rounded-xl border cursor-pointer transition shadow-2xs ${
                isSelected
                  ? "bg-white border-indigo-600 ring-2 ring-indigo-500/10"
                  : "bg-white border-slate-200 hover:border-slate-300"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 truncate">
                  {isUploadedFile ? (
                    <FileSpreadsheet className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : (
                    <Database className="w-4 h-4 text-indigo-600 shrink-0" />
                  )}
                  <span className="font-semibold text-sm text-slate-900 truncate">{c.name}</span>
                </div>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded shrink-0 ${
                  isUploadedFile ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                }`}>
                  {isUploadedFile ? "CSV / XLS" : c.dialect}
                </span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono truncate">{c.database}</div>
              <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-slate-100">
                <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{c.status || "Ready"}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Link
                    href={`/visualizer?connectionId=${encodeURIComponent(c.id)}`}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 hover:text-emerald-700"
                  >
                    Visualize
                  </Link>
                  <Link
                    href={`/chat?connectionId=${encodeURIComponent(c.id)}`}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-700"
                  >
                    Analyze <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Upload CSV / Excel Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-base text-slate-900">Import CSV / Excel (.xls, .xlsx)</h3>
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
              onSuccess={async (res) => {
                setShowUploadModal(false);
                await loadData();
                if (res.id) {
                  setSelectedConnId(res.id);
                  loadSchema(res.id);
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Add Connection Modal Form */}
      {showAddForm && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-base text-slate-900">Connect New Database</h3>
              <button
                onClick={() => setShowAddForm(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Display Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Production Analytics"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800 focus:outline-hidden focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Dialect</label>
                  <select
                    value={dialect}
                    onChange={(e) => setDialect(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                  >
                    <option value="postgres">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlite">SQLite</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Port</label>
                  <input
                    type="number"
                    value={port}
                    onChange={(e) => setPort(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Host</label>
                <input
                  type="text"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Database Name / Path</label>
                <input
                  type="text"
                  required
                  value={database}
                  onChange={(e) => setDatabase(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Username</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                  />
                </div>
              </div>

              <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg flex items-start gap-2 text-emerald-800 text-[11px]">
                <Shield className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" />
                <span>
                  Credentials are encrypted using AES-256 envelope encryption. Decryption only occurs in-memory.
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg shadow-sm transition"
                >
                  Save & Introspect
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Schema Browser Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-800">
            Introspected Schema: {activeConn?.name || "None"}
          </h2>
          <span className="text-xs font-semibold text-slate-500">
            {schemaTables.length} tables registered
          </span>
        </div>

        {loadingSchema ? (
          <div className="p-12 text-center text-xs text-slate-400">Loading catalog schema...</div>
        ) : (
          <SchemaTree tables={schemaTables} onRefresh={() => selectedConnId && loadSchema(selectedConnId)} />
        )}
      </div>
    </div>
  );
}

