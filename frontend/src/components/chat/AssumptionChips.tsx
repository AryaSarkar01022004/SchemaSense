import React from "react";
import { Info } from "lucide-react";

interface AssumptionChipsProps {
  assumptions: string[];
}

export default function AssumptionChips({ assumptions }: AssumptionChipsProps) {
  if (!assumptions || assumptions.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 mb-3">
      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">
        <Info className="w-3.5 h-3.5 text-indigo-500" /> Assumptions:
      </span>
      {assumptions.map((item, idx) => (
        <span
          key={idx}
          className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100 shadow-2xs"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

