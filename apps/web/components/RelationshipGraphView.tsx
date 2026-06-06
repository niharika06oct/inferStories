"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Alert, Button, Panel, Spinner } from "./ui";
import {
  fetchRelationshipGraph,
  type RelationshipGraphOut,
} from "../lib/api";

const GROUP_LABEL: Record<string, string> = {
  romantic: "Romantic",
  trust: "Trust",
  rivalry: "Rivalry",
  family: "Family",
  mentorship: "Mentorship",
  social: "Social",
};

/** Edge stroke colors — match CSS vars on `.relationship-graph-canvas`. */
function edgeStrokeColor(edge: RelationshipGraphOut["edges"][number]): string {
  const p = edge.sub_relationships[0];
  if (edge.sub_relationships.length === 1 && p) {
    if (p === "distrusts" || p === "distrusted") return "var(--graph-edge-distrust)";
    if (p === "loves" || p === "loved" || p === "desires" || p === "desired") {
      return "var(--graph-edge-romantic)";
    }
    if (p === "hates" || p === "hated") return "var(--graph-edge-rivalry)";
    if (p === "is_half_brother_of") return "var(--graph-edge-family)";
  }
  const key = edge.primary_relationship;
  if (key === "trust" && edge.sub_relationships.every((s) => s.includes("distrust"))) {
    return "var(--graph-edge-distrust)";
  }
  return `var(--graph-edge-${key})`;
}

function edgeDisplayLabel(edge: RelationshipGraphOut["edges"][number]): string {
  if (edge.sub_relationships.length === 1) {
    const raw = edge.sub_relationships[0].replace(/_/g, " ");
    return raw.charAt(0).toUpperCase() + raw.slice(1);
  }
  return GROUP_LABEL[edge.primary_relationship] ?? edge.primary_relationship;
}

function formatPredicates(predicates: string[]): string {
  return predicates.map((p) => p.replace(/_/g, " ")).join(", ");
}

type CharacterNodeData = {
  label: string;
  importance: number;
};

