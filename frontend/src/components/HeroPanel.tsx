"use client";

export function HeroPanel() {
  return (
    <section
      data-testid="hero-panel"
      className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm"
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Change Assurance Layer</p>
      <h2 className="mt-2 text-2xl font-semibold leading-tight">
        Conduct makes legacy systems understandable. RegShift makes them safely changeable.
      </h2>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
        RegShift compiles business change into a machine-checkable Change Contract, traces impact through
        processes, modules, files, risks, tests, and approvals — with the expert in control at every step.
      </p>
      <div
        data-testid="impact-metrics"
        className="mt-5 grid gap-3 rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 md:grid-cols-3"
      >
        <Metric label="Traditional estimate" value="6–12 weeks" sub="3–5 FTEs · £80k–£250k" />
        <Metric label="RegShift assisted" value="~2 hours" sub="1 expert · approval-ready pack" highlight />
        <Metric label="Speed-up" value="40–80×" sub="Analysis & assurance phase" />
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  sub,
  highlight = false,
}: {
  label: string;
  value: string;
  sub: string;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-lg p-3 ${highlight ? "bg-gradient-to-br from-orange-50 to-red-50" : "bg-white"}`}>
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{sub}</p>
    </div>
  );
}
