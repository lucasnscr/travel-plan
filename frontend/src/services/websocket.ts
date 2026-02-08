/**
 * Orchestrator WebSocket client.
 *
 * Connects to the backend /ws/orchestrator endpoint for real-time
 * events. Falls back to a timer-based simulation when the backend
 * WebSocket is unavailable.
 */

import { LINEAR_PATH, GRAPH_NODES } from "@/utils/constants";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import type {
  OrchestratorNode,
  NodeStatus,
  WsMessageType,
  ToolCallEvent,
  AgentLogEntry,
  StateSnapshot,
} from "@/types/api";

type MessageHandler = (payload: unknown) => void;

/** MCP tool call definitions for demo simulation */
const DEMO_TOOL_CALLS: Partial<
  Record<OrchestratorNode, { tool: string; server: string; params: Record<string, unknown> }[]>
> = {
  analyze_destination: [
    {
      tool: "get_weather",
      server: "weather-mcp",
      params: { destination: "Tokyo", start_date: "2026-04-01", end_date: "2026-04-05" },
    },
  ],
  search_hotels: [
    {
      tool: "search_hotels",
      server: "hotels-mcp",
      params: { destination: "Tokyo", checkin: "2026-04-01", checkout: "2026-04-05", guests: 2 },
    },
  ],
  search_activities: [
    {
      tool: "discover_activities",
      server: "activities-mcp",
      params: { destination: "Tokyo", interests: ["culture", "gastronomy"], limit: 10 },
    },
    {
      tool: "text_search",
      server: "activities-mcp",
      params: { query: "temples in Tokyo", language: "en" },
    },
  ],
  search_flights: [
    {
      tool: "search_flights",
      server: "flights-mcp",
      params: { origin: "GRU", destination: "NRT", date: "2026-04-01", passengers: 2 },
    },
  ],
};

/** State keys that change after each major node */
const STATE_CHANGES: Partial<Record<OrchestratorNode, string[]>> = {
  gather_requirements: ["destination", "dates", "budget", "traveler_profile"],
  analyze_destination: ["destination_analysis"],
  search_hotels: ["hotel_options"],
  search_activities: ["activity_options"],
  optimize_itinerary: ["optimized_itinerary"],
  calculate_budget: ["current_cost"],
  present_for_approval: ["approval_status"],
};

