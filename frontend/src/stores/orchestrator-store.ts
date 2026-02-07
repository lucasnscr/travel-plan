import { create } from "zustand";
import type {
  OrchestratorNode,
  NodeStatus,
  OrchestratorEvent,
  ToolCallEvent,
  StateSnapshot,
  AgentLogEntry,
} from "@/types/api";
import { GRAPH_NODES } from "@/utils/constants";

interface OrchestratorState {
  nodeStatuses: Record<OrchestratorNode, NodeStatus>;
  currentNode: OrchestratorNode | null;
  events: OrchestratorEvent[];
  toolCalls: ToolCallEvent[];
  stateSnapshots: StateSnapshot[];
  agentLogs: AgentLogEntry[];
  activeFilter: OrchestratorNode | "all";

  updateNodeStatus: (node: OrchestratorNode, status: NodeStatus) => void;
  addToolCall: (tc: ToolCallEvent) => void;
  updateToolCall: (id: string, updates: Partial<ToolCallEvent>) => void;
  addStateSnapshot: (snap: StateSnapshot) => void;
  addAgentLog: (log: AgentLogEntry) => void;
  setActiveFilter: (filter: OrchestratorNode | "all") => void;
  resetPipeline: () => void;
}

function initialStatuses(): Record<OrchestratorNode, NodeStatus> {
  const statuses = {} as Record<OrchestratorNode, NodeStatus>;
  for (const node of GRAPH_NODES) {
    statuses[node] = "idle";
  }
  return statuses;
}

export const useOrchestratorStore = create<OrchestratorState>((set) => ({
  nodeStatuses: initialStatuses(),
  currentNode: null,
  events: [],
  toolCalls: [],
  stateSnapshots: [],
  agentLogs: [],
  activeFilter: "all",

  updateNodeStatus: (node, status) =>
    set((s) => ({
      nodeStatuses: { ...s.nodeStatuses, [node]: status },
      currentNode: status === "running" ? node : s.currentNode,
      events: [
        ...s.events,
        { node, status, timestamp: Date.now() },
      ],
    })),

  addToolCall: (tc) =>
    set((s) => ({ toolCalls: [...s.toolCalls, tc] })),

  updateToolCall: (id, updates) =>
    set((s) => ({
      toolCalls: s.toolCalls.map((tc) =>
        tc.id === id ? { ...tc, ...updates } : tc,
      ),
    })),

  addStateSnapshot: (snap) =>
    set((s) => ({ stateSnapshots: [...s.stateSnapshots, snap] })),

  addAgentLog: (log) =>
    set((s) => ({ agentLogs: [...s.agentLogs, log] })),

  setActiveFilter: (filter) => set({ activeFilter: filter }),

  resetPipeline: () =>
    set({
      nodeStatuses: initialStatuses(),
      currentNode: null,
      events: [],
      toolCalls: [],
      stateSnapshots: [],
      agentLogs: [],
    }),
}));
