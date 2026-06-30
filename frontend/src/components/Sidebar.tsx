"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "@/lib/navigation";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-[280px] shrink-0 flex-col border-r border-[#e8e4df] bg-white/80 backdrop-blur-xl">
      <div className="border-b border-[#e8e4df] px-6 py-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">RegShift</p>
        <h1 className="mt-1 text-xl font-semibold">Change Assurance</h1>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.id}
              href={item.href}
              data-testid={`nav-${item.id}`}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm transition ${
                isActive
                  ? "bg-gradient-to-r from-orange-500/10 to-red-500/10 font-medium text-[#1a1a1a] shadow-sm"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
