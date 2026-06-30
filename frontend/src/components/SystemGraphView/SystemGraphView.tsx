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
import { Database, Loader2, Network, RefreshCw } from "lucide-react";

import { PolicyGraphNode } from "@/components/PolicyGraphNode";
import { api } from "@/lib/api";
import { computeNetworkLayout, findGraphNode, summarizeGraph } from "@/lib/graphLayout";
import { normalizeFetchError } from "@/lib/networkErrors";
import { describeSystemIngestion } from "@/lib/systemGraphLayout";
import type { GraphEdge, GraphNode, SystemSummary } from "@/lib/types";

const NODE_TYPES = { policyGraph: PolicyGraphNode };
const GRAPH_HEIGHT = 640;

const TOOLBAR_BUTTON =
  "inline-flex items-center gap-2 rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-[#FAF9F7] disabled:cursor-not-allowed disabled:opacity-50";
const TOOLBAR_BUTTON_PRIMARY =
  "inline-flex items-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-4 py-2 text-sm font-medium text-purple-700 shadow-sm transition hover:bg-purple-100 disabled:cursor-not-allowed disabled:opacity-50";
const TOOLBAR_BUTTON_ACCENT =
  "inline-flex items-center gap-2 rounded-xl border border-teal-200 bg-teal-50 px-4 py-2 text-sm font-medium text-teal-700 shadow-sm transition hover:bg-teal-100 disabled:cursor-not-allowed disabled:opacity-50";
const SELECT_CLASS =
  "rounded-xl border border-[#e8e4df] bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm outline-none ring-purple-500/10 focus:ring-2";

function formatIngestStatus(status: string | null | undefined): string {
  if (!status) {
    return "pending";
  }
  return status.replace(/_/g, " ");
}

