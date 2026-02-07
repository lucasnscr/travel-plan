import { useState } from "react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AnimatedEdge } from "./AnimatedEdge";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import {
  GRAPH_EDGES,
  NODE_LABELS,
  NODE_DESCRIPTIONS,
  GRAPH_NODES,
} from "@/utils/constants";
import { cn } from "@/utils/cn";
import type { OrchestratorNode, NodeStatus } from "@/types/api";

/** DAG node positions within viewBox 0 0 920 320 */
const NODE_POSITIONS: Record<OrchestratorNode, { x: number; y: number }> = {
  gather_requirements: { x: 80, y: 60 },
  analyze_destination: { x: 220, y: 60 },
  search_flights: { x: 370, y: 60 },
  search_hotels: { x: 520, y: 60 },
  search_activities: { x: 670, y: 60 },
  optimize_itinerary: { x: 145, y: 170 },
  calculate_budget: { x: 295, y: 170 },
  risk_and_policy_check: { x: 455, y: 170 },
  present_for_approval: { x: 615, y: 170 },
  process_feedback: { x: 615, y: 275 },
  book_services: { x: 765, y: 170 },
  generate_documents: { x: 855, y: 170 },
};

const CONDITIONAL_EDGES: Set<string> = new Set([
  "calculate_budget->search_flights",
  "present_for_approval->process_feedback",
  "process_feedback->search_flights",
  "process_feedback->search_hotels",
  "process_feedback->search_activities",
]);

const STATUS_COLORS: Record<NodeStatus, { fill: string; stroke: string; bg: string }> = {
  idle: { fill: "transparent", stroke: "#475569", bg: "#47556915" },
  running: { fill: "#f59e0b20", stroke: "#f59e0b", bg: "#f59e0b20" },
  completed: { fill: "#10b98130", stroke: "#10b981", bg: "#10b98120" },
  error: { fill: "#ef444430", stroke: "#ef4444", bg: "#ef444420" },
};

const LEGEND: { label: string; color: string }[] = [
  { label: "Idle", color: "#475569" },
  { label: "Running", color: "#f59e0b" },
  { label: "Completed", color: "#10b981" },
  { label: "Error", color: "#ef4444" },
];

export function GraphVisualizer() {
  const nodeStatuses = useOrchestratorStore((s) => s.nodeStatuses);
  const [hoveredNode, setHoveredNode] = useState<OrchestratorNode | null>(null);

  function isEdgeActive(from: OrchestratorNode, to: OrchestratorNode): boolean {
    return (
      nodeStatuses[from] === "completed" ||
      nodeStatuses[to] === "running" ||
      nodeStatuses[from] === "running"
    );
  }

  return (
    <GlassPanel className="space-y-3">
      <h3 className="font-heading text-lg font-semibold text-slate-100">
        Orchestrator Graph
      </h3>

      <div className="overflow-x-auto">
        <svg viewBox="0 0 920 320" className="w-full min-w-[750px]">
          {/* SVG Filters */}
          <defs>
            <filter id="glow-amber" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-red" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <radialGradient id="running-gradient">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.05" />
            </radialGradient>
          </defs>

          {/* Edges */}
          {GRAPH_EDGES.map(([from, to]) => {
            const f = NODE_POSITIONS[from];
            const t = NODE_POSITIONS[to];
            const key = `${from}->${to}`;
            return (
              <AnimatedEdge
                key={key}
                fromX={f.x}
                fromY={f.y}
                toX={t.x}
                toY={t.y}
                active={isEdgeActive(from, to)}
                isConditional={CONDITIONAL_EDGES.has(key)}
              />
            );
          })}

          {/* Nodes */}
          {GRAPH_NODES.map((node) => {
            const pos = NODE_POSITIONS[node];
            const status = nodeStatuses[node];
            const colors = STATUS_COLORS[status];
            const isHovered = hoveredNode === node;

            return (
              <g
                key={node}
                onMouseEnter={() => setHoveredNode(node)}
                onMouseLeave={() => setHoveredNode(null)}
                className="cursor-pointer"
              >
                {/* Outer glow ring for running */}
                {status === "running" && (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={22}
                    fill="url(#running-gradient)"
                    stroke="#f59e0b"
                    strokeWidth={0.5}
                    strokeOpacity={0.3}
                    filter="url(#glow-amber)"
                    className="animate-node-pulse"
                  />
                )}

                {/* Main circle */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={16}
                  fill={colors.bg}
                  stroke={colors.stroke}
                  strokeWidth={2}
                  filter={
                    status === "running"
                      ? "url(#glow-amber)"
                      : status === "error"
                        ? "url(#glow-red)"
                        : undefined
                  }
                  className={cn(
                    status === "running" && "animate-node-glow",
                    status === "error" && "animate-node-shake",
                  )}
                />

                {/* Status icon */}
                {status === "completed" && (
                  <path
                    d={`M ${pos.x - 5} ${pos.y} l 3.5 3.5 l 6.5 -7`}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
                {status === "error" && (
                  <>
                    <line
                      x1={pos.x - 4}
                      y1={pos.y - 4}
                      x2={pos.x + 4}
                      y2={pos.y + 4}
                      stroke="#ef4444"
                      strokeWidth={2.5}
                      strokeLinecap="round"
                    />
                    <line
                      x1={pos.x + 4}
                      y1={pos.y - 4}
                      x2={pos.x - 4}
                      y2={pos.y + 4}
                      stroke="#ef4444"
                      strokeWidth={2.5}
                      strokeLinecap="round"
                    />
                  </>
                )}
                {status === "running" && (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={4}
                    fill="#f59e0b"
                    opacity={0.8}
                  >
                    <animate
                      attributeName="r"
                      values="3;5;3"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {status === "idle" && (
                  <circle cx={pos.x} cy={pos.y} r={3} fill="#475569" opacity={0.4} />
                )}

                {/* Label */}
                <text
                  x={pos.x}
                  y={pos.y + 30}
                  textAnchor="middle"
                  className={cn(
                    "text-[9px] font-medium",
                    status === "running"
                      ? "fill-brand-400"
                      : status === "completed"
                        ? "fill-emerald-400"
                        : "fill-slate-500",
                  )}
                >
                  {NODE_LABELS[node]}
                </text>

                {/* Tooltip on hover */}
                {isHovered && (
                  <g>
                    <rect
                      x={pos.x - 80}
                      y={pos.y - 48}
                      width={160}
                      height={24}
                      rx={6}
                      fill="#1e293b"
                      stroke="#334155"
                      strokeWidth={1}
                      opacity={0.95}
                    />
                    <text
                      x={pos.x}
                      y={pos.y - 32}
                      textAnchor="middle"
                      className="fill-slate-300 text-[8px]"
                    >
                      {NODE_DESCRIPTIONS[node]}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Legend */}
          {LEGEND.map((item, i) => (
            <g key={item.label} transform={`translate(${740 + i * 45}, 308)`}>
              <circle cx={0} cy={0} r={4} fill={item.color} />
              <text x={7} y={3} className="fill-slate-600 text-[7px]">
                {item.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </GlassPanel>
  );
}
