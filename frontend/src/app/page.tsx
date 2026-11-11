import Link from "next/link";
import {
  MessageSquare,
  Database,
  ShieldCheck,
  FileSpreadsheet,
  BarChart3,
  Cpu,
  Mail,
  Sparkles,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  return (
    <div className="py-10 space-y-14 animate-fade-in-up">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto space-y-6">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gradient-to-r from-indigo-50 to-emerald-50 text-indigo-700 border border-indigo-200/80 shadow-2xs">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          Powered by Gemini &amp; Local LM Studio · Read-Only AST Sandbox
        </div>

        <h1 className="text-4xl sm:text-6xl font-black text-slate-900 tracking-tight leading-[1.1]">
          Ask questions.{" "}
          <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-emerald-600 bg-clip-text text-transparent">
            Visualize instantly.
          </span>
        </h1>

        <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto">
          Connect PostgreSQL or MySQL databases, or drop CSV and Excel files for instant analysis.
          Explore with natural language, build custom charts in the Data Visualizer, and share insights via Gmail.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-sm font-semibold rounded-2xl shadow-md hover:shadow-lg transition-all"
          >
            <MessageSquare className="w-4 h-4" /> Open Explorer
            <ArrowRight className="w-4 h-4" />
          </Link>

          <Link
            href="/visualizer"
            className="inline-flex items-center gap-2 px-6 py-3 bg-white hover:bg-emerald-50 text-emerald-700 text-sm font-semibold border border-emerald-200 rounded-2xl shadow-xs transition-all"
          >
            <BarChart3 className="w-4 h-4 text-emerald-600" /> Data Visualizer Studio
          </Link>

          <Link
            href="/connections"
            className="inline-flex items-center gap-2 px-5 py-3 bg-white hover:bg-slate-50 text-slate-700 text-sm font-semibold border border-slate-200 rounded-2xl shadow-xs transition-all"
          >
            <Database className="w-4 h-4 text-indigo-600" /> Databases &amp; CSV/XLS
          </Link>
        </div>
      </div>

      {/* Bento Feature Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 pt-2">
        <Link
          href="/visualizer"
          className="group bg-white/90 border border-slate-200/90 hover:border-indigo-300 rounded-2xl p-6 shadow-xs hover:shadow-md transition-all space-y-3"
        >
          <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:scale-105 transition">
            <BarChart3 className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-base">Data Visualizer</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Pick axes, aggregations (SUM/AVG/COUNT), and chart types (Bar, Line, Area, Donut, Scatter) or auto-discover a full dashboard.
          </p>
        </Link>

        <Link
          href="/connections"
          className="group bg-white/90 border border-slate-200/90 hover:border-emerald-300 rounded-2xl p-6 shadow-xs hover:shadow-md transition-all space-y-3"
        >
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-105 transition">
            <FileSpreadsheet className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-base">CSV, XLS &amp; SQL DBs</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Upload spreadsheets directly or connect PostgreSQL/MySQL with AES-256 envelope encryption and schema introspection.
          </p>
        </Link>

        <Link
          href="/settings"
          className="group bg-white/90 border border-slate-200/90 hover:border-violet-300 rounded-2xl p-6 shadow-xs hover:shadow-md transition-all space-y-3"
        >
          <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center group-hover:scale-105 transition">
            <Cpu className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-base">Gemini &amp; LM Studio</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Connected to Google Gemini with an interactive Analysis Assistant drawer, or run privately with local models in LM Studio.
          </p>
        </Link>

        <Link
          href="/chat"
          className="group bg-white/90 border border-slate-200/90 hover:border-rose-300 rounded-2xl p-6 shadow-xs hover:shadow-md transition-all space-y-3"
        >
          <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-500 flex items-center justify-center group-hover:scale-105 transition">
            <Mail className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-base">Gmail, CSV &amp; PNG Export</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Share analysis reports, SQL, and table previews directly to Gmail, export CSV/JSON datasets, or save high-res PNG charts.
          </p>
        </Link>
      </div>
    </div>
  );
}
