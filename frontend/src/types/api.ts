/** API request/response types and orchestrator types */

import type { TravelPlannerCore } from "./core";

export interface PlanRequest {
  destination: string;
  start_date: string;
  end_date: string;
  budget: number;
  currency: string;
  group_size: number;
  interests: string;
  audio_file?: File;
  image_file?: File;
  pdf_file?: File;
}

export interface PlanResponse {
  plan: TravelPlannerCore;
  map_url: string;
  pdf_url: string;
}

export interface ApprovalRequest {
  decision: "approved" | "rejected";
  feedback: string;
}

export interface ApprovalResponse {
  message: string;
}

export interface HealthResponse {
  status: string;
}

/** The 12 graph nodes from planner_graph.py */
export type OrchestratorNode =
  | "gather_requirements"
  | "analyze_destination"
  | "search_flights"
  | "search_hotels"
  | "search_activities"
  | "optimize_itinerary"
  | "calculate_budget"
  | "risk_and_policy_check"
  | "present_for_approval"
  | "process_feedback"
  | "book_services"
  | "generate_documents";

export type NodeStatus = "idle" | "running" | "completed" | "error";

export interface OrchestratorEvent {
  node: OrchestratorNode;
  status: NodeStatus;
  timestamp: number;
  message?: string;
}

/** MCP tool call event from WebSocket */
export interface ToolCallEvent {
  id: string;
  node: OrchestratorNode;
  tool: string;
  server: string;
  params: Record<string, unknown>;
  result?: unknown;
  status: "pending" | "success" | "error";
  error?: string;
  startedAt: number;
  duration_ms?: number;
}

/** Agent log entry for the activity timeline */
export interface AgentLogEntry {
  id: string;
  node: OrchestratorNode;
  type: "node_started" | "node_completed" | "node_error" | "tool_call" | "state_update";
  message: string;
  timestamp: number;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

/** State snapshot after a node completes */
export interface StateSnapshot {
  node: OrchestratorNode;
  timestamp: number;
  state: Record<string, unknown>;
  changedKeys: string[];
}

/** WebSocket message envelope */
export type WsMessageType = "node_status" | "tool_call" | "state_update" | "agent_log";

export interface WsMessage {
  type: WsMessageType;
  payload: OrchestratorEvent | ToolCallEvent | StateSnapshot | AgentLogEntry;
}
