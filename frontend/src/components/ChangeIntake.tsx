"use client";

import { useRegShiftStore } from "@/lib/store";

interface ChangeIntakeProps {
  onClassify: () => void;
  onDemoMode: () => void;
}

export function ChangeIntake({ onClassify, onDemoMode }: ChangeIntakeProps) {
  const changeText = useRegShiftStore((state) => state.changeText);
  const setChangeText = useRegShiftStore((state) => state.setChangeText);
  const domain = useRegShiftStore((state) => state.domain);
  const confidence = useRegShiftStore((state) => state.confidence);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  return (
    <section data-testid="change-intake" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Change Request</p>
        <button
          type="button"
          data-testid="demo-mode-button"
          onClick={onDemoMode}
          className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm"
        >
          Demo Mode
        </button>
      </div>
      <textarea
        data-testid="change-input"
        value={changeText}
        onChange={(event) => setChangeText(event.target.value)}
        rows={5}
        placeholder="Describe the business change..."
        className="glass-input w-full rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 text-sm outline-none ring-orange-500/10 focus:ring-2"
      />
      <div className="mt-4 flex items-center justify-between">
        <div className="text-sm text-slate-600">
          {domain ? (
            <span data-testid="classified-domain">
              Domain: <strong>{domain}</strong> ({Math.round((confidence ?? 0) * 100)}% confidence)
            </span>
          ) : (
            "Not classified yet"
          )}
        </div>
        <button
          type="button"
          data-testid="classify-button"
          disabled={isLoading || changeText.length < 10}
          onClick={onClassify}
          className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
        >
          Classify Change
        </button>
      </div>
    </section>
  );
}
