"use client";

import { ChangeIntake } from "@/components/ChangeIntake";
import { ContractEditor } from "@/components/ContractEditor";
import { HeroPanel } from "@/components/HeroPanel";
import { ImplementationPanel } from "@/components/ImplementationPanel";
import { ImpactPanel } from "@/components/ImpactPanel";
import { KnowledgeGraphPanel } from "@/components/KnowledgeGraphPanel";
import { PackPanel } from "@/components/PackPanel";
import { PolicyPanel } from "@/components/PolicyPanel";
import { ProductionGatePanel } from "@/components/ProductionGatePanel";
import { RiskPanel } from "@/components/RiskPanel";
import { ScenarioCards } from "@/components/ScenarioCards";
import { SimulationPanel } from "@/components/SimulationPanel";
import { SystemsPanel } from "@/components/SystemsPanel";
import { TestPanel } from "@/components/TestPanel";
import { WorkflowTracePanel } from "@/components/WorkflowTracePanel";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { useWorkflowActions } from "@/hooks/useWorkflowActions";
import { GOLDEN_DEMO_TEXT } from "@/lib/demoScenarios";
import { useRegShiftStore } from "@/lib/store";
import type { WorkflowStepId } from "@/lib/types";

export function DemoWorkflow() {
  const store = useRegShiftStore();
  const actions = useWorkflowActions();

  const handleDemoMode = () => {
    store.resetWorkflow();
    store.setChangeText(GOLDEN_DEMO_TEXT);
    store.setActiveStep("intake");
    store.setStepStatus("intake", "active");
  };

  const handleScenarioSelect = (text: string, domain: string) => {
    store.resetWorkflow();
    store.setChangeText(text);
    store.setSession("", domain, 1);
  };

  const handleStepClick = (stepId: string) => {
    store.setActiveStep(stepId as WorkflowStepId);
  };

  return (
    <div data-testid="demo-workflow" className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="glass-card rounded-2xl border border-orange-200 bg-gradient-to-r from-orange-50 to-red-50 p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-orange-700">Demo Workflow</p>
        <h2 className="mt-2 text-2xl font-semibold">Guided assurance demo with autonomous agent</h2>
        <p className="mt-2 text-sm text-slate-600">
          Run agent to classify and compile, approve the contract, then the agent finishes impact through change pack.
        </p>
      </section>
      <HeroPanel />
      <WorkflowStepper steps={store.steps} activeStep={store.activeStep} onStepClick={handleStepClick} />
      <WorkflowTracePanel />
      {store.error ? (
        <div data-testid="error-banner" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {store.error}
        </div>
      ) : null}
      <ChangeIntake onClassify={actions.handleAgentStart} onDemoMode={handleDemoMode} />
      <SystemsPanel onConfirmSystems={actions.handleConfirmSystems} />
      <PolicyPanel showDemoLoader onPolicyIngested={() => undefined} />
      <ScenarioCards onSelect={handleScenarioSelect} />
      {store.activeStep === "contract" || store.contractYaml ? (
        <ContractEditor onCompile={actions.handleAgentStart} onApprove={actions.handleAgentResume} />
      ) : null}
      {store.contractApproved || store.contractYaml ? (
        <KnowledgeGraphPanel onBuildGraph={actions.handleAgentResume} contractApproved={store.contractApproved} />
      ) : null}
      {store.files.length > 0 ? <ImpactPanel /> : null}
      {store.activeStep === "risk" || store.risks ? <RiskPanel onScoreRisk={actions.handleAgentResume} /> : null}
      {store.activeStep === "tests" || store.tests.length > 0 ? (
        <TestPanel onGenerateTests={actions.handleAgentResume} />
      ) : null}
      {store.simulationBefore.length > 0 ? <SimulationPanel onRunSimulation={actions.handleAgentResume} /> : null}
      <ProductionGatePanel onEvaluateGovernance={actions.handleAgentResume} />
      {store.activeStep === "pack" || store.packMarkdown ? (
        <>
          <PackPanel onGeneratePack={actions.handleAgentResume} />
          <ImplementationPanel
            onApplyImplementation={actions.handleApplyImplementation}
            onOpenChangePack={actions.handleOpenChangePack}
          />
        </>
      ) : null}
    </div>
  );
}
