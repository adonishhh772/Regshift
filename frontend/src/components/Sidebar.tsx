"use client";

import { LayoutDashboard, FileText, Package, Layers, Settings } from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "Contracts", icon: FileText, active: false },
  { label: "Change Packs", icon: Package, active: false },
  { label: "Domain Packs", icon: Layers, active: false },
  { label: "Settings", icon: Settings, active: false },
];

export function Sidebar() {
  return (
    <aside className="flex w-[280px] shrink-0 flex-col border-r border-[#e8e4df] bg-white/80 backdrop-blur-xl">
      <div className="border-b border-[#e8e4df] px-6 py-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">RegShift</p>
        <h1 className="mt-1 text-xl font-semibold">Change Assurance</h1>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              type="button"
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm transition ${
                item.active
                  ? "bg-gradient-to-r from-orange-500/10 to-red-500/10 font-medium text-[#1a1a1a] shadow-sm"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Icon size={18} />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
