import { useEffect, useRef } from "react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import { NODE_LABELS, GRAPH_NODES } from "@/utils/constants";
import { cn } from "@/utils/cn";
import { Activity, Clock } from "lucide-react";
import type { AgentLogEntry, OrchestratorNode } from "@/types/api";

const TYPE_CONFIG: Record<
  AgentLogEntry["type"],
  { color: string; dotColor: string; variant: "info" | "success" | "danger" | "warning" | "default" }
> = {
  node_started: { color: "text-blue-400", dotColor: "bg-blue-400", variant: "info" },
  node_completed: { color: "text-emerald-400", dotColor: "bg-emerald-500", variant: "success" },
  node_error: { color: "text-red-400", dotColor: "bg-red-500", variant: "danger" },
  tool_call: { color: "text-amber-400", dotColor: "bg-amber-500", variant: "warning" },
  state_update: { color: "text-purple-400", dotColor: "bg-purple-500", variant: "default" },
};

function formatTimestamp(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatTypeLabel(type: AgentLogEntry["type"]): string {
  return type.replace(/_/g, " ");
}

export function AgentActivityLog() {
  const agentLogs = useOrchestratorStore((s) => s.agentLogs);
  const activeFilter = useOrchestratorStore((s) => s.activeFilter);
  const setActiveFilter = useOrchestratorStore((s) => s.setActiveFilter);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filteredLogs =
    activeFilter === "all"
      ? agentLogs.slice(-100)
      : agentLogs.filter((l) => l.node === activeFilter).slice(-100);

  // Auto-scroll on new entries
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [filteredLogs.length]);

  const filterOptions: (OrchestratorNode | "all")[] = ["all", ...GRAPH_NODES];

  return (
    <GlassPanel className="flex flex-col space-y-3">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-slate-400" />
        <h4 className="text-sm font-semibold text-slate-200">Activity Log</h4>
      </div>

      {/* Filter bar */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {filterOptions.map((f) => (
          <button
            key={f}
            onClick={() => setActiveFilter(f)}
            className={cn(
              "shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors",
              activeFilter === f
                ? "bg-brand-500/20 text-brand-300"
                : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
            )}
          >
            {f === "all" ? "All" : NODE_LABELS[f]}
          </button>
        ))}
      </div>

      {/* Timeline */}
      <div
        ref={scrollRef}
        className="max-h-[380px] overflow-y-auto space-y-0.5 pr-1"
      >
        {filteredLogs.length === 0 ? (
          <p className="py-8 text-center text-xs text-slate-600">
            Waiting for pipeline to start...
          </p>
        ) : (
          filteredLogs.map((log) => {
            const config = TYPE_CONFIG[log.type];
            return (
              <div
                key={log.id}
                className="flex items-start gap-2.5 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]"
              >
                {/* Timeline dot */}
                <div className="mt-1.5 flex flex-col items-center">
                  <div
                    className={cn("h-2 w-2 rounded-full", config.dotColor)}
                  />
                  <div className="mt-1 h-full w-px bg-white/5" />
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={config.variant}
                      label={formatTypeLabel(log.type)}
                      className="text-[9px] px-1.5 py-0"
                    />
                    <span className="text-[10px] text-slate-600">
                      {NODE_LABELS[log.node]}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-300 truncate">
                    {log.message}
                  </p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="text-[10px] text-slate-600">
                      {formatTimestamp(log.timestamp)}
                    </span>
                    {log.duration_ms != null && (
                      <span className="flex items-center gap-0.5 text-[10px] text-slate-500">
                        <Clock className="h-2.5 w-2.5" />
                        {log.duration_ms.toFixed(0)}ms
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </GlassPanel>
  );
}
