"use client";

import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import { GraphFlowNode } from "@/components/GraphFlowNode";
import { useRegShiftStore } from "@/lib/store";

const NODE_TYPES = { regshift: GraphFlowNode };

const LEGEND_ITEMS = [
  { type: "Obligation", color: "#fee2e2" },
  { type: "BusinessProcess", color: "#dbeafe" },
  { type: "ERPModule", color: "#e0e7ff" },
  { type: "File", color: "#f3f4f6" },
  { type: "SystemKGFile", color: "#bae6fd" },
  { type: "TargetSystem", color: "#ddd6fe" },
  { type: "Risk", color: "#fecaca" },
  { type: "Test", color: "#d1fae5" },
  { type: "ApprovalRole", color: "#fce7f3" },
  { type: "ImplementationPlan", color: "#ccfbf1" },
  { type: "CodeChange", color: "#a5f3fc" },
];

interface KnowledgeGraphPanelProps {
  onBuildGraph: () => void;
  contractApproved: boolean;
}

function KnowledgeGraphCanvas({ onBuildGraph, contractApproved }: KnowledgeGraphPanelProps) {
  const graphNodes = useRegShiftStore((state) => state.graphNodes);
  const graphEdges = useRegShiftStore((state) => state.graphEdges);
  const highlightedPath = useRegShiftStore((state) => state.highlightedPath);
  const selectedNodeId = useRegShiftStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useRegShiftStore((state) => state.setSelectedNodeId);
  const setHighlightedPath = useRegShiftStore((state) => state.setHighlightedPath);
  const isLoading = useRegShiftStore((state) => state.isLoading);
  const { fitView } = useReactFlow();

  const nodes: Node[] = useMemo(
    () =>
      graphNodes.map((node, index) => ({
        id: node.id,
        type: "regshift",
        data: { label: node.label, type: node.type, metadata: node.metadata },
        position: {
          x: Number(node.metadata?.x ?? (index % 4) * 240),
          y: Number(node.metadata?.y ?? Math.floor(index / 4) * 130),
        },
        style: {
          opacity: highlightedPath.length > 0 && !highlightedPath.includes(node.id) ? 0.25 : 1,
        },
      })),
    [graphNodes, highlightedPath]
  );

  const edges: Edge[] = useMemo(
    () =>
      graphEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        animated: highlightedPath.includes(edge.source) && highlightedPath.includes(edge.target),
        style: {
          stroke:
            highlightedPath.includes(edge.source) && highlightedPath.includes(edge.target) ? "#f97316" : "#94a3b8",
          strokeWidth: highlightedPath.includes(edge.source) && highlightedPath.includes(edge.target) ? 2.5 : 1.5,
        },
        labelStyle: { fontSize: 9, fill: "#64748b" },
      })),
    [graphEdges, highlightedPath]
  );

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
      const nodeData = graphNodes.find((graphNode) => graphNode.id === node.id);
      if (nodeData?.type === "Obligation") {
        const path = traceImpactPath(node.id, graphNodes, graphEdges);
        setHighlightedPath(path);
      }
    },
    [graphEdges, graphNodes, setHighlightedPath, setSelectedNodeId]
  );

  const handleTraceFirstObligation = useCallback(() => {
    const obligation = graphNodes.find((node) => node.type === "Obligation");
    if (!obligation) return;
    setSelectedNodeId(obligation.id);
    setHighlightedPath(traceImpactPath(obligation.id, graphNodes, graphEdges));
    window.setTimeout(() => fitView({ padding: 0.2, duration: 400 }), 50);
  }, [fitView, graphEdges, graphNodes, setHighlightedPath, setSelectedNodeId]);

  const handleClearHighlight = useCallback(() => {
    setHighlightedPath([]);
    setSelectedNodeId(null);
  }, [setHighlightedPath, setSelectedNodeId]);

  const selectedNode = graphNodes.find((node) => node.id === selectedNodeId);
  const hasGraph = nodes.length > 0;

  return (
    <section
      data-testid="knowledge-graph-panel"
      className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Knowledge Graph</p>
          <p className="mt-1 text-sm text-slate-600">
            NetworkX impact graph — business intent to code, risk, tests, and approvals
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasGraph ? (
            <>
              <button
                type="button"
                data-testid="trace-impact-button"
                onClick={handleTraceFirstObligation}
                className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm"
              >
                Trace Impact Path
              </button>
              <button
                type="button"
                onClick={handleClearHighlight}
                className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm"
              >
                Clear Highlight
              </button>
            </>
          ) : null}
          <button
            type="button"
            data-testid="build-graph-button"
            disabled={isLoading || !contractApproved}
            onClick={onBuildGraph}
            className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
          >
            {hasGraph ? "Rebuild Graph" : "Build Knowledge Graph"}
          </button>
        </div>
      </div>

      {hasGraph ? (
        <div className="mb-3 flex flex-wrap gap-3 text-xs text-slate-600">
          <span data-testid="graph-node-count" className="rounded-full bg-[#FAF9F7] px-3 py-1">
            {graphNodes.length} nodes
          </span>
          <span data-testid="graph-edge-count" className="rounded-full bg-[#FAF9F7] px-3 py-1">
            {graphEdges.length} edges
          </span>
          {highlightedPath.length > 0 ? (
            <span className="rounded-full bg-orange-50 px-3 py-1 text-orange-700">
              Tracing {highlightedPath.length} steps
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="h-[520px] overflow-hidden rounded-xl border border-[#e8e4df] bg-[#FAF9F7]">
        {hasGraph ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            onNodeClick={handleNodeClick}
            fitView
            minZoom={0.2}
            maxZoom={1.5}
          >
            <Background gap={20} color="#e8e4df" />
            <MiniMap pannable zoomable />
            <Controls />
          </ReactFlow>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-slate-500">
            <p>Approve the Change Contract, then build the knowledge graph.</p>
            <p className="text-xs">Graph shows: Obligation → Process → Module → File → Risk → Test → Approval</p>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {LEGEND_ITEMS.map((item) => (
          <span
            key={item.type}
            className="rounded-full border border-[#e8e4df] px-2 py-1 text-[10px] uppercase tracking-wider"
            style={{ backgroundColor: item.color }}
          >
            {item.type}
          </span>
        ))}
      </div>

      {selectedNode ? (
        <div data-testid="node-details" className="mt-4 rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 text-sm">
          <p className="font-medium">{selectedNode.label}</p>
          <p className="mt-1 text-xs uppercase tracking-wider text-slate-500">{selectedNode.type}</p>
          {selectedNode.metadata?.path ? (
            <p className="mt-2 font-mono text-xs text-slate-600">{String(selectedNode.metadata.path)}</p>
          ) : null}
          {selectedNode.metadata?.file_path ? (
            <p className="mt-2 font-mono text-xs text-slate-600">{String(selectedNode.metadata.file_path)}</p>
          ) : null}
          {selectedNode.metadata?.description ? (
            <p className="mt-2 text-xs text-slate-600">{String(selectedNode.metadata.description)}</p>
          ) : null}
          {selectedNode.metadata?.snippet ? (
            <p className="mt-2 text-xs text-slate-600">{String(selectedNode.metadata.snippet)}</p>
          ) : null}
          {selectedNode.type === "Obligation" ? (
            <p className="mt-2 text-xs text-orange-700">Click Trace Impact Path to highlight the full assurance chain</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function KnowledgeGraphPanel(props: KnowledgeGraphPanelProps) {
  return (
    <ReactFlowProvider>
      <KnowledgeGraphCanvas {...props} />
    </ReactFlowProvider>
  );
}

function traceImpactPath(
  obligationId: string,
  nodes: { id: string; type: string }[],
  edges: { source: string; target: string }[]
): string[] {
  const adjacency: Record<string, string[]> = {};
  edges.forEach((edge) => {
    adjacency[edge.source] = adjacency[edge.source] ?? [];
    adjacency[edge.source].push(edge.target);
  });

  const typeMap = Object.fromEntries(nodes.map((node) => [node.id, node.type]));
  const path = [obligationId];
  let current = obligationId;

  for (const preferredType of [
    "BusinessProcess",
    "ERPModule",
    "File",
    "CodeChange",
    "Risk",
    "Test",
    "ApprovalRole",
    "ImplementationPlan",
  ]) {
    const neighbor = (adjacency[current] ?? []).find((target) => typeMap[target] === preferredType);
    if (neighbor) {
      path.push(neighbor);
      current = neighbor;
    }
  }

  return path;
}
