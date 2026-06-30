import type { GraphEdge, GraphNode } from "./types";

export interface LayoutPosition {
  x: number;
  y: number;
}

const TYPE_SECTOR: Record<string, number> = {
  PolicyRule: 0,
  Obligation: 1,
  Threshold: 2,
  ApprovalRole: 3,
  AgentLimit: 4,
  Package: 0,
  CodeFile: 1,
  Artifact: 2,
  Symbol: 3,
};

const ROOT_NODE_TYPES = ["PolicyDocument", "System"];

const SECTOR_SPAN = (Math.PI * 2) / 5;

export function computeNetworkLayout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number
): Map<string, LayoutPosition> {
  const positions = new Map<string, LayoutPosition>();
  if (nodes.length === 0) {
    return positions;
  }

  const centerX = width / 2;
  const centerY = height / 2;
  const rootNode =
    nodes.find((node) => ROOT_NODE_TYPES.includes(node.type)) ??
    nodes.find((node) => !edges.some((edge) => edge.target === node.id)) ??
    nodes[0];
  positions.set(rootNode.id, { x: centerX, y: centerY });

  const groupedByType = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    if (node.id === rootNode.id) {
      continue;
    }
    const bucket = groupedByType.get(node.type) ?? [];
    bucket.push(node);
    groupedByType.set(node.type, bucket);
  }

  groupedByType.forEach((typeNodes, nodeType) => {
    const sectorIndex = TYPE_SECTOR[nodeType] ?? 0;
    const sectorStart = sectorIndex * SECTOR_SPAN - Math.PI / 2;
    const radius = nodeType === "PolicyRule" ? Math.min(width, height) * 0.28 : Math.min(width, height) * 0.42;

    typeNodes.forEach((node, index) => {
      const spread = Math.min(SECTOR_SPAN * 0.85, (Math.PI / 6) * Math.max(typeNodes.length - 1, 1));
      const angleOffset = typeNodes.length === 1 ? 0 : (index / (typeNodes.length - 1) - 0.5) * spread;
      const angle = sectorStart + SECTOR_SPAN / 2 + angleOffset;
      positions.set(node.id, {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
      });
    });
  });

  resolveCollisions(positions, 96);
  relaxLinkedNodes(nodes, edges, positions, 16);
  resolveCollisions(positions, 88);
  return positions;
}

function resolveCollisions(positions: Map<string, LayoutPosition>, minDistance: number): void {
  const nodeIds = Array.from(positions.keys());
  for (let pass = 0; pass < 12; pass += 1) {
    for (let firstIndex = 0; firstIndex < nodeIds.length; firstIndex += 1) {
      for (let secondIndex = firstIndex + 1; secondIndex < nodeIds.length; secondIndex += 1) {
        const first = positions.get(nodeIds[firstIndex]);
        const second = positions.get(nodeIds[secondIndex]);
        if (!first || !second) {
          continue;
        }
        const deltaX = second.x - first.x;
        const deltaY = second.y - first.y;
        const distance = Math.hypot(deltaX, deltaY);
        if (distance >= minDistance || distance === 0) {
          continue;
        }
        const push = (minDistance - distance) / 2;
        const offsetX = (deltaX / distance) * push;
        const offsetY = (deltaY / distance) * push;
        first.x -= offsetX;
        first.y -= offsetY;
        second.x += offsetX;
        second.y += offsetY;
      }
    }
  }
}

function relaxLinkedNodes(
  nodes: GraphNode[],
  edges: GraphEdge[],
  positions: Map<string, LayoutPosition>,
  iterations: number
): void {
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    for (const edge of edges) {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) {
        continue;
      }
      const deltaX = target.x - source.x;
      const deltaY = target.y - source.y;
      const distance = Math.max(Math.hypot(deltaX, deltaY), 1);
      const desired = 140;
      const force = (distance - desired) * 0.04;
      const offsetX = (deltaX / distance) * force;
      const offsetY = (deltaY / distance) * force;
      source.x += offsetX;
      source.y += offsetY;
      target.x -= offsetX;
      target.y -= offsetY;
    }
  }
}

export function summarizeGraph(nodes: GraphNode[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const node of nodes) {
    counts[node.type] = (counts[node.type] ?? 0) + 1;
  }
  return counts;
}

export function findGraphNode(nodes: GraphNode[], nodeId: string | null): GraphNode | undefined {
  if (!nodeId) {
    return undefined;
  }
  return nodes.find((node) => node.id === nodeId);
}
