import { create } from "zustand";

import type {
  AgentTraceEvent,
  BackendConnectionStatus,
  ChatMessage,
  GeneratedTest,
  SystemIdentification,
  CodePatchRecord,
  GovernanceConfig,
  GovernanceEvaluation,
  GraphEdge,
  GraphNode,
  ImpactedFile,
  IndexStatus,
  OrchestrationStatus,
  PolicyDocument,
  RiskAssessment,
  SimulationCase,
  StepStatus,
  WorkflowStep,
  WorkflowStepId,
} from "./types";

const INITIAL_STEPS: WorkflowStep[] = [
  { id: "intake", label: "Intake", status: "active" },
  { id: "contract", label: "Contract", status: "pending" },
  { id: "graph", label: "Graph", status: "pending" },
  { id: "impact", label: "Impact", status: "pending" },
  { id: "risk", label: "Risk", status: "pending" },
  { id: "tests", label: "Tests", status: "pending" },
  { id: "simulation", label: "Simulation", status: "pending" },
  { id: "pack", label: "Pack", status: "pending" },
];

interface RegShiftState {
  changeText: string;
  sessionId: string | null;
  domain: string | null;
  confidence: number | null;
  targetSystems: SystemIdentification | null;
  systemsConfirmed: boolean;
  contractYaml: string;
  contractApproved: boolean;
  indexStatus: IndexStatus | null;
  processes: string[];
  modules: string[];
  files: ImpactedFile[];
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  highlightedPath: string[];
  selectedNodeId: string | null;
  risks: RiskAssessment | null;
  tests: GeneratedTest[];
  simulationBefore: SimulationCase[];
  simulationAfter: SimulationCase[];
  simulationSummary: string;
  packMarkdown: string;
  packFilename: string;
  implementationApplied: boolean;
  implementationPatches: CodePatchRecord[];
  implementationRepoPath: string;
  governance: GovernanceEvaluation | null;
  orchestration: OrchestrationStatus | null;
  activePolicy: PolicyDocument | null;
  governanceConfig: GovernanceConfig | null;
  langfuseUiUrl: string | null;
  graphBackend: string;
  trace: AgentTraceEvent[];
  workflowTraceVersion: number;
  steps: WorkflowStep[];
  activeStep: WorkflowStepId;
  isLoading: boolean;
  error: string | null;
  chatMessages: ChatMessage[];
  backendStatus: BackendConnectionStatus;
  setChangeText: (text: string) => void;
  setContractYaml: (yaml: string) => void;
  setActiveStep: (step: WorkflowStepId) => void;
  setStepStatus: (stepId: WorkflowStepId, status: StepStatus) => void;
  setSelectedNodeId: (nodeId: string | null) => void;
  setHighlightedPath: (path: string[]) => void;
  appendTrace: (events: AgentTraceEvent[]) => void;
  bumpWorkflowTraceVersion: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetWorkflow: () => void;
  setSession: (sessionId: string, domain: string, confidence: number) => void;
  setTargetSystems: (systems: SystemIdentification | null, confirmed?: boolean) => void;
  setIndexStatus: (status: IndexStatus) => void;
  setContract: (yaml: string, approved: boolean) => void;
  setImpact: (processes: string[], modules: string[], files: ImpactedFile[]) => void;
  setGraph: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  setRisks: (risks: RiskAssessment) => void;
  setTests: (tests: GeneratedTest[]) => void;
  setSimulation: (before: SimulationCase[], after: SimulationCase[], summary: string) => void;
  setPack: (markdown: string, filename: string) => void;
  setImplementation: (applied: boolean, patches: CodePatchRecord[], repoPath: string) => void;
  setGovernance: (governance: GovernanceEvaluation) => void;
  setOrchestration: (orchestration: OrchestrationStatus) => void;
  setActivePolicy: (policy: PolicyDocument | null) => void;
  setGovernanceConfig: (config: GovernanceConfig | null) => void;
  setLangfuseUiUrl: (url: string | null) => void;
  setGraphBackend: (backend: string) => void;
  addChatMessage: (message: ChatMessage) => void;
  updateChatMessage: (messageId: string, patch: Partial<ChatMessage>) => void;
  toggleChatThinkingExpanded: (messageId: string) => void;
  setChatMessages: (messages: ChatMessage[]) => void;
  clearChatMessages: () => void;
  setBackendStatus: (status: BackendConnectionStatus) => void;
}

