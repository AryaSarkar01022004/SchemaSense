"use client";

import React, { useState, useEffect } from "react";
import {
  BarChart3,
  PieChart,
  TrendingUp,
  Layers,
  Database,
  FileSpreadsheet,
  Sparkles,
  Loader2,
  Code2,
  SlidersHorizontal,
  LayoutGrid,
} from "lucide-react";
import ChartPanel from "@/components/results/ChartPanel";
import DataGrid from "@/components/results/DataGrid";
import ExportMenu from "@/components/results/ExportMenu";
import {
  fetchConnections,
  fetchSchema,
  runVisualizerQuery,
  discoverVisualizerCharts,
} from "@/lib/api";

const CHART_TYPES = [
  { id: "bar", label: "Bar", icon: BarChart3 },
  { id: "hbar", label: "H-Bar", icon: Layers },
  { id: "line", label: "Line", icon: TrendingUp },
  { id: "area", label: "Area", icon: TrendingUp },
  { id: "pie", label: "Pie / Donut", icon: PieChart },
  { id: "scatter", label: "Scatter", icon: Sparkles },
];

export default function VisualizerPage() {
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnId, setSelectedConnId] = useState<string>("");
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTableName, setSelectedTableName] = useState<string>("");

  const [mode, setMode] = useState<"builder" | "discover">("builder");

  // Builder state
  const [chartType, setChartType] = useState<string>("bar");
  const [xCol, setXCol] = useState<string>("");
  const [yCol, setYCol] = useState<string>("");
  const [aggregation, setAggregation] = useState<string>("COUNT");
  const [limit, setLimit] = useState<number>(10);
  const [sortDir, setSortDir] = useState<string>("DESC");

  const [builderResult, setBuilderResult] = useState<any>(null);
  const [builderLoading, setBuilderLoading] = useState<boolean>(false);
  const [builderError, setBuilderError] = useState<string | null>(null);
  const [showSql, setShowSql] = useState<boolean>(false);

  // Auto-discover state
  const [discoverData, setDiscoverData] = useState<any>(null);
  const [discoverLoading, setDiscoverLoading] = useState<boolean>(false);

  useEffect(() => {
    async function init() {
      try {
        const params = new URLSearchParams(window.location.search);
        const paramConnId = params.get("connectionId");
        const conns = await fetchConnections();
        const connList = conns || [];
        setConnections(connList);
        if (connList.length > 0) {
          const initialId =
            paramConnId && connList.some((c: any) => c.id === paramConnId)
              ? paramConnId
              : connList[0].id;
          setSelectedConnId(initialId);
          await loadSchema(initialId);
        }
      } catch (err) {
        console.error("Failed to initialize visualizer:", err);
      }
    }
    init();
  }, []);

  const loadSchema = async (connId: string) => {
    try {
      const res = await fetchSchema(connId);
      const tbls = res.tables || [];
      setTables(tbls);
      if (tbls.length > 0) {
        const firstTbl = tbls[0];
        setSelectedTableName(firstTbl.table_name);
        pickDefaultAxes(firstTbl);
      } else {
        setSelectedTableName("");
        setXCol("");
        setYCol("");
      }
    } catch (err) {
      console.error("Failed to load schema:", err);
    }
  };

  const pickDefaultAxes = (tbl: any) => {
    const cols = (tbl?.columns || []).filter((c: any) => !c.is_sensitive);
    const numericCols = cols.filter((c: any) =>
      /(INT|REAL|FLOAT|DOUBLE|NUMERIC|DECIMAL)/i.test(c.data_type || "") &&
      c.column_name.toLowerCase() !== "id" &&
      !c.column_name.toLowerCase().endsWith("_id")
    );
    const catCols = cols.filter(
      (c: any) =>
        !numericCols.includes(c) &&
        c.column_name.toLowerCase() !== "id" &&
        !c.column_name.toLowerCase().endsWith("_id") &&
        !/(about|description|review_content|img_link|product_link|url)/i.test(c.column_name)
    );
    catCols.sort((a: any, b: any) => (a.distinct_estimate || 9999) - (b.distinct_estimate || 9999));

    const defaultX = catCols[0]?.column_name || cols[0]?.column_name || "";
    const defaultY = numericCols[0]?.column_name || "";
    setXCol(defaultX);
    setYCol(defaultY);
    setAggregation(defaultY ? (defaultY.toLowerCase().includes("rating") ? "AVG" : "SUM") : "COUNT");
  };

  const handleSelectConn = async (connId: string) => {
    setSelectedConnId(connId);
    setBuilderResult(null);
    setDiscoverData(null);
    await loadSchema(connId);
  };

  const handleSelectTable = (tName: string) => {
    setSelectedTableName(tName);
    setBuilderResult(null);
    setDiscoverData(null);
    const tbl = tables.find((t) => t.table_name === tName);
    if (tbl) pickDefaultAxes(tbl);
  };

  // Run builder query reactively whenever builder inputs change
  useEffect(() => {
    if (mode !== "builder" || !selectedConnId || !selectedTableName || !xCol) return;

    let cancelled = false;
    async function execute() {
      setBuilderLoading(true);
      setBuilderError(null);
      try {
        const res = await runVisualizerQuery({
          connection_id: selectedConnId,
          table_name: selectedTableName,
          x_col: xCol,
          y_col: aggregation === "COUNT" ? undefined : yCol || undefined,
          aggregation,
          chart_type: chartType,
          limit,
          sort_dir: sortDir,
        });
        if (!cancelled) {
          if (res.error) {
            setBuilderError(res.error);
          } else {
            setBuilderResult(res);
          }
        }
      } catch (err: any) {
        if (!cancelled) setBuilderError(String(err?.message || err));
      } finally {
        if (!cancelled) setBuilderLoading(false);
      }
    }
    execute();
    return () => {
      cancelled = true;
    };
  }, [mode, selectedConnId, selectedTableName, xCol, yCol, aggregation, chartType, limit, sortDir]);

  // Run auto-discover when switching to discover mode
  useEffect(() => {
    if (mode !== "discover" || !selectedConnId || !selectedTableName) return;
    let cancelled = false;
    async function runDiscover() {
      setDiscoverLoading(true);
      try {
        const res = await discoverVisualizerCharts(selectedConnId, selectedTableName);
        if (!cancelled) setDiscoverData(res);
      } catch (err) {
        console.error("Auto discover failed:", err);
      } finally {
        if (!cancelled) setDiscoverLoading(false);
      }
    }
    runDiscover();
    return () => {
      cancelled = true;
    };
  }, [mode, selectedConnId, selectedTableName]);

  const activeConn = connections.find((c) => c.id === selectedConnId);
  const activeTable = tables.find((t) => t.table_name === selectedTableName);
  const allCols = (activeTable?.columns || []).filter((c: any) => !c.is_sensitive);
  const numericCols = allCols.filter((c: any) =>
    /(INT|REAL|FLOAT|DOUBLE|NUMERIC|DECIMAL)/i.test(c.data_type || "")
  );

  // Sync context with Analysis Assistant
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.__schemasenseContext = {
      connectionId: selectedConnId || undefined,
      connectionName: activeConn?.name || undefined,
      activeSql: builderResult?.sql || undefined,
      activeColumns: builderResult?.columns || undefined,
      sampleRows: builderResult?.rows?.slice(0, 5) || undefined,
    };
    window.dispatchEvent(new CustomEvent("schemasense:context-updated"));
  }, [selectedConnId, activeConn?.name, builderResult]);

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Top Studio Header */}
      <div className="bg-white/90 backdrop-blur border border-slate-200/90 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
            <span className="p-1.5 rounded-xl bg-indigo-600 text-white shadow-xs">
              <BarChart3 className="w-5 h-5" />
            </span>
            Interactive Data Visualizer
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Build custom charts visually from any database table or CSV/XLS file — no SQL required.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Connection Picker */}
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800">
            {activeConn?.host === "uploaded-file" ? (
              <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
            ) : (
              <Database className="w-4 h-4 text-indigo-600" />
            )}
            <select
              value={selectedConnId}
              onChange={(e) => handleSelectConn(e.target.value)}
              className="bg-transparent outline-hidden cursor-pointer"
            >
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Table Picker */}
          {tables.length > 0 && (
            <select
              value={selectedTableName}
              onChange={(e) => handleSelectTable(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 outline-hidden cursor-pointer"
            >
              {tables.map((t) => (
                <option key={t.id} value={t.table_name}>
                  Table: {t.table_name} ({t.row_estimate?.toLocaleString() || 0} rows)
                </option>
              ))}
            </select>
          )}

          {/* Mode Toggle */}
          <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setMode("builder")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
                mode === "builder" ? "bg-white text-indigo-600 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" /> Visual Builder
            </button>
            <button
              type="button"
              onClick={() => setMode("discover")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
                mode === "discover" ? "bg-white text-indigo-600 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" /> Auto-Dashboard
            </button>
          </div>
        </div>
      </div>

      {/* KPI Strip */}
      {activeTable && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-2xs">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Records</div>
            <div className="text-2xl font-black text-slate-900 mt-1">
              {(activeTable.row_estimate || 0).toLocaleString()}
            </div>
          </div>
          <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-2xs">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Columns</div>
            <div className="text-2xl font-black text-indigo-600 mt-1">{allCols.length}</div>
          </div>
          <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-2xs">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Numeric Metrics</div>
            <div className="text-2xl font-black text-emerald-600 mt-1">{numericCols.length}</div>
          </div>
          <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-2xs">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Source</div>
            <div className="text-sm font-bold text-slate-800 mt-2 truncate">{activeTable.table_name}</div>
          </div>
        </div>
      )}

      {/* Mode 1: Interactive Chart Builder */}
      {mode === "builder" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left Controls Rail */}
          <div className="lg:col-span-4 bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs space-y-5 h-fit">
            <div>
              <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                Chart Type
              </label>
              <div className="grid grid-cols-3 gap-1.5">
                {CHART_TYPES.map((ct) => {
                  const Icon = ct.icon;
                  const active = chartType === ct.id;
                  return (
                    <button
                      key={ct.id}
                      type="button"
                      onClick={() => setChartType(ct.id)}
                      className={`flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl border text-[11px] font-semibold transition ${
                        active
                          ? "bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs"
                          : "bg-slate-50/70 border-slate-200 text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{ct.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  X-Axis / Group Dimension
                </label>
                <select
                  value={xCol}
                  onChange={(e) => setXCol(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800 font-mono text-xs"
                >
                  {allCols.map((c: any) => (
                    <option key={c.id} value={c.column_name}>
                      {c.column_name} ({c.data_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Aggregation</label>
                <div className="grid grid-cols-3 gap-1.5">
                  {["COUNT", "SUM", "AVG", "MIN", "MAX", "RAW"].map((agg) => (
                    <button
                      key={agg}
                      type="button"
                      onClick={() => setAggregation(agg)}
                      className={`py-1.5 rounded-lg border text-[11px] font-bold transition ${
                        aggregation === agg
                          ? "bg-indigo-600 border-indigo-600 text-white"
                          : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {agg}
                    </button>
                  ))}
                </div>
              </div>

              {aggregation !== "COUNT" && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Y-Axis / Metric Column
                  </label>
                  <select
                    value={yCol}
                    onChange={(e) => setYCol(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800 font-mono text-xs"
                  >
                    {numericCols.length === 0 ? (
                      <option value="">No numeric columns (use COUNT)</option>
                    ) : (
                      numericCols.map((c: any) => (
                        <option key={c.id} value={c.column_name}>
                          {c.column_name} ({c.data_type})
                        </option>
                      ))
                    )}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Top Rows</label>
                  <select
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800"
                  >
                    {[5, 10, 15, 25, 50, 100].map((n) => (
                      <option key={n} value={n}>
                        Top {n}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Sort Order</label>
                  <select
                    value={sortDir}
                    onChange={(e) => setSortDir(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800"
                  >
                    <option value="DESC">Highest First</option>
                    <option value="ASC">Lowest First</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Right Live Visualization Canvas */}
          <div className="lg:col-span-8 space-y-4">
            {builderError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
                {builderError}
              </div>
            )}

            {builderLoading && !builderResult && (
              <div className="bg-white border border-slate-200 rounded-2xl p-16 flex flex-col items-center justify-center gap-2 text-xs text-slate-500">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                <span>Building visualization...</span>
              </div>
            )}

            {builderResult && (
              <>
                <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-xs space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-100">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      {builderLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />}
                      <span className="font-semibold text-slate-700">
                        {builderResult.row_count} groups plotted ({builderResult.exec_ms}ms)
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setShowSql((v) => !v)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-[11px] font-semibold transition"
                      >
                        <Code2 className="w-3.5 h-3.5" /> {showSql ? "Hide SQL" : "Show SQL"}
                      </button>

                      <ExportMenu
                        columns={builderResult.columns || []}
                        rows={builderResult.rows || []}
                        filename={`${selectedTableName}_visual`}
                        title={builderResult.chart_spec?.title || `${selectedTableName} Visualization`}
                        sql={builderResult.sql}
                      />
                    </div>
                  </div>

                  {showSql && (
                    <pre className="p-3 bg-slate-900 text-emerald-300 rounded-xl font-mono text-xs overflow-x-auto">
                      {builderResult.sql}
                    </pre>
                  )}

                  <ChartPanel
                    spec={builderResult.chart_spec}
                    rows={builderResult.rows || []}
                  />
                </div>

                <DataGrid
                  columns={builderResult.columns || []}
                  rows={builderResult.rows || []}
                  rowCount={builderResult.row_count}
                  execMs={builderResult.exec_ms}
                  title={builderResult.chart_spec?.title || `${selectedTableName} Visualization`}
                  sql={builderResult.sql}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* Mode 2: Auto-Discovered Dashboard Grid */}
      {mode === "discover" && (
        <div className="space-y-4">
          {discoverLoading ? (
            <div className="bg-white border border-slate-200 rounded-2xl p-16 flex flex-col items-center justify-center gap-2 text-xs text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
              <span>Auto-discovering best charts for {selectedTableName}...</span>
            </div>
          ) : discoverData?.charts?.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {discoverData.charts.map((c: any, idx: number) => (
                <div
                  key={idx}
                  className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-xs space-y-2"
                >
                  <div className="flex items-center justify-end">
                    <ExportMenu
                      columns={c.columns || []}
                      rows={c.rows || []}
                      filename={`${selectedTableName}_chart_${idx + 1}`}
                      title={c.chart_spec?.title || "SchemaSense Chart"}
                      sql={c.sql}
                    />
                  </div>
                  <ChartPanel spec={c.chart_spec} rows={c.rows || []} />
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center text-xs text-slate-500">
              No auto-discovered charts available for this table yet. Try the Visual Builder tab!
            </div>
          )}
        </div>
      )}
    </div>
  );
}

