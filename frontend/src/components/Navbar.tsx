"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  MessageSquare,
  BarChart3,
  Activity,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { fetchLLMSettings } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const [aiBadge, setAiBadge] = useState<string>("AI Ready");

  useEffect(() => {
    fetchLLMSettings()
      .then((cfg) => {
        if (cfg?.provider === "gemini") setAiBadge("Gemini");
        else if (cfg?.provider === "lmstudio") setAiBadge("LM Studio");
        else if (cfg?.provider === "openai") setAiBadge("OpenAI");
        else setAiBadge("Offline AI");
      })
      .catch(() => {});
  }, [pathname]);

  const navItems = [
    { href: "/chat", label: "Explorer", icon: MessageSquare },
    { href: "/visualizer", label: "Data Visualizer", icon: BarChart3 },
    { href: "/connections", label: "Data Sources", icon: Database },
    { href: "/insights", label: "Insights", icon: Activity },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-md border-b border-slate-200/80 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2.5 font-black text-xl text-slate-900 tracking-tight group"
          >
            <div className="p-2 bg-gradient-to-br from-indigo-600 to-violet-600 text-white rounded-xl shadow-sm group-hover:shadow-md transition">
              <Database className="w-4 h-4" />
            </div>
            <span>
              Schema<span className="text-indigo-600">Sense</span>
            </span>
          </Link>

          <span className="hidden lg:inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80">
            <ShieldCheck className="w-3.5 h-3.5" /> Read-Only Sandbox
          </span>
        </div>

        <nav className="flex items-center gap-1 overflow-x-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname?.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl whitespace-nowrap transition-all ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200/70 shadow-2xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-indigo-600" : ""}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}

          <Link
            href="/settings"
            className="hidden sm:inline-flex items-center gap-1 ml-2 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-indigo-600/10 text-indigo-700 border border-indigo-200 hover:bg-indigo-600/15 transition"
          >
            <Sparkles className="w-3 h-3" />
            {aiBadge}
          </Link>
        </nav>
      </div>
    </header>
  );
}