export const useRegShiftStore = create<RegShiftState>((set) => ({
  changeText: "",
  sessionId: null,
  domain: null,
  confidence: null,
  targetSystems: null,
  systemsConfirmed: false,
  contractYaml: "",
  contractApproved: false,
  indexStatus: null,
  processes: [],
  modules: [],
  files: [],
  graphNodes: [],
  graphEdges: [],
  highlightedPath: [],
  selectedNodeId: null,
  risks: null,
  tests: [],
  simulationBefore: [],
  simulationAfter: [],
  simulationSummary: "",
  packMarkdown: "",
  packFilename: "",
  implementationApplied: false,
  implementationPatches: [],
  implementationRepoPath: "",
  governance: null,
  orchestration: null,
  activePolicy: null,
  governanceConfig: null,
  langfuseUiUrl: null,
  graphBackend: "networkx_fallback",
  trace: [],
  workflowTraceVersion: 0,
  steps: INITIAL_STEPS,
  activeStep: "intake",
  isLoading: false,
  error: null,
  chatMessages: [],
  backendStatus: "checking",
  setChangeText: (text) => set({ changeText: text }),
  setContractYaml: (yaml) => set({ contractYaml: yaml }),
  setActiveStep: (step) => set({ activeStep: step }),
  setStepStatus: (stepId, status) =>
    set((state) => ({
      steps: state.steps.map((step) => (step.id === stepId ? { ...step, status } : step)),
    })),
  setSelectedNodeId: (nodeId) => set({ selectedNodeId: nodeId }),
  setHighlightedPath: (path) => set({ highlightedPath: path }),
  appendTrace: (events) =>
    set((state) => ({
      trace: [...state.trace, ...events.filter((event) => !state.trace.some((existing) => existing.timestamp === event.timestamp && existing.message === event.message))],
    })),
  bumpWorkflowTraceVersion: () =>
    set((state) => ({
      workflowTraceVersion: state.workflowTraceVersion + 1,
    })),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  resetWorkflow: () =>
    set({
      sessionId: null,
      domain: null,
      confidence: null,
      targetSystems: null,
      systemsConfirmed: false,
      contractYaml: "",
      contractApproved: false,
      processes: [],
      modules: [],
      files: [],
      graphNodes: [],
      graphEdges: [],
      highlightedPath: [],
      selectedNodeId: null,
      risks: null,
      tests: [],
      simulationBefore: [],
      simulationAfter: [],
      simulationSummary: "",
      packMarkdown: "",
      packFilename: "",
      implementationApplied: false,
      implementationPatches: [],
      implementationRepoPath: "",
      governance: null,
      orchestration: null,
      activePolicy: null,
      governanceConfig: null,
      langfuseUiUrl: null,
      graphBackend: "networkx_fallback",
      trace: [],
      steps: INITIAL_STEPS,
      activeStep: "intake",
      error: null,
    }),
  setSession: (sessionId, domain, confidence) => set({ sessionId, domain, confidence }),
  setTargetSystems: (targetSystems, systemsConfirmed = false) =>
    set({ targetSystems, systemsConfirmed: systemsConfirmed || targetSystems?.confirmed || false }),
  setIndexStatus: (indexStatus) => set({ indexStatus }),
  setContract: (contractYaml, contractApproved) => set({ contractYaml, contractApproved }),
  setImpact: (processes, modules, files) => set({ processes, modules, files }),
  setGraph: (graphNodes, graphEdges) => set({ graphNodes, graphEdges }),
  setRisks: (risks) => set({ risks }),
  setTests: (tests) => set({ tests }),
  setSimulation: (simulationBefore, simulationAfter, simulationSummary) =>
    set({ simulationBefore, simulationAfter, simulationSummary }),
  setPack: (packMarkdown, packFilename) => set({ packMarkdown, packFilename }),
  setImplementation: (implementationApplied, implementationPatches, implementationRepoPath) =>
    set({ implementationApplied, implementationPatches, implementationRepoPath }),
  setGovernance: (governance) => set({ governance }),
  setOrchestration: (orchestration) => set({ orchestration }),
  setActivePolicy: (activePolicy) => set({ activePolicy }),
  setGovernanceConfig: (governanceConfig) => set({ governanceConfig }),
  setLangfuseUiUrl: (langfuseUiUrl) => set({ langfuseUiUrl }),
  setGraphBackend: (graphBackend) => set({ graphBackend }),
  addChatMessage: (message) =>
    set((state) => ({
      chatMessages: [...state.chatMessages, message],
    })),
  updateChatMessage: (messageId, patch) =>
    set((state) => ({
      chatMessages: state.chatMessages.map((message) =>
        message.id === messageId ? { ...message, ...patch } : message
      ),
    })),
  toggleChatThinkingExpanded: (messageId) =>
    set((state) => ({
      chatMessages: state.chatMessages.map((message) => {
        if (message.id !== messageId || !message.thinking) {
          return message;
        }
        return {
          ...message,
          thinking: {
            ...message.thinking,
            subagentsExpanded: !message.thinking.subagentsExpanded,
          },
        };
      }),
    })),
  setChatMessages: (chatMessages) => set({ chatMessages }),
  clearChatMessages: () => set({ chatMessages: [] }),
  setBackendStatus: (backendStatus) => set({ backendStatus }),
}));
