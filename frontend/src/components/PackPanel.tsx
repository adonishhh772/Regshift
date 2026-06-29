"use client";

import { useRegShiftStore } from "@/lib/store";

interface PackPanelProps {
  onGeneratePack: () => void;
}

export function PackPanel({ onGeneratePack }: PackPanelProps) {
  const packMarkdown = useRegShiftStore((state) => state.packMarkdown);
  const packFilename = useRegShiftStore((state) => state.packFilename);
  const isLoading = useRegShiftStore((state) => state.isLoading);
  const setError = useRegShiftStore((state) => state.setError);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(packMarkdown);
    } catch {
      setError("Failed to copy markdown");
    }
  };

  const handleDownload = () => {
    const blob = new Blob([packMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = packFilename || "change_pack.md";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section data-testid="pack-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Approval Pack</p>
        <div className="flex gap-2">
          <button
            type="button"
            data-testid="generate-pack-button"
            disabled={isLoading}
            onClick={onGeneratePack}
            className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
          >
            Generate Change Pack
          </button>
          <button
            type="button"
            data-testid="copy-markdown-button"
            disabled={!packMarkdown}
            onClick={handleCopy}
            className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
          >
            Copy Markdown
          </button>
          <button
            type="button"
            data-testid="download-pack-button"
            disabled={!packMarkdown}
            onClick={handleDownload}
            className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
          >
            Download .md
          </button>
        </div>
      </div>
      <pre
        data-testid="pack-preview"
        className="max-h-[420px] overflow-auto rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 text-xs leading-5 text-slate-700"
      >
        {packMarkdown || "Generate a change pack to preview approval-ready markdown."}
      </pre>
    </section>
  );
}
