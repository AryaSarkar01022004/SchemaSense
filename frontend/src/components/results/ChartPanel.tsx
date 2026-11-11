"use client";

import React, { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import { BarChart2, Hash, Download } from "lucide-react";
import { mapSpecToECharts } from "@/lib/echartsMapper";

interface ChartPanelProps {
  spec: any;
  rows?: any[];
}

export default function ChartPanel({ spec, rows = [] }: ChartPanelProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  const [chartTypeOverride, setChartTypeOverride] = useState<string | undefined>(undefined);
  const [yColOverride, setYColOverride] = useState<string | undefined>(undefined);

  // Reset overrides if spec changes to a new query result
  useEffect(() => {
    setChartTypeOverride(undefined);
    setYColOverride(undefined);
  }, [spec]);

  const isTable = !spec || spec.type === "table";
  const isKpi = spec?.type === "kpi";

  useEffect(() => {
    if (isTable || isKpi) {
      if (instanceRef.current) {
        instanceRef.current.dispose();
        instanceRef.current = null;
      }
      return;
    }

    const el = chartRef.current;
    if (!el) return;

    const options = mapSpecToECharts(spec, rows, chartTypeOverride, yColOverride);
    if (!options) return;

    let instance = echarts.getInstanceByDom(el);
    if (!instance) {
      instance = echarts.init(el);
    }
    instanceRef.current = instance;
    instance.setOption(options, { notMerge: true });
    instance.resize();

    const handleResize = () => {
      instanceRef.current?.resize();
    };
    window.addEventListener("resize", handleResize);

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(() => {
        instanceRef.current?.resize();
      });
      observer.observe(el);
    }

    return () => {
      window.removeEventListener("resize", handleResize);
      observer?.disconnect();
    };
  }, [spec, rows, chartTypeOverride, yColOverride, isTable, isKpi]);

  // Clean up on full unmount
  useEffect(() => {
    return () => {
      if (instanceRef.current) {
        instanceRef.current.dispose();
        instanceRef.current = null;
      }
    };
  }, []);

  if (isTable) {
    return null;
  }

  // Single Numeric -> KPI Card (Section 5.7)
  if (isKpi) {
    const formattedVal = typeof spec.value === "number" ? spec.value.toLocaleString() : spec.value;
    return (
      <div className="bg-gradient-to-br from-indigo-50 to-white border border-indigo-100 rounded-xl p-6 shadow-xs my-4 max-w-sm">
        <div className="flex items-center justify-between text-indigo-600 mb-2">
          <span className="text-xs font-bold uppercase tracking-wider">{spec.title || "Key Metric"}</span>
          <Hash className="w-5 h-5 opacity-70" />
        </div>
        <div className="text-3xl font-extrabold text-slate-900">{formattedVal}</div>
        {spec.label && <div className="text-xs text-slate-500 mt-1">{spec.label}</div>}
      </div>
    );
  }

  const activeType = chartTypeOverride || spec.type || "bar";
  const availableYCols: string[] =
    spec.available_y_cols && spec.available_y_cols.length > 0
      ? spec.available_y_cols
      : spec.y_axis
      ? [spec.y_axis]
      : [];
  const activeYCol = yColOverride || spec.y_axis;

  const handleExportPng = () => {
    if (!instanceRef.current) return;
    const url = instanceRef.current.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: "#ffffff",
    });
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(spec.title || "chart").toLowerCase().replace(/\s+/g, "_")}.png`;
    link.click();
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs my-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 px-1">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-indigo-600 shrink-0" />
          <h3 className="text-sm font-semibold text-slate-800">{spec.title || "Visualization"}</h3>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {availableYCols.length > 1 && rows.length > 0 && (
            <select
              value={activeYCol}
              onChange={(e) => setYColOverride(e.target.value)}
              className="text-[11px] px-2 py-1 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-medium"
            >
              {availableYCols.map((col) => (
                <option key={col} value={col}>
                  Metric: {col}
                </option>
              ))}
            </select>
          )}

          {spec.type !== "scatter" && (
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-[11px] font-medium">
              {(["bar", "line", "pie"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setChartTypeOverride(t)}
                  className={`px-2 py-0.5 rounded-md capitalize transition ${
                    activeType === t
                      ? "bg-white text-indigo-600 shadow-2xs font-semibold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={handleExportPng}
            title="Download Chart as PNG"
            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-slate-600 hover:text-indigo-600 bg-slate-50 hover:bg-indigo-50 border border-slate-200 rounded-lg transition"
          >
            <Download className="w-3 h-3" /> PNG
          </button>
        </div>
      </div>

      <div ref={chartRef} style={{ width: "100%", height: "320px" }} />
    </div>
  );
}