export class OrchestratorSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<WsMessageType, MessageHandler[]>();
  private timers: ReturnType<typeof setTimeout>[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private connected = false;
  private fallbackMode = false;

  /** Whether the WebSocket is connected to the backend */
  get isConnected(): boolean {
    return this.connected && !this.fallbackMode;
  }

  /** Connect to the backend WebSocket endpoint */
  connect(url?: string) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = url ?? `${protocol}//${window.location.host}/ws/orchestrator`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.connected = true;
        this.fallbackMode = false;
      };

      this.ws.onmessage = (e: MessageEvent) => {
        try {
          const msg = JSON.parse(e.data as string) as {
            type: WsMessageType;
            payload: unknown;
          };
          this.dispatch(msg.type, msg.payload);
          this.applyToStore(msg.type, msg.payload);
        } catch {
          // ignore malformed messages
        }
      };

      this.ws.onclose = () => {
        this.connected = false;
        // Auto-reconnect after 3s unless disconnecting intentionally
        if (!this.fallbackMode) {
          this.reconnectTimer = setTimeout(() => {
            this.connect(url);
          }, 3000);
        }
      };

      this.ws.onerror = () => {
        this.fallbackMode = true;
        this.ws?.close();
      };
    } catch {
      this.fallbackMode = true;
    }
  }

  /** Register a handler for a specific message type */
  on(type: WsMessageType, handler: MessageHandler) {
    const existing = this.handlers.get(type) ?? [];
    existing.push(handler);
    this.handlers.set(type, existing);
  }

  /** Remove a handler */
  off(type: WsMessageType, handler: MessageHandler) {
    const existing = this.handlers.get(type) ?? [];
    this.handlers.set(
      type,
      existing.filter((h) => h !== handler),
    );
  }

  /** Send a message to the backend */
  send(action: string, data?: unknown) {
    if (this.connected && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...((data as object) ?? {}) }));
    }
  }

  /** Start the demo — sends to backend or falls back to simulation */
  startDemo() {
    if (this.connected && !this.fallbackMode) {
      this.send("start_demo");
    } else {
      this.simulateProgress();
    }
  }

  /** Timer-based simulation fallback */
  simulateProgress() {
    this.stop();
    const store = useOrchestratorStore.getState();

    let delay = 0;
    let counter = 0;

    for (const node of LINEAR_PATH) {
      // Node started
      const startDelay = delay;
      const startTimer = setTimeout(() => {
        store.updateNodeStatus(node, "running");
        store.addAgentLog({
          id: `log-${counter++}`,
          node,
          type: "node_started",
          message: `Starting ${node.replace(/_/g, " ")}`,
          timestamp: Date.now(),
        });

        // Emit tool calls for this node
        const tools = DEMO_TOOL_CALLS[node];
        if (tools) {
          for (const tool of tools) {
            const toolId = `tc-${counter++}`;
            const toolStartTime = Date.now();

            store.addToolCall({
              id: toolId,
              node,
              tool: tool.tool,
              server: tool.server,
              params: tool.params,
              status: "pending",
              startedAt: toolStartTime,
            });

            store.addAgentLog({
              id: `log-${counter++}`,
              node,
              type: "tool_call",
              message: `Calling ${tool.tool} on ${tool.server}`,
              timestamp: toolStartTime,
            });

            // Complete tool call after a short delay
            const toolTimer = setTimeout(() => {
              const duration = 200 + Math.random() * 600;
              store.updateToolCall(toolId, {
                status: "success",
                duration_ms: duration,
                result: { data_source: "mock", items: Math.floor(Math.random() * 10 + 1) },
              });
            }, 300 + Math.random() * 500);
            this.timers.push(toolTimer);
          }
        }
      }, startDelay);
      this.timers.push(startTimer);

      // Node completed
      const duration = 800 + Math.random() * 1200;
      delay += duration;

      const endTimer = setTimeout(() => {
        store.updateNodeStatus(node, "completed");
        const nodeDuration = duration;
        store.addAgentLog({
          id: `log-${counter++}`,
          node,
          type: "node_completed",
          message: `Completed ${node.replace(/_/g, " ")}`,
          timestamp: Date.now(),
          duration_ms: nodeDuration,
        });

        // Emit state snapshot for nodes with state changes
        const changes = STATE_CHANGES[node];
        if (changes) {
          store.addStateSnapshot({
            node,
            timestamp: Date.now(),
            state: buildMockState(node),
            changedKeys: changes,
          });
          store.addAgentLog({
            id: `log-${counter++}`,
            node,
            type: "state_update",
            message: `State updated: ${changes.join(", ")}`,
            timestamp: Date.now(),
          });
        }
      }, delay);
      this.timers.push(endTimer);

      delay += 200;
    }
  }

  /** Stop all timers */
  stop() {
    this.timers.forEach(clearTimeout);
    this.timers = [];
  }

  /** Disconnect and clean up */
  disconnect() {
    this.stop();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.fallbackMode = true;
    this.connected = false;
    this.ws?.close();
    this.ws = null;
    this.handlers.clear();
  }

  private dispatch(type: WsMessageType, payload: unknown) {
    const handlers = this.handlers.get(type) ?? [];
    for (const handler of handlers) {
      handler(payload);
    }
  }

  private applyToStore(type: WsMessageType, payload: unknown) {
    const store = useOrchestratorStore.getState();

    switch (type) {
      case "node_status": {
        const ns = payload as unknown as { node: OrchestratorNode; status: NodeStatus };
        store.updateNodeStatus(ns.node, ns.status);
        break;
      }
      case "tool_call": {
        const tc = payload as unknown as ToolCallEvent;
        if (tc.id) {
          const existing = store.toolCalls.find((t) => t.id === tc.id);
          if (existing) {
            store.updateToolCall(tc.id, tc);
          } else {
            store.addToolCall(tc);
          }
        }
        break;
      }
      case "state_update":
        store.addStateSnapshot(payload as unknown as StateSnapshot);
        break;
      case "agent_log":
        store.addAgentLog(payload as unknown as AgentLogEntry);
        break;
    }
  }
}

/** Build a mock state snapshot for demo purposes */
function buildMockState(afterNode: OrchestratorNode): Record<string, unknown> {
  const base: Record<string, unknown> = {
    plan_id: "plan_demo_001",
    destination: "Tokyo",
    dates: { start_date: "2026-04-01", end_date: "2026-04-05" },
    budget: { total: 5000, currency: "USD", flexibility: 0.1 },
    traveler_profile: { interests: ["culture", "gastronomy"], pace: "moderate", group_size: 2 },
    revision_count: 0,
    approval_status: "pending",
    risk_flags: [],
  };

  const nodeIndex = GRAPH_NODES.indexOf(afterNode);

  if (nodeIndex >= 1) {
    base.destination_analysis = {
      forecast: [
        { date: "2026-04-01", temp_max: 18, temp_min: 10, condition: "partly_cloudy" },
        { date: "2026-04-02", temp_max: 20, temp_min: 12, condition: "sunny" },
      ],
      events: ["Cherry Blossom Festival"],
    };
  }
  if (nodeIndex >= 3) {
    base.hotel_options = [
      { id: "h1", name: "Tokyo Garden Hotel", score: 87, nightly_price_avg: 180 },
      { id: "h2", name: "Shinjuku Grand", score: 92, nightly_price_avg: 220 },
    ];
  }
  if (nodeIndex >= 4) {
    base.activity_options = [
      { id: "a1", name: "Senso-ji Temple", category: "culture", price: 0 },
      { id: "a2", name: "Tsukiji Market Tour", category: "gastronomy", price: 45 },
    ];
  }
  if (nodeIndex >= 5) {
    base.optimized_itinerary = {
      days: [
        { day: 1, activities: ["Senso-ji Temple", "Tsukiji Market Tour"] },
        { day: 2, activities: ["Meiji Shrine", "Harajuku Walk"] },
      ],
    };
  }
  if (nodeIndex >= 6) {
    base.current_cost = 2850;
  }

  return base;
}
