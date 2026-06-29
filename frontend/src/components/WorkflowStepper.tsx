"use client";

import type { WorkflowStep } from "@/lib/types";

interface WorkflowStepperProps {
  steps: WorkflowStep[];
  activeStep: string;
  onStepClick: (stepId: string) => void;
}

const STATUS_STYLES: Record<string, string> = {
  pending: "border-slate-200 bg-white text-slate-400",
  active: "border-orange-300 bg-gradient-to-r from-orange-50 to-red-50 text-orange-700",
  approved: "border-emerald-300 bg-emerald-50 text-emerald-700",
  blocked: "border-amber-300 bg-amber-50 text-amber-700",
  completed: "border-emerald-300 bg-emerald-50 text-emerald-700",
};

export function WorkflowStepper({ steps, activeStep, onStepClick }: WorkflowStepperProps) {
  return (
    <section data-testid="workflow-stepper" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-4 shadow-sm">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Workflow</p>
      <div className="flex flex-wrap gap-2">
        {steps.map((step, index) => (
          <button
            key={step.id}
            type="button"
            data-testid={`step-${step.id}`}
            onClick={() => onStepClick(step.id)}
            className={`flex min-w-[100px] flex-col rounded-xl border px-3 py-2 text-left transition ${
              activeStep === step.id ? "ring-2 ring-orange-200" : ""
            } ${STATUS_STYLES[step.status] ?? STATUS_STYLES.pending}`}
          >
            <span className="text-[10px] uppercase tracking-wider">Step {index + 1}</span>
            <span className="text-sm font-medium">{step.label}</span>
            <span className="text-[10px] capitalize">{step.status}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
