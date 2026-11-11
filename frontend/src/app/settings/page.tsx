"use client";

import React, { useState, useEffect } from "react";
import { Cpu, Server, Key, RefreshCw, CheckCircle2, AlertCircle, Zap, Save, Mail } from "lucide-react";
import {
  fetchLLMSettings,
  saveLLMSettings,
  fetchLMStudioModels,
  fetchGeminiModels,
  testLLMSettings,
  fetchEmailSettings,
  saveEmailSettings,
} from "@/lib/api";

export default function SettingsPage() {
  const [provider, setProvider] = useState("lmstudio");
  const [lmstudioUrl, setLmstudioUrl] = useState("http://127.0.0.1:1234/v1");
  const [model, setModel] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [hasOpenaiKey, setHasOpenaiKey] = useState(false);
  const [hasGeminiKey, setHasGeminiKey] = useState(false);

  const [lmModels, setLmModels] = useState<string[]>([]);
  const [geminiModels, setGeminiModels] = useState<string[]>([]);
  const [lmConnected, setLmConnected] = useState<boolean | null>(null);
  const [lmError, setLmError] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [statusBanner, setStatusBanner] = useState<{ ok: boolean; text: string } | null>(null);

  // Gmail SMTP settings
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [hasSmtpPassword, setHasSmtpPassword] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);
  const [emailBanner, setEmailBanner] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const [cfg, emailCfg] = await Promise.all([
          fetchLLMSettings(),
          fetchEmailSettings().catch(() => null),
        ]);
        setProvider(cfg.provider || "mock");
        setLmstudioUrl(cfg.lmstudio_base_url || "http://127.0.0.1:1234/v1");
        setModel(cfg.model || "");
        setHasOpenaiKey(Boolean(cfg.has_openai_key));
        setHasGeminiKey(Boolean(cfg.has_gemini_key));
        if (cfg.lmstudio_base_url) {
          detectLMStudioModels(cfg.lmstudio_base_url);
        }
        if (emailCfg) {
          setSmtpUser(emailCfg.smtp_user || "");
          setHasSmtpPassword(Boolean(emailCfg.has_smtp_password));
        }
      } catch (err) {
        console.error("Failed to fetch LLM settings:", err);
      }
    }
    init();
  }, []);

  const detectLMStudioModels = async (urlOverride?: string) => {
    setLoadingModels(true);
    setLmError(null);
    try {
      const res = await fetchLMStudioModels(urlOverride || lmstudioUrl);
      setLmConnected(Boolean(res.connected));
      setLmModels(res.models || []);
      if (!res.connected) {
        setLmError(res.error || "Could not reach LM Studio Local Server.");
      } else if (res.models?.length > 0 && !model) {
        const firstChat = res.models.find((m: string) => !m.toLowerCase().includes("embed")) || res.models[0];
        setModel(firstChat);
      }
    } catch (err: any) {
      setLmConnected(false);
      setLmError(String(err));
    } finally {
      setLoadingModels(false);
    }
  };

  const buildPayload = () => ({
    provider,
    model,
    lmstudio_base_url: lmstudioUrl,
    openai_api_key: openaiKey || undefined,
    gemini_api_key: geminiKey || undefined,
  });

  const handleSave = async () => {
    setSaving(true);
    setStatusBanner(null);
    try {
      const res = await saveLLMSettings(buildPayload());
      setStatusBanner({
        ok: true,
        text: `Saved active LLM configuration: ${res.provider}${res.model ? ` (${res.model})` : ""}.`,
      });
    } catch (err: any) {
      setStatusBanner({ ok: false, text: `Save failed: ${err}` });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setStatusBanner(null);
    try {
      const res = await testLLMSettings(buildPayload());
      if (res.ok) {
        setStatusBanner({
          ok: true,
          text: `Connected to ${res.provider} (${res.model}) successfully!`,
        });
      } else {
        setStatusBanner({
          ok: false,
          text: res.error || "Connection test failed.",
        });
      }
    } catch (err: any) {
      setStatusBanner({ ok: false, text: `Test failed: ${err}` });
    } finally {
      setTesting(false);
    }
  };

  const providers = [
    { id: "lmstudio", title: "LM Studio (Local)", desc: "Run local open-weights models privately via LM Studio server" },
    { id: "openai", title: "OpenAI", desc: "GPT-4o / GPT-4o-mini cloud API" },
    { id: "gemini", title: "Google Gemini", desc: "Gemini Flash / Pro cloud API" },
    { id: "mock", title: "Offline Engine (Mock)", desc: "Zero-dependency deterministic SQL synthesizer" },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Cpu className="w-6 h-6 text-indigo-600" /> AI Model & Provider Settings
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Connect SchemaSense to your local models in LM Studio or configure cloud LLM providers.
        </p>
      </div>

      {/* Provider Selector */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {providers.map((p) => {
          const active = provider === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => setProvider(p.id)}
              className={`text-left p-4 rounded-xl border transition shadow-2xs ${
                active
                  ? "bg-indigo-50/60 border-indigo-600 ring-2 ring-indigo-500/10"
                  : "bg-white border-slate-200 hover:border-slate-300"
              }`}
            >
              <div className="font-bold text-xs text-slate-900 mb-1">{p.title}</div>
              <div className="text-[11px] text-slate-500 leading-snug">{p.desc}</div>
            </button>
          );
        })}
      </div>

      {/* Provider Details Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-5">
        {provider === "lmstudio" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-indigo-600" />
                <h2 className="font-bold text-sm text-slate-900">LM Studio Local Server Configuration</h2>
              </div>
              {lmConnected === true && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Server Online ({lmModels.length} model{lmModels.length === 1 ? "" : "s"})
                </span>
              )}
              {lmConnected === false && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                  <AlertCircle className="w-3.5 h-3.5" /> Server Offline
                </span>
              )}
            </div>

            <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-1">
              <div className="font-semibold text-slate-800">How to connect LM Studio:</div>
              <div>1. Open <strong>LM Studio</strong>, load a coding/SQL model (e.g., Qwen2.5-Coder, Llama-3, DeepSeek, or Gemma).</div>
              <div>2. Go to the <strong>Developer (Local Server)</strong> tab and click <strong>Start Server</strong> (default port <code>1234</code>).</div>
              <div>3. Click <strong>Refresh Loaded Models</strong> below to automatically detect and bind the model.</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">LM Studio Base URL</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={lmstudioUrl}
                    onChange={(e) => setLmstudioUrl(e.target.value)}
                    placeholder="http://127.0.0.1:1234/v1"
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-lg font-mono text-slate-800 focus:outline-hidden focus:border-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => detectLMStudioModels()}
                    disabled={loadingModels}
                    className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg transition disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingModels ? "animate-spin" : ""}`} />
                    Detect
                  </button>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Loaded Model ID</label>
                {lmModels.length > 0 ? (
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono text-slate-800 bg-white focus:outline-hidden focus:border-indigo-500"
                  >
                    <option value="">Auto-detect loaded chat model</option>
                    {lmModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="Leave blank to auto-select loaded model"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono text-slate-800 focus:outline-hidden focus:border-indigo-500"
                  />
                )}
              </div>
            </div>

            {lmError && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                Could not query LM Studio models at <code>{lmstudioUrl}</code>: {lmError}
              </div>
            )}
          </div>
        )}

        {provider === "openai" && (
          <div className="space-y-4 text-xs">
            <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Key className="w-4 h-4 text-indigo-600" /> OpenAI Configuration
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  OpenAI API Key {hasOpenaiKey && <span className="text-emerald-600">(configured)</span>}
                </label>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={hasOpenaiKey ? "•••••••• (leave blank to keep existing)" : "sk-..."}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Model</label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="gpt-4o-mini"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
                />
              </div>
            </div>
          </div>
        )}

        {provider === "gemini" && (
          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <Key className="w-4 h-4 text-indigo-600" /> Google Gemini Configuration
              </h2>
              {hasGeminiKey && (
                <button
                  type="button"
                  onClick={async () => {
                    const res = await fetchGeminiModels();
                    if (res.connected && res.models) {
                      setGeminiModels(res.models);
                    }
                  }}
                  className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg transition"
                >
                  <RefreshCw className="w-3 h-3" /> Fetch Available Models
                </button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Gemini API Key {hasGeminiKey && <span className="text-emerald-600">(configured)</span>}
                </label>
                <input
                  type="password"
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  placeholder={hasGeminiKey ? "•••••••• (leave blank to keep existing)" : "AIza... or AQ..."}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Model</label>
                {geminiModels.length > 0 ? (
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono bg-white"
                  >
                    <option value="gemini-flash-lite-latest">gemini-flash-lite-latest</option>
                    {geminiModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="gemini-flash-lite-latest"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
                  />
                )}
              </div>
            </div>
          </div>
        )}

        {provider === "mock" && (
          <div className="text-xs text-slate-600 space-y-2">
            <h2 className="font-bold text-sm text-slate-900">Built-in Offline Semantic Engine</h2>
            <p>
              Generates SQL deterministically without calling external APIs. Great for instant offline evaluation,
              demos, and schema safety verification.
            </p>
          </div>
        )}

        {statusBanner && (
          <div
            className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${
              statusBanner.ok
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-rose-50 border-rose-200 text-rose-800"
            }`}
          >
            {statusBanner.ok ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
            <span>{statusBanner.text}</span>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="flex items-center gap-1.5 px-4 py-2 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-300 rounded-xl shadow-2xs transition disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            {testing ? "Testing..." : "Test Connection"}
          </button>

          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-xs transition disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving..." : "Save Configuration"}
          </button>
        </div>
      </div>

      {/* Gmail Export SMTP Settings */}
      <div id="gmail" className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-rose-500" />
            <h2 className="font-bold text-sm text-slate-900">Gmail Direct Export (Optional SMTP)</h2>
          </div>
          {hasSmtpPassword && smtpUser && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3.5 h-3.5" /> Direct Send Enabled
            </span>
          )}
        </div>

        <p className="text-xs text-slate-500 leading-relaxed">
          You can already export any report to Gmail via the <strong>Open in Gmail</strong> web compose option.
          If you also want 1-click direct sending with auto-attached CSV files, enter your Gmail address and a Google App Password below.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Gmail Address</label>
            <input
              type="email"
              value={smtpUser}
              onChange={(e) => setSmtpUser(e.target.value)}
              placeholder="you@gmail.com"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
            />
          </div>
          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Gmail App Password {hasSmtpPassword && <span className="text-emerald-600">(configured)</span>}
            </label>
            <input
              type="password"
              value={smtpPassword}
              onChange={(e) => setSmtpPassword(e.target.value)}
              placeholder={hasSmtpPassword ? "•••••••• (leave blank to keep existing)" : "16-char Google App Password"}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono"
            />
          </div>
        </div>

        {emailBanner && (
          <div
            className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${
              emailBanner.ok
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-rose-50 border-rose-200 text-rose-800"
            }`}
          >
            {emailBanner.ok ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
            <span>{emailBanner.text}</span>
          </div>
        )}

        <div className="flex justify-end pt-2 border-t border-slate-100">
          <button
            type="button"
            disabled={savingEmail}
            onClick={async () => {
              setSavingEmail(true);
              setEmailBanner(null);
              try {
                const res = await saveEmailSettings({
                  smtp_host: "smtp.gmail.com",
                  smtp_port: 587,
                  smtp_user: smtpUser,
                  smtp_password: smtpPassword || undefined,
                });
                setHasSmtpPassword(Boolean(res.has_smtp_password));
                setEmailBanner({ ok: true, text: "Gmail SMTP configuration saved." });
              } catch (err: any) {
                setEmailBanner({ ok: false, text: String(err) });
              } finally {
                setSavingEmail(false);
              }
            }}
            className="flex items-center gap-1.5 px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white text-xs font-semibold rounded-xl shadow-xs transition disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            {savingEmail ? "Saving..." : "Save Gmail Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}

