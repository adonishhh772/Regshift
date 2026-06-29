"use client";

import { useCallback, useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { ChangeIntake } from "@/components/ChangeIntake";
import { ContractEditor } from "@/components/ContractEditor";
import { HeroPanel } from "@/components/HeroPanel";
import { ImpactPanel } from "@/components/ImpactPanel";
import { KnowledgeGraphPanel } from "@/components/KnowledgeGraphPanel";
import { PackPanel } from "@/components/PackPanel";
import { PolicyPanel } from "@/components/PolicyPanel";
import { ProductionGatePanel } from "@/components/ProductionGatePanel";
import { RiskPanel } from "@/components/RiskPanel";
import { ScenarioCards } from "@/components/ScenarioCards";
import { SimulationPanel } from "@/components/SimulationPanel";
import { TestPanel } from "@/components/TestPanel";
import { WorkflowTracePanel } from "@/components/WorkflowTracePanel";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { api } from "@/lib/api";
import { GOLDEN_DEMO_TEXT } from "@/lib/demoScenarios";
import { useRegShiftStore } from "@/lib/store";
import type { WorkflowStepId } from "@/lib/types";

export default function DashboardPage() {
  const store = useRegShiftStore();

  useEffect(() => {
    api.indexStatus().then(store.setIndexStatus).catch(() => undefined);
    api.getHealth().then((health) => {
      store.setGraphBackend(health.neo4j.available ? "neo4j" : health.neo4j.backend);
      if (health.langfuse?.ui_url) {
        store.setLangfuseUiUrl(health.langfuse.ui_url);
      }
    }).catch(() => undefined);
  }, [store.setIndexStatus, store.setGraphBackend]);

  const runWithLoading = useCallback(
    async (action: () => Promise<void>) => {
      store.setLoading(true);
      store.setError(null);
      try {
        await action();
      } catch (error) {
        store.setError(error instanceof Error ? error.message : "Unexpected error");
      } finally {
        store.setLoading(false);
      }
    },
    [store]
  );

  const handleClassify = () =>
    runWithLoading(async () => {
      const result = await api.classify(store.changeText, store.sessionId ?? undefined);
      store.setSession(result.session_id, result.domain, result.confidence);
      store.appendTrace(result.trace);
      store.setStepStatus("intake", "completed");
      store.setStepStatus("contract", "active");
      store.setActiveStep("contract");
    });

  const handleCompileContract = () =>
    runWithLoading(async () => {
      const result = await api.generateContract(
        store.changeText,
        store.domain ?? undefined,
        store.sessionId ?? undefined
      );
      store.setSession(result.session_id, result.domain, store.confidence ?? 1);
      store.setContract(result.contract_yaml, false);
      store.appendTrace(result.trace);
      store.setStepStatus("contract", "blocked");
    });

  const handleApproveContract = () =>
    runWithLoading(async () => {
      if (!store.sessionId) return;
      const result = await api.approveContract(store.sessionId, store.contractYaml);
      store.setContract(result.contract_yaml, true);
      store.appendTrace(result.trace);
      store.setStepStatus("contract", "approved");
      store.setStepStatus("graph", "active");
      store.setActiveStep("graph");
    });

  const handleBuildGraph = () =>
    runWithLoading(async () => {
      if (!store.sessionId) return;
      const impact = await api.analyzeImpact(store.sessionId);
      const graph = await api.getGraph(store.sessionId);
      store.setImpact(impact.processes, impact.modules, impact.files);
      store.setGraph(graph.nodes, graph.edges);
      store.appendTrace(impact.trace);
      store.setStepStatus("graph", "completed");
      store.setStepStatus("impact", "completed");
      store.setStepStatus("risk", "active");
      store.setActiveStep("graph");
    });

  const handleScoreRisk = () =>
    runWithLoading(async () => {
      if (!store.sessionId) return;
      const risks = await api.scoreRisk(store.sessionId);
      store.setRisks(risks);
      store.setStepStatus("risk", "completed");
      store.setStepStatus("tests", "active");
      store.setActiveStep("risk");
    });

  const handleGenerateTests = () =>
    runWithLoading(async () => {
      const result = await api.generateTests(store.sessionId ?? undefined);
      store.setTests(result.tests);
      store.appendTrace(result.trace);
      store.setStepStatus("tests", "completed");
      store.setStepStatus("simulation", "active");
      store.setActiveStep("tests");
    });

  const handleRunSimulation = () =>
    runWithLoading(async () => {
      const result = await api.runSimulation(store.sessionId ?? undefined);
      store.setSimulation(result.before, result.after, result.summary);
      store.appendTrace(result.trace);
      store.setStepStatus("simulation", "completed");
      store.setStepStatus("pack", "active");
      store.setActiveStep("simulation");
    });

  const handleEvaluateGovernance = () =>
    runWithLoading(async () => {
      if (!store.sessionId) return;
      const evaluation = await api.evaluateGovernance(store.sessionId);
      const orchestration = await api.getOrchestrationStatus(store.sessionId);
      store.setGovernance(evaluation);
      store.setOrchestration(orchestration);
      store.appendTrace([
        {
          timestamp: new Date().toISOString(),
          message: `Production gate: ${evaluation.gate_status.toUpperCase()}`,
          status: evaluation.passed ? "completed" : "blocked",
          explanation: evaluation.summary,
          evidence_count: evaluation.checks.length,
        },
      ]);
      store.setStepStatus("simulation", "completed");
      if (evaluation.passed) {
        store.setStepStatus("pack", "active");
        store.setActiveStep("pack");
      }
    });

  const handleGeneratePack = () =>
    runWithLoading(async () => {
      if (!store.sessionId) return;
      const result = await api.generatePack(store.sessionId);
      store.setPack(result.markdown, result.filename);
      store.appendTrace(result.trace);
      store.setStepStatus("pack", "completed");
      store.setActiveStep("pack");
    });

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
    <AppShell>
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <HeroPanel />
        <WorkflowStepper steps={store.steps} activeStep={store.activeStep} onStepClick={handleStepClick} />
        <WorkflowTracePanel />
        {store.error ? (
          <div data-testid="error-banner" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {store.error}
          </div>
        ) : null}
        <ChangeIntake onClassify={handleClassify} onDemoMode={handleDemoMode} />
        <PolicyPanel />
        <ScenarioCards onSelect={handleScenarioSelect} />
        {store.activeStep === "contract" || store.contractYaml ? (
          <ContractEditor onCompile={handleCompileContract} onApprove={handleApproveContract} />
        ) : null}
        {store.contractApproved || store.contractYaml ? (
          <KnowledgeGraphPanel onBuildGraph={handleBuildGraph} contractApproved={store.contractApproved} />
        ) : null}
        {store.files.length > 0 ? <ImpactPanel /> : null}
        {store.activeStep === "risk" || store.risks ? <RiskPanel onScoreRisk={handleScoreRisk} /> : null}
        {store.activeStep === "tests" || store.tests.length > 0 ? <TestPanel onGenerateTests={handleGenerateTests} /> : null}
        {store.simulationBefore.length > 0 ? (
          <SimulationPanel onRunSimulation={handleRunSimulation} />
        ) : null}
        <ProductionGatePanel onEvaluateGovernance={handleEvaluateGovernance} />
        {store.activeStep === "pack" || store.packMarkdown ? <PackPanel onGeneratePack={handleGeneratePack} /> : null}
      </div>
    </AppShell>
  );
}
