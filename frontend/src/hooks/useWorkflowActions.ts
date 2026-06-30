"use client";

import { useCallback } from "react";

import { api } from "@/lib/api";
import { parseApiErrorMessage } from "@/lib/apiErrors";
import { streamApi } from "@/lib/streamApi";
import { useRegShiftStore } from "@/lib/store";
import type { AgentTraceEvent, AgentWorkflowResult } from "@/lib/types";

export function useWorkflowActions() {
  const store = useRegShiftStore();

  const appendLiveTrace = useCallback(
    (event: AgentTraceEvent) => {
      store.appendTrace([event]);
    },
    [store]
  );

  const runStreamWithLoading = useCallback(
    async <T,>(action: (onTrace: (event: AgentTraceEvent) => void) => Promise<T>): Promise<T> => {
      store.setLoading(true);
      store.setError(null);
      try {
        const result = await action(appendLiveTrace);
        store.bumpWorkflowTraceVersion();
        return result;
      } catch (error) {
        const message = error instanceof Error ? parseApiErrorMessage(error.message) : "Unexpected error";
        store.setError(message);
        throw error;
      } finally {
        store.setLoading(false);
      }
    },
    [appendLiveTrace, store]
  );

  const executeClassify = useCallback(async () => {
    const result = await api.classify(store.changeText, store.sessionId ?? undefined);
    store.setSession(result.session_id, result.domain, result.confidence);
    if (result.systems) {
      store.setTargetSystems(result.systems, result.systems.confirmed);
    }
    store.appendTrace(result.trace);
    store.setStepStatus("intake", "completed");
    store.setStepStatus("contract", "active");
    store.setActiveStep("contract");
    return result;
  }, [store]);

  const executeClassifyStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      const result = await streamApi.classify(store.changeText, store.sessionId ?? undefined, onTrace);
      store.setSession(result.session_id, result.domain, result.confidence);
      store.appendTrace(result.trace);
      store.setStepStatus("intake", "completed");
      store.setStepStatus("contract", "active");
      store.setActiveStep("contract");
      return result;
    },
    [store]
  );

  const executeCompileContract = useCallback(async () => {
    const result = await api.generateContract(
      store.changeText,
      store.domain ?? undefined,
      store.sessionId ?? undefined
    );
    store.setSession(result.session_id, result.domain, store.confidence ?? 1);
    store.setContract(result.contract_yaml, false);
    store.appendTrace(result.trace);
    store.setStepStatus("contract", "blocked");
    return result;
  }, [store]);

  const executeCompileContractStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      const result = await streamApi.generateContract(
        store.changeText,
        store.domain ?? undefined,
        store.sessionId ?? undefined,
        onTrace
      );
      store.setSession(result.session_id, result.domain, store.confidence ?? 1);
      store.setContract(result.contract_yaml, false);
      store.appendTrace(result.trace);
      store.setStepStatus("contract", "blocked");
      return result;
    },
    [store]
  );

  const executeApproveContract = useCallback(async () => {
    if (!store.sessionId) {
      throw new Error("No active session. Classify a change first.");
    }
    const result = await api.approveContract(store.sessionId, store.contractYaml);
    store.setContract(result.contract_yaml, true);
    store.appendTrace(result.trace);
    store.setStepStatus("contract", "approved");
    store.setStepStatus("graph", "active");
    store.setActiveStep("graph");
    return result;
  }, [store]);

  const executeApproveContractStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      if (!store.sessionId) {
        throw new Error("No active session. Classify a change first.");
      }
      const result = await streamApi.approveContract(store.sessionId, store.contractYaml, onTrace);
      store.setContract(result.contract_yaml, true);
      store.appendTrace(result.trace);
      store.setStepStatus("contract", "approved");
      store.setStepStatus("graph", "active");
      store.setActiveStep("graph");
      return result;
    },
    [store]
  );

  const executeBuildGraph = useCallback(async () => {
    if (!store.sessionId) {
      throw new Error("No active session. Classify a change first.");
    }
    const impact = await api.analyzeImpact(store.sessionId);
    const graph = await api.getGraph(store.sessionId);
    store.setImpact(impact.processes, impact.modules, impact.files);
    store.setGraph(graph.nodes, graph.edges);
    store.appendTrace(impact.trace);
    store.setStepStatus("graph", "completed");
    store.setStepStatus("impact", "completed");
    store.setStepStatus("risk", "active");
    store.setActiveStep("graph");
    return { impact, graph, trace: impact.trace };
  }, [store]);

  const executeBuildGraphStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      if (!store.sessionId) {
        throw new Error("No active session. Classify a change first.");
      }
      const impact = await streamApi.analyzeImpact(store.sessionId, onTrace);
      const graph = await api.getGraph(store.sessionId);
      store.setImpact(impact.processes, impact.modules, impact.files);
      store.setGraph(graph.nodes, graph.edges);
      store.appendTrace(impact.trace);
      store.setStepStatus("graph", "completed");
      store.setStepStatus("impact", "completed");
      store.setStepStatus("risk", "active");
      store.setActiveStep("graph");
      return { impact, graph, trace: impact.trace };
    },
    [store]
  );

  const executeScoreRisk = useCallback(async () => {
    if (!store.sessionId) {
      throw new Error("No active session. Classify a change first.");
    }
    const risks = await api.scoreRisk(store.sessionId);
    store.setRisks(risks);
    store.setStepStatus("risk", "completed");
    store.setStepStatus("tests", "active");
    store.setActiveStep("risk");
    return { ...risks, trace: [] as AgentTraceEvent[] };
  }, [store]);

  const executeScoreRiskStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      if (!store.sessionId) {
        throw new Error("No active session. Classify a change first.");
      }
      const result = await streamApi.scoreRisk(store.sessionId, onTrace);
      store.setRisks(result.assessment);
      store.appendTrace(result.trace);
      store.setStepStatus("risk", "completed");
      store.setStepStatus("tests", "active");
      store.setActiveStep("risk");
      return { ...result.assessment, trace: result.trace };
    },
    [store]
  );

  const executeGenerateTests = useCallback(async () => {
    const result = await api.generateTests(store.sessionId ?? undefined);
    store.setTests(result.tests);
    store.appendTrace(result.trace);
    store.setStepStatus("tests", "completed");
    store.setStepStatus("simulation", "active");
    store.setActiveStep("tests");
    return result;
  }, [store]);

  const executeGenerateTestsStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      const result = await streamApi.generateTests(store.sessionId ?? undefined, onTrace);
      store.setTests(result.tests);
      store.appendTrace(result.trace);
      store.setStepStatus("tests", "completed");
      store.setStepStatus("simulation", "active");
      store.setActiveStep("tests");
      return result;
    },
    [store]
  );

  const executeRunSimulation = useCallback(async () => {
    const result = await api.runSimulation(store.sessionId ?? undefined);
    store.setSimulation(result.before, result.after, result.summary);
    store.appendTrace(result.trace);
    store.setStepStatus("simulation", "completed");
    store.setStepStatus("pack", "active");
    store.setActiveStep("simulation");
    return result;
  }, [store]);

  const executeRunSimulationStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      const result = await streamApi.runSimulation(store.sessionId ?? undefined, onTrace);
      store.setSimulation(result.before, result.after, result.summary);
      store.appendTrace(result.trace);
      store.setStepStatus("simulation", "completed");
      store.setStepStatus("pack", "active");
      store.setActiveStep("simulation");
      return result;
    },
    [store]
  );

  const executeEvaluateGovernance = useCallback(async () => {
    if (!store.sessionId) {
      throw new Error("No active session. Classify a change first.");
    }
    const evaluation = await api.evaluateGovernance(store.sessionId);
    const orchestration = await api.getOrchestrationStatus(store.sessionId);
    store.setGovernance(evaluation);
    store.setOrchestration(orchestration);
    const trace: AgentTraceEvent[] = [
      {
        timestamp: new Date().toISOString(),
        message: `Production gate: ${evaluation.gate_status.toUpperCase()}`,
        status: evaluation.passed ? "completed" : "blocked",
        explanation: evaluation.summary,
        evidence_count: evaluation.checks.length,
      },
    ];
    store.appendTrace(trace);
    store.setStepStatus("simulation", "completed");
    if (evaluation.passed) {
      store.setStepStatus("pack", "active");
      store.setActiveStep("pack");
    }
    return { evaluation, trace };
  }, [store]);

  const executeEvaluateGovernanceStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      if (!store.sessionId) {
        throw new Error("No active session. Classify a change first.");
      }
      const result = await streamApi.evaluateGovernance(store.sessionId, onTrace);
      store.setGovernance(result.evaluation);
      store.setOrchestration(result.orchestration);
      store.appendTrace(result.trace);
      store.setStepStatus("simulation", "completed");
      if (result.evaluation.passed) {
        store.setStepStatus("pack", "active");
        store.setActiveStep("pack");
      }
      return { evaluation: result.evaluation, trace: result.trace };
    },
    [store]
  );

  const executeGeneratePack = useCallback(async () => {
    if (!store.sessionId) {
      throw new Error("No active session. Classify a change first.");
    }
    const result = await api.generatePack(store.sessionId);
    store.setPack(result.markdown, result.filename);
    store.appendTrace(result.trace);
    store.setStepStatus("pack", "completed");
    store.setActiveStep("pack");
    return result;
  }, [store]);

  const executeGeneratePackStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      if (!store.sessionId) {
        throw new Error("No active session. Classify a change first.");
      }
      const result = await streamApi.generatePack(store.sessionId, onTrace);
      store.setPack(result.markdown, result.filename);
      store.appendTrace(result.trace);
      store.setStepStatus("pack", "completed");
      store.setActiveStep("pack");
      return result;
    },
    [store]
  );

  const applyAgentWorkflowResult = useCallback(
    async (result: AgentWorkflowResult) => {
      const domain = result.domain ?? store.domain ?? "procurement";
      const confidence = result.confidence ?? store.confidence ?? 1;
      store.setSession(result.session_id, domain, confidence);
      store.appendTrace(result.trace);

      if (result.contract_yaml) {
        store.setContract(result.contract_yaml, result.contract_approved);
      }

      if (result.graph_node_count > 0) {
        const graph = await api.getGraph(result.session_id);
        store.setGraph(graph.nodes, graph.edges);
        store.setImpact(result.processes, result.modules, []);
        store.setStepStatus("graph", "completed");
        store.setStepStatus("impact", "completed");
      }

      if (result.tests_count > 0) {
        store.setStepStatus("tests", "completed");
      }

      if (result.simulation_summary) {
        store.setStepStatus("simulation", "completed");
      }

      if (result.pack_markdown && result.pack_filename) {
        store.setPack(result.pack_markdown, result.pack_filename);
        store.setStepStatus("pack", "completed");
        store.setActiveStep("pack");
      }

      if (result.status === "paused" && result.pause_gate === "human_approval") {
        store.setStepStatus("intake", "completed");
        store.setStepStatus("contract", "blocked");
        store.setActiveStep("contract");
      }

      if (result.status === "completed") {
        store.setStepStatus("intake", "completed");
        store.setStepStatus("contract", "approved");
        store.setStepStatus("risk", "completed");
        store.setActiveStep("pack");
      }
    },
    [store]
  );

  const executeAgentStartStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      const { changeText, sessionId } = useRegShiftStore.getState();
      if (changeText.length < 10) {
        throw new Error("Describe your business change in at least 10 characters.");
      }
      const result = await streamApi.runAgent(changeText, sessionId ?? undefined, onTrace);
      await applyAgentWorkflowResult(result);
      return result;
    },
    [applyAgentWorkflowResult]
  );

  const executeAgentResumeStream = useCallback(
    async (onTrace: (event: AgentTraceEvent) => void) => {
      const { sessionId } = useRegShiftStore.getState();
      if (!sessionId) {
        throw new Error("No active session. Describe your change first.");
      }
      const result = await streamApi.resumeAgent(sessionId, onTrace);
      await applyAgentWorkflowResult(result);
      return result;
    },
    [applyAgentWorkflowResult]
  );

  const executeApplyImplementation = useCallback(async () => {
    if (!store.sessionId) {
      throw new Error("No active session. Complete the workflow or load a change pack first.");
    }
    const packId = store.packFilename.replace(".md", "") || undefined;
    const result = await api.applyImplementation(store.sessionId, packId);
    store.appendTrace(result.trace);
    if (result.graph) {
      store.setGraph(result.graph.nodes, result.graph.edges);
      store.setStepStatus("graph", "completed");
      store.setActiveStep("graph");
    }
    store.setImplementation(result.applied, result.patches, result.repo_path);
    return result;
  }, [store]);

  const handleOpenChangePack = useCallback(() => {
    store.setActiveStep("pack");
    const preview = document.querySelector("[data-testid='pack-preview']");
    preview?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [store]);

  const executeConfirmSystems = useCallback(async () => {
    if (!store.sessionId || !store.targetSystems) {
      throw new Error("No systems identified for this session.");
    }
    const systemIds = store.targetSystems.systems.map((system) => system.system_id);
    const confirmed = await api.confirmSystems(store.sessionId, systemIds);
    store.setTargetSystems(confirmed, true);
    return confirmed;
  }, [store]);

  return {
    handleAgentStart: () => runStreamWithLoading(executeAgentStartStream),
    handleAgentResume: () => runStreamWithLoading(executeAgentResumeStream),
    handleCompileContract: () => runStreamWithLoading(executeCompileContractStream),
    handleApproveContract: () => runStreamWithLoading(executeApproveContractStream),
    handleBuildGraph: () => runStreamWithLoading(executeBuildGraphStream),
    handleScoreRisk: () => runStreamWithLoading(executeScoreRiskStream),
    handleGenerateTests: () => runStreamWithLoading(executeGenerateTestsStream),
    handleRunSimulation: () => runStreamWithLoading(executeRunSimulationStream),
    handleEvaluateGovernance: () => runStreamWithLoading(executeEvaluateGovernanceStream),
    handleGeneratePack: () => runStreamWithLoading(executeGeneratePackStream),
    handleApplyImplementation: () => runStreamWithLoading(executeApplyImplementation),
    handleOpenChangePack,
    handleConfirmSystems: () => runStreamWithLoading(executeConfirmSystems),
    executeClassify,
    executeCompileContract,
    executeApproveContract,
    executeBuildGraph,
    executeScoreRisk,
    executeGenerateTests,
    executeRunSimulation,
    executeEvaluateGovernance,
    executeGeneratePack,
    executeClassifyStream,
    executeCompileContractStream,
    executeApproveContractStream,
    executeBuildGraphStream,
    executeScoreRiskStream,
    executeGenerateTestsStream,
    executeRunSimulationStream,
    executeEvaluateGovernanceStream,
    executeAgentStartStream,
    executeAgentResumeStream,
  };
}