function SystemGraphCanvas() {
  const [systems, setSystems] = useState<SystemSummary[]>([]);
  const [selectedSystemId, setSelectedSystemId] = useState<string>("");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isIngesting, setIsIngesting] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const { fitView } = useReactFlow();

  const loadSystems = useCallback(async () => {
    const response = await api.listSystems();
    setSystems(response.systems);
    setSelectedSystemId((current) => current || response.systems[0]?.id || "");
  }, []);

  const loadGraph = useCallback(async (systemId: string) => {
    if (!systemId) {
      setNodes([]);
      setEdges([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const graph = await api.getSystemGraph(systemId);
      setNodes(graph.nodes);
      setEdges(graph.edges);
      setSelectedNodeId(null);
    } catch (loadError) {
      setError(normalizeFetchError(loadError));
      setNodes([]);
      setEdges([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSystems().catch((loadError) => setError(normalizeFetchError(loadError)));
  }, [loadSystems]);

  useEffect(() => {
    loadGraph(selectedSystemId).catch((loadError) => setError(normalizeFetchError(loadError)));
  }, [selectedSystemId, loadGraph]);

  const handleSystemChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedSystemId(event.target.value);
    setIngestMessage(null);
  }, []);

  const handleRefreshGraph = useCallback(() => {
    loadSystems()
      .then(() => loadGraph(selectedSystemId))
      .catch((loadError) => setError(normalizeFetchError(loadError)));
  }, [loadGraph, loadSystems, selectedSystemId]);

  const handleIngestSelected = useCallback(async () => {
    if (!selectedSystemId) {
      return;
    }
    setIsIngesting(true);
    setError(null);
    setIngestMessage(null);
    try {
      const result = await api.ingestSystem(selectedSystemId);
      if (result.persisted) {
        setIngestMessage(
          `Ingested ${result.node_count ?? 0} nodes and ${result.file_count ?? 0} files for ${selectedSystemId}.`
        );
      } else {
        setIngestMessage(result.reason ?? `Ingest failed for ${selectedSystemId}.`);
      }
      await loadSystems();
      await loadGraph(selectedSystemId);
    } catch (ingestError) {
      setError(normalizeFetchError(ingestError));
    } finally {
      setIsIngesting(false);
    }
  }, [loadGraph, loadSystems, selectedSystemId]);

  const handleIngestAll = useCallback(async () => {
    setIsIngesting(true);
    setError(null);
    setIngestMessage(null);
    try {
      const result = await api.ingestSystems();
      setIngestMessage(`Ingested ${result.succeeded} of ${result.total} systems from catalog.`);
      await loadSystems();
      await loadGraph(selectedSystemId);
    } catch (ingestError) {
      setError(normalizeFetchError(ingestError));
    } finally {
      setIsIngesting(false);
    }
  }, [loadGraph, loadSystems, selectedSystemId]);

  const handleFitGraph = useCallback(() => {
    fitView({ padding: 0.35, duration: 350 });
  }, [fitView]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const layoutWidth = 1100;
  const layoutPositions = useMemo(
    () => computeNetworkLayout(nodes, edges, layoutWidth, GRAPH_HEIGHT),
    [nodes, edges]
  );
  const typeCounts = useMemo(() => summarizeGraph(nodes), [nodes]);
  const selectedNode = useMemo(() => findGraphNode(nodes, selectedNodeId), [nodes, selectedNodeId]);
  const selectedSummary = useMemo(
    () => systems.find((system) => system.id === selectedSystemId),
    [systems, selectedSystemId]
  );
  const ingestionInfo = useMemo(
    () => (selectedSummary ? describeSystemIngestion(selectedSummary) : null),
    [selectedSummary]
  );

  const flowNodes: Node[] = useMemo(
    () =>
      nodes.map((node) => ({
        id: node.id,
        type: "policyGraph",
        data: { label: node.label, type: node.type, metadata: node.metadata },
        position: layoutPositions.get(node.id) ?? { x: 0, y: 0 },
        selected: node.id === selectedNodeId,
      })),
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

  useEffect(() => {
    if (nodes.length === 0) {
      return;
    }
    const timer = window.setTimeout(handleFitGraph, 100);
    return () => window.clearTimeout(timer);
  }, [handleFitGraph, nodes, edges, selectedSystemId]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6" data-testid="system-graph-explorer">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">System Knowledge Graph</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">System Graph Explorer</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Browse ingested graphs for ERPNext, Salesforce, SAP, and RegShift services. Same radial layout as policy
          graphs — select a system, ingest from catalog sources, then explore nodes.
        </p>
      </section>

      <section className="glass-card overflow-hidden rounded-2xl border border-[#e8e4df] bg-white shadow-sm">
        <div className="border-b border-[#e8e4df] bg-[#FAF9F7] px-4 py-4 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <label className="flex min-w-[220px] flex-col gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">System</span>
              <select
                aria-label="Select system"
                className={SELECT_CLASS}
                data-testid="system-graph-select"
                onChange={handleSystemChange}
                value={selectedSystemId}
              >
                {systems.map((system) => (
                  <option key={system.id} value={system.id}>
                    {system.name} ({formatIngestStatus(system.ingest_status)})
                  </option>
                ))}
              </select>
            </label>

            <div className="flex flex-wrap items-center gap-2">
              <button className={TOOLBAR_BUTTON} data-testid="system-graph-fit" onClick={handleFitGraph} type="button">
                Fit view
              </button>
              <button
                className={TOOLBAR_BUTTON}
                data-testid="system-graph-refresh"
                onClick={handleRefreshGraph}
                type="button"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
              <button
                className={TOOLBAR_BUTTON_ACCENT}
                data-testid="system-graph-ingest-selected"
                disabled={isIngesting || !selectedSystemId}
                onClick={handleIngestSelected}
                type="button"
              >
                {isIngesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
                Ingest selected
              </button>
              <button
                className={TOOLBAR_BUTTON_PRIMARY}
                data-testid="system-graph-ingest"
                disabled={isIngesting}
                onClick={handleIngestAll}
                type="button"
              >
                {isIngesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Network className="h-4 w-4" />}
                Ingest all
              </button>
            </div>
          </div>

          {selectedSummary ? (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-sm">
                {selectedSummary.name}
              </span>
              <span className="rounded-full bg-purple-100 px-3 py-1 text-xs font-medium text-purple-700">
                {selectedSummary.connector}
              </span>
              <span className="rounded-full bg-[#FAF9F7] px-3 py-1 text-xs text-slate-600">
                {selectedSummary.node_count ?? 0} nodes · {selectedSummary.file_count ?? 0} files
              </span>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  selectedSummary.source_available
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {selectedSummary.source_available ? "Source available" : "Source missing"}
              </span>
            </div>
          ) : null}
        </div>

        <div className="p-4 sm:p-6">
          {Object.keys(typeCounts).length > 0 ? (
            <div className="mb-4 flex flex-wrap gap-2">
              {Object.entries(typeCounts).map(([type, count]) => (
                <span
                  key={type}
                  className="rounded-full border border-[#e8e4df] bg-[#FAF9F7] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-600"
                >
                  {type.replace(/([A-Z])/g, " $1").trim()} · {count}
                </span>
              ))}
            </div>
          ) : null}

          {ingestMessage ? (
            <div
              className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
              data-testid="system-graph-ingest-message"
            >
              {ingestMessage}
            </div>
          ) : null}

          {error ? (
            <div
              className="mb-4 rounded-xl border border-pink-200 bg-pink-50 px-4 py-3 text-sm text-pink-800"
              data-testid="system-graph-error"
            >
              {error}
            </div>
          ) : null}

          {isLoading ? <p className="text-sm text-slate-500">Loading system graph…</p> : null}

          {!isLoading && nodes.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#e8e4df] bg-[#FAF9F7] p-8 text-center text-sm text-slate-500">
              No graph data yet. Choose a system and run <strong className="text-slate-700">Ingest selected</strong> to
              build its knowledge graph.
            </div>
          ) : null}

          {nodes.length > 0 ? (
            <div
              className="overflow-hidden rounded-xl border border-[#e8e4df]"
              data-testid="system-graph-canvas"
              style={{ height: GRAPH_HEIGHT, background: "radial-gradient(circle at center, #1e1b4b 0%, #0a0a1a 72%)" }}
            >
              <ReactFlow
                edges={flowEdges}
                maxZoom={2}
                minZoom={0.25}
                nodes={flowNodes}
                nodeTypes={NODE_TYPES}
                nodesDraggable
                onNodeClick={handleNodeClick}
                onPaneClick={handlePaneClick}
                proOptions={{ hideAttribution: true }}
              >
                <Background gap={28} color="#312e81" />
                <MiniMap maskColor="#0a0a1a88" nodeColor="#818cf8" pannable zoomable />
                <Controls showInteractive={false} />
              </ReactFlow>
            </div>
          ) : null}

          {selectedNode ? (
            <div
              className="mt-4 rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-4 py-3 text-sm text-slate-700"
              data-testid="system-graph-node-details"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-purple-700">{selectedNode.type}</p>
              <p className="mt-1 font-semibold text-slate-900">{selectedNode.label}</p>
              {typeof selectedNode.metadata?.path === "string" ? (
                <p className="mt-1 font-mono text-xs text-slate-500">{selectedNode.metadata.path}</p>
              ) : null}
              {selectedNode.metadata?.snippet ? (
                <p className="mt-2 text-xs leading-relaxed text-slate-600">
                  {String(selectedNode.metadata.snippet).slice(0, 200)}
                </p>
              ) : null}
            </div>
          ) : nodes.length > 0 ? (
            <p className="mt-3 text-xs text-slate-500">Tip: click any glowing node to inspect its path and metadata.</p>
          ) : null}
        </div>
      </section>

      {ingestionInfo ? (
        <section
          className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm"
          data-testid="system-graph-ingestion-info"
        >
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Ingestion</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-900">{ingestionInfo.title}</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-600">
            {ingestionInfo.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="mt-4 text-xs text-slate-500">
            Registered in <code className="rounded bg-[#FAF9F7] px-1.5 py-0.5 text-slate-700">data/systems/catalog.yaml</code>.
            Triggered on API startup and via the ingest buttons above.
          </p>
        </section>
      ) : null}
    </div>
  );
}

export function SystemGraphView() {
  return (
    <ReactFlowProvider>
      <SystemGraphCanvas />
    </ReactFlowProvider>
  );
}

export default SystemGraphView;
