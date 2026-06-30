"use client";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { AgentTrace } from "./AgentTrace";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen min-h-0 bg-[#FAF9F7] text-[#1a1a1a]">
      <Sidebar />
      <div className="flex min-h-0 flex-1 flex-col">
        <TopBar />
        <div className="flex min-h-0 flex-1 overflow-hidden">
          <main className="min-h-0 flex-1 overflow-y-auto p-6">{children}</main>
          <AgentTrace />
        </div>
      </div>
    </div>
  );
}
