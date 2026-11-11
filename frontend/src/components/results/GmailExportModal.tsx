"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Mail, Send, ExternalLink, Copy, Check, X, Loader2, AlertCircle, CheckCircle2, Settings } from "lucide-react";
import { exportToEmail, fetchEmailSettings } from "@/lib/api";

interface GmailExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  sql?: string;
  insight?: string;
  columns?: string[];
  rows?: any[];
  onDownloadCsv?: () => void;
}

export default function GmailExportModal({
  isOpen,
  onClose,
  title = "SchemaSense Analysis Report",
  sql = "",
  insight = "",
  columns = [],
  rows = [],
  onDownloadCsv,
}: GmailExportModalProps) {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState(title);
  const [note, setNote] = useState("Hi,\n\nSharing the latest data analysis report from SchemaSense:");
  const [includeInsight, setIncludeInsight] = useState(Boolean(insight));
  const [includeSql, setIncludeSql] = useState(Boolean(sql));
  const [includeTable, setIncludeTable] = useState(rows.length > 0);
  const [autoDownloadCsv, setAutoDownloadCsv] = useState(rows.length > 0);

  const [smtpConfigured, setSmtpConfigured] = useState(false);
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      setSubject(title || "SchemaSense Analysis Report");
      setIncludeInsight(Boolean(insight));
      setIncludeSql(Boolean(sql));
      setIncludeTable(rows.length > 0);
      setStatus(null);
      fetchEmailSettings()
        .then((res) => setSmtpConfigured(Boolean(res?.smtp_configured)))
        .catch(() => setSmtpConfigured(false));
    }
  }, [isOpen, title, insight, sql, rows.length]);

  if (!isOpen) return null;

  const buildPayload = (sendDirect: boolean) => ({
    to,
    subject,
    note,
    insight: includeInsight ? insight : "",
    sql: includeSql ? sql : "",
    columns: includeTable ? columns : [],
    rows: includeTable ? rows : [],
    attachment_filename: `${(title || "schemasense_report").toLowerCase().replace(/[^a-z0-9]+/g, "_")}.csv`,
    send_direct: sendDirect,
  });

  const handleOpenInGmail = async () => {
    setStatus(null);
    try {
      const res = await exportToEmail(buildPayload(false));
      if (autoDownloadCsv && onDownloadCsv && rows.length > 0) {
        onDownloadCsv();
      }
      if (res.gmail_compose_url) {
        window.open(res.gmail_compose_url, "_blank", "noopener,noreferrer");
        setStatus({
          ok: true,
          text: autoDownloadCsv && rows.length > 0
            ? "Opened Gmail compose window and downloaded CSV file for attachment."
            : "Opened Gmail compose window.",
        });
      }
    } catch (err: any) {
      setStatus({ ok: false, text: String(err?.message || err) });
    }
  };

  const handleCopyReport = async () => {
    try {
      const res = await exportToEmail(buildPayload(false));
      if (res.plain_report) {
        await navigator.clipboard.writeText(res.plain_report);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch (err) {
      console.error("Failed to copy report:", err);
    }
  };

  const handleDirectSend = async () => {
    if (!to.trim()) {
      setStatus({ ok: false, text: "Please enter a recipient email address first." });
      return;
    }
    setSending(true);
    setStatus(null);
    try {
      const res = await exportToEmail(buildPayload(true));
      if (res.sent) {
        setStatus({ ok: true, text: `Report emailed directly to ${to} with CSV attached!` });
      } else {
        setStatus({ ok: false, text: res.error || "Failed to send email." });
      }
    } catch (err: any) {
      setStatus({ ok: false, text: String(err?.message || err) });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fade-in-up">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 bg-gradient-to-r from-rose-500 to-amber-500 text-white flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-white/20 rounded-lg">
              <Mail className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm">Export Report to Gmail</h3>
              <p className="text-[11px] text-rose-50">
                Share insights, SQL, and tabular CSV data directly via Gmail
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 hover:bg-white/20 rounded-lg transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-5 space-y-4 text-xs">
          <div className="grid grid-cols-1 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Recipient Email (To)</label>
              <input
                type="email"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="colleague@company.com"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800 focus:outline-hidden focus:border-indigo-500 focus:bg-white transition"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800 focus:outline-hidden focus:border-indigo-500 focus:bg-white transition"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Message Note</label>
              <textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-800 focus:outline-hidden focus:border-indigo-500 focus:bg-white transition"
              />
            </div>
          </div>

          {/* Content Checkboxes */}
          <div className="flex flex-wrap gap-3 p-3 bg-slate-50 border border-slate-200 rounded-xl">
            {insight && (
              <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-700 font-medium">
                <input
                  type="checkbox"
                  checked={includeInsight}
                  onChange={(e) => setIncludeInsight(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600"
                />
                Include Insight
              </label>
            )}
            {sql && (
              <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-700 font-medium">
                <input
                  type="checkbox"
                  checked={includeSql}
                  onChange={(e) => setIncludeSql(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600"
                />
                Include SQL
              </label>
            )}
            {rows.length > 0 && (
              <>
                <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-700 font-medium">
                  <input
                    type="checkbox"
                    checked={includeTable}
                    onChange={(e) => setIncludeTable(e.target.checked)}
                    className="rounded border-slate-300 text-indigo-600"
                  />
                  Include Data Summary ({rows.length} rows)
                </label>
                <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-700 font-medium">
                  <input
                    type="checkbox"
                    checked={autoDownloadCsv}
                    onChange={(e) => setAutoDownloadCsv(e.target.checked)}
                    className="rounded border-slate-300 text-indigo-600"
                  />
                  Download CSV for attachment
                </label>
              </>
            )}
          </div>

          {!smtpConfigured && (
            <div className="flex items-center justify-between gap-2 p-2.5 bg-indigo-50/70 border border-indigo-100 rounded-xl text-[11px] text-indigo-800">
              <span>Want 1-click direct sending with auto-attached CSV?</span>
              <Link
                href="/settings#gmail"
                onClick={onClose}
                className="inline-flex items-center gap-1 font-bold text-indigo-700 hover:underline shrink-0"
              >
                <Settings className="w-3 h-3" /> Setup Gmail SMTP
              </Link>
            </div>
          )}

          {status && (
            <div
              className={`p-2.5 rounded-xl border flex items-start gap-2 text-[11px] ${
                status.ok
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : "bg-rose-50 border-rose-200 text-rose-800"
              }`}
            >
              {status.ok ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              )}
              <span>{status.text}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={handleCopyReport}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-xl transition"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied Report!" : "Copy Text"}
            </button>

            <div className="flex items-center gap-2">
              {smtpConfigured && (
                <button
                  type="button"
                  onClick={handleDirectSend}
                  disabled={sending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl shadow-xs transition disabled:opacity-50"
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  {sending ? "Sending..." : "Send Direct"}
                </button>
              )}

              <button
                type="button"
                onClick={handleOpenInGmail}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-rose-500 to-amber-500 hover:from-rose-600 hover:to-amber-600 text-white font-semibold rounded-xl shadow-sm transition"
              >
                <ExternalLink className="w-3.5 h-3.5" /> Open in Gmail
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

