"use client";

import React, { useState, useEffect } from "react";
import { Activity, AlertTriangle, AlertCircle, ArrowUpRight, ArrowDownRight, Bell, Calendar } from "lucide-react";
import { fetchInsights } from "@/lib/api";

export default function InsightsPage() {
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchInsights();
        setInsights(res || []);
      } catch (err) {
        console.error("Failed to load insights:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6 text-amber-500" /> Automated Anomaly Insights
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Statistical detection across pinned metric series (rolling median + MAD, robust z-score &gt; 3.0).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-slate-700 text-xs font-semibold border border-slate-300 rounded-lg shadow-2xs hover:bg-slate-50 transition">
            <Bell className="w-3.5 h-3.5 text-indigo-600" /> Configure Slack / Email Webhook
          </button>
        </div>
      </div>

      {/* Insights Cards */}
      {loading ? (
        <div className="p-12 text-center text-xs text-slate-400">Scanning for metric anomalies...</div>
      ) : insights.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center space-y-3 max-w-lg mx-auto">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
            <Activity className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-slate-800 text-base">All Metrics Operating Normally</h3>
          <p className="text-xs text-slate-500">
            No statistical anomalies detected. When robust z-scores exceed 3.0 or unexpected week-over-week
            deviations occur, automated AI insights will appear here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {insights.map((insight) => {
            const isCritical = insight.severity === "critical";
            const isHigh = insight.severity === "high";
            const detail = insight.detail || {};

            return (
              <div
                key={insight.id}
                className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3 hover:border-slate-300 transition"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                        isCritical
                          ? "bg-rose-50 text-rose-700 border border-rose-200"
                          : isHigh
                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                          : "bg-blue-50 text-blue-700 border border-blue-200"
                      }`}
                    >
                      <AlertTriangle className="w-3 h-3" />
                      {insight.severity} Anomaly
                    </span>
                    <span className="font-bold text-sm text-slate-900">
                      {detail.metric_name || "Metric Alert"}
                    </span>
                  </div>

                  <span className="text-[11px] text-slate-400 flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {insight.detected_at?.slice(0, 10)}
                  </span>
                </div>

                <p className="text-xs text-slate-700 leading-relaxed font-medium">
                  {insight.summary}
                </p>

                {/* Statistical Details Strip */}
                {detail.robust_z_score && (
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100 text-[11px]">
                    <div className="bg-slate-50 p-2 rounded-lg">
                      <span className="text-slate-400 block text-[10px]">Robust Z-Score</span>
                      <span className="font-mono font-bold text-slate-800">{detail.robust_z_score}</span>
                    </div>
                    <div className="bg-slate-50 p-2 rounded-lg">
                      <span className="text-slate-400 block text-[10px]">Baseline Median</span>
                      <span className="font-mono font-bold text-slate-800">
                        {typeof detail.baseline_median === "number" ? detail.baseline_median.toLocaleString() : detail.baseline_median}
                      </span>
                    </div>
                    <div className="bg-slate-50 p-2 rounded-lg">
                      <span className="text-slate-400 block text-[10px]">Latest Value</span>
                      <span className="font-mono font-bold text-indigo-600">
                        {typeof detail.latest_value === "number" ? detail.latest_value.toLocaleString() : detail.latest_value}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

