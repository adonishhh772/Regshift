"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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

import { PolicyGraphNode } from "@/components/PolicyGraphNode";
import { api } from "@/lib/api";
import { computeNetworkLayout, findGraphNode, summarizeGraph } from "@/lib/graphLayout";
import { normalizeFetchError } from "@/lib/networkErrors";
import type { GraphEdge, GraphNode } from "@/lib/types";

const NODE_TYPES = { policyGraph: PolicyGraphNode };
const GRAPH_HEIGHT = 640;

interface PolicyGraphCanvasProps {
  domain: string;
  policyId: string;
  refreshKey?: number;
}

function formatDomainLabel(domain: string): string {
  return domain.replace(/_/g, " ");
}

function PolicyGraphCanvas({ domain, policyId, refreshKey = 0 }: PolicyGraphCanvasProps) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [backend, setBackend] = useState<string>("unknown");
  const [graphLabel, setGraphLabel] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const { fitView } = useReactFlow();

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    api
      .getPolicyGraph(domain, policyId)
      .then((graph) => {
        setNodes(graph.nodes);
        setEdges(graph.edges);
        setBackend(graph.backend);
        setSelectedNodeId(null);
        const title = graph.policy_title ?? "Policy";
        const version = graph.policy_version ? `v${graph.policy_version}` : "";
        const graphDomain = graph.domain ?? domain;
        setGraphLabel(`${title}${version ? ` ${version}` : ""} · ${formatDomainLabel(graphDomain)}`);
      })
      .catch((loadError) => {
        setError(normalizeFetchError(loadError));
        setNodes([]);
        setEdges([]);
        setGraphLabel("");
      })
      .finally(() => setIsLoading(false));
  }, [domain, policyId, refreshKey]);

  const layoutWidth = 1100;
  const layoutPositions = useMemo(
    () => computeNetworkLayout(nodes, edges, layoutWidth, GRAPH_HEIGHT),
    [nodes, edges]
  );

  const typeCounts = useMemo(() => summarizeGraph(nodes), [nodes]);
  const selectedNode = useMemo(() => findGraphNode(nodes, selectedNodeId), [nodes, selectedNodeId]);

  const flowNodes: Node[] = useMemo(
    () =>
      nodes.map((node) => {
        const position = layoutPositions.get(node.id) ?? { x: 0, y: 0 };
        return {
          id: node.id,
          type: "policyGraph",
          data: { label: node.label, type: node.type, metadata: node.metadata },
          position,
          selected: node.id === selectedNodeId,
        };
      }),
    [layoutPositions, nodes, selectedNodeId]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      edges.map((edge) => {
        const isHighlighted =
          selectedNodeId !== null && (edge.source === selectedNodeId || edge.target === selectedNodeId);
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          animated: isHighlighted,
          style: {
            stroke: isHighlighted ? "#c4b5fd" : "#4c1d95",
            strokeWidth: isHighlighted ? 2 : 1,
            opacity: selectedNodeId && !isHighlighted ? 0.25 : 0.9,
          },
        };
      }),
    [edges, selectedNodeId]
  );

  const handleFitGraph = useCallback(() => {
    fitView({ padding: 0.35, duration: 350 });
  }, [fitView]);

  useEffect(() => {
    if (nodes.length === 0) {
      return;
    }
    const timer = window.setTimeout(handleFitGraph, 100);
    return () => window.clearTimeout(timer);
  }, [handleFitGraph, nodes, edges]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  return (
    <section
      data-testid="policy-graph-panel"
      className="glass-card overflow-hidden rounded-2xl border border-white/10 bg-[#0a0a1a] p-6 shadow-sm"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Policy Knowledge Graph</p>
          <p className="mt-1 text-sm text-slate-300" data-testid="policy-graph-label">
            {graphLabel || "Loading graph…"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            data-testid="fit-policy-graph-button"
            onClick={handleFitGraph}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10"
          >
            Fit view
          </button>
          <span className="rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1 text-xs font-medium text-purple-200">
            {backend} · {nodes.length} nodes
          </span>
        </div>
      </div>

      {Object.keys(typeCounts).length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {Object.entries(typeCounts).map(([type, count]) => (
            <span
              key={type}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-300"
            >
              {type.replace(/([A-Z])/g, " $1").trim()} · {count}
            </span>
          ))}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}

      {isLoading ? <p className="text-sm text-slate-400">Loading policy graph…</p> : null}

      {!isLoading && nodes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 bg-white/5 p-6 text-sm text-slate-400">
          No graph data for this policy.
        </div>
      ) : null}

      {nodes.length > 0 ? (
        <>
          <div
            className="overflow-hidden rounded-xl border border-white/10"
            style={{ height: GRAPH_HEIGHT, background: "radial-gradient(circle at center, #1e1b4b 0%, #0a0a1a 72%)" }}
          >
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={NODE_TYPES}
              onNodeClick={handleNodeClick}
              onPaneClick={handlePaneClick}
              nodesDraggable
              minZoom={0.25}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={28} color="#312e81" />
              <MiniMap pannable zoomable maskColor="#0a0a1a88" nodeColor="#818cf8" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>

          {selectedNode ? (
            <div
              data-testid="policy-graph-node-details"
              className="mt-4 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200"
            >
              <p className="text-xs uppercase tracking-wider text-purple-300">{selectedNode.type}</p>
              <p className="mt-1 font-medium">{selectedNode.label}</p>
              {selectedNode.metadata?.citation ? (
                <p className="mt-1 text-xs text-slate-400">{String(selectedNode.metadata.citation)}</p>
              ) : null}
            </div>
          ) : (
            <p className="mt-3 text-xs text-slate-500">Tip: click any glowing node to read its full label and citation.</p>
          )}
        </>
      ) : null}
    </section>
  );
}

interface PolicyGraphPanelProps {
  domain: string;
  policyId: string;
  refreshKey?: number;
}

export function PolicyGraphPanel({ domain, policyId, refreshKey = 0 }: PolicyGraphPanelProps) {
  const graphKey = `${domain}-${policyId}-${refreshKey}`;

  return (
    <ReactFlowProvider key={graphKey}>
      <PolicyGraphCanvas domain={domain} policyId={policyId} refreshKey={refreshKey} />
    </ReactFlowProvider>
  );
}