function CharacterNode({ data }: NodeProps<Node<CharacterNodeData>>) {
  const size = 56 + Math.min(48, (data.importance ?? 0) * 0.45);
  return (
    <div
      className="relationship-graph-node soft-heading"
      style={{ width: size, height: size, fontSize: size > 72 ? 13 : 11 }}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <span className="relationship-graph-node__label">{data.label}</span>
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
}

const nodeTypes = { character: CharacterNode };

function circleLayout(
  count: number,
  centerX: number,
  centerY: number,
  radius: number,
): { x: number; y: number }[] {
  if (count === 0) return [];
  if (count === 1) return [{ x: centerX, y: centerY }];
  return Array.from({ length: count }, (_, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });
}

function labelForId(
  graph: RelationshipGraphOut,
  nodeId: string,
): string {
  return graph.nodes.find((n) => n.id === nodeId)?.label ?? nodeId;
}

type RelationshipGraphViewProps = {
  storyId: number;
  onBack: () => void;
};

export function RelationshipGraphView({
  storyId,
  onBack,
}: RelationshipGraphViewProps) {
  const [graph, setGraph] = useState<RelationshipGraphOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includePreview, setIncludePreview] = useState(false);
  const [hoverEdge, setHoverEdge] = useState<
    RelationshipGraphOut["edges"][number] | null
  >(null);

  const loadGraph = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchRelationshipGraph(storyId, { includePreview })
      .then(setGraph)
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load graph");
      })
      .finally(() => setLoading(false));
  }, [storyId, includePreview]);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] };

    const positions = circleLayout(
      graph.nodes.length,
      200,
      200,
      Math.max(120, 36 + graph.nodes.length * 32),
    );

    const flowNodes: Node<CharacterNodeData>[] = graph.nodes.map((n, i) => {
      const pos = positions[i] ?? { x: 200, y: 200 };
      return {
        id: n.id,
        type: "character",
        position: pos,
        data: { label: n.label, importance: n.importance_score },
      };
    });

    const flowEdges: Edge[] = graph.edges.map((e) => {
      const color = edgeStrokeColor(e);
      const width = Math.min(5, 1.25 + e.strength * 0.22);
      const isPreview = e.status === "preview";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: edgeDisplayLabel(e),
        animated: false,
        style: {
          stroke: color,
          strokeWidth: width,
          strokeDasharray: isPreview ? "7 5" : undefined,
          opacity: isPreview ? 0.55 : 0.92,
        },
        labelStyle: {
          fill: "var(--foreground)",
          fontSize: 10,
          fontWeight: 600,
        },
        labelBgStyle: {
          fill: "var(--card)",
          fillOpacity: 0.94,
        },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 4,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color,
          width: 18,
          height: 18,
        },
        data: { edge: e },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [graph]);

  const approvedCount = graph?.meta.approved_relationship_claim_count ?? 0;
  const previewPending = graph?.meta.pending_preview_claim_count ?? 0;

  return (
    <Panel
      title="Relationship map"
      description="Approved relationship memory between characters. Approve claims in Chapter checks, then refresh."
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onBack}>
          ← Back to chapters
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void loadGraph()}
          disabled={loading}
        >
          Refresh
        </Button>
        {graph ? (
          <span className="text-xs text-muted-foreground">
            {graph.nodes.length} characters · {graph.edges.length} on map
          </span>
        ) : null}
      </div>

      {!loading && graph && graph.edges.length === 0 ? (
        <Alert title="No approved relationships yet">
          <p className="leading-relaxed">
            The map only includes <strong>approved</strong> or{" "}
            <strong>canonized</strong> relationship claims (trust, distrust, love,
            family, etc.).
          </p>
          {approvedCount === 0 && previewPending > 0 ? (
            <p className="mt-2 text-sm">
              You have {previewPending} suggested relationship claim
              {previewPending === 1 ? "" : "s"} waiting — open{" "}
              <strong>Chapter checks → New claims</strong> and click{" "}
              <strong>Approve</strong>, then refresh this map.
            </p>
          ) : null}
          {approvedCount === 0 ? (
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includePreview}
                onChange={(e) => setIncludePreview(e.target.checked)}
              />
              Show suggested claims as preview (dashed lines)
            </label>
          ) : null}
        </Alert>
      ) : null}

      {loading ? (
        <div className="flex min-h-[320px] items-center justify-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading relationship graph…
        </div>
      ) : null}

      {error ? (
        <Alert title="Could not load graph">
          <p>{error}</p>
        </Alert>
      ) : null}

      {!loading && !error && graph && graph.edges.length > 0 ? (
        <>
          {includePreview ? (
            <p className="mb-2 text-xs text-amber-700 dark:text-amber-200">
              Preview mode — dashed edges are not yet approved canon.
            </p>
          ) : null}
          <div className="relationship-graph-shell">
            <div className="relationship-graph-canvas">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.35, minZoom: 0.4, maxZoom: 1.4 }}
                minZoom={0.2}
                maxZoom={2}
                onEdgeMouseEnter={(_, edge) => {
                  const payload = edge.data as {
                    edge?: RelationshipGraphOut["edges"][number];
                  };
                  setHoverEdge(payload.edge ?? null);
                }}
                onEdgeMouseLeave={() => setHoverEdge(null)}
                nodesDraggable
                nodesConnectable={false}
                elementsSelectable
                proOptions={{ hideAttribution: true }}
              >
                <Background gap={22} size={1} />
                <Controls />
              </ReactFlow>
            </div>
            {hoverEdge ? (
              <aside className="relationship-graph-side glass-panel">
                <p className="text-sm font-semibold text-foreground">
                  {labelForId(graph, hoverEdge.source)} →{" "}
                  {labelForId(graph, hoverEdge.target)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {GROUP_LABEL[hoverEdge.primary_relationship] ??
                    hoverEdge.primary_relationship}{" "}
                  · strength {hoverEdge.strength}
                  {hoverEdge.status === "preview" ? " · preview" : ""}
                </p>
                <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs">
                  {hoverEdge.supporting_claims.map((c) => (
                    <li
                      key={c.claim_id}
                      className="rounded bg-muted/40 px-2 py-1"
                    >
                      <span className="font-medium">{c.predicate}</span>
                      {c.claim_text ? ` — ${c.claim_text}` : null}
                    </li>
                  ))}
                </ul>
              </aside>
            ) : (
              <aside className="relationship-graph-side glass-panel">
                <p className="text-xs font-medium text-muted-foreground">
                  Relationships
                </p>
                <ul className="mt-2 max-h-[420px] space-y-2 overflow-y-auto text-xs">
                  {graph.edges.map((e) => (
                    <li key={e.id} className="relationship-graph-side__item">
                      <span className="font-semibold text-foreground">
                        {labelForId(graph, e.source)}
                      </span>{" "}
                      <span className="text-muted-foreground">
                        {formatPredicates(e.sub_relationships)}
                      </span>{" "}
                      <span className="font-semibold text-foreground">
                        {labelForId(graph, e.target)}
                      </span>
                    </li>
                  ))}
                </ul>
              </aside>
            )}
          </div>
        </>
      ) : null}
    </Panel>
  );
}
