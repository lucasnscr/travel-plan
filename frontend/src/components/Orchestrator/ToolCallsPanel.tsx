import { useState, useMemo } from "react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import { cn } from "@/utils/cn";
import { Wrench, ChevronDown, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";
import type { ToolCallEvent } from "@/types/api";

const SERVER_COLORS: Record<string, string> = {
  "weather-mcp": "bg-blue-500/15 text-blue-400 border-blue-500/20",
  "hotels-mcp": "bg-purple-500/15 text-purple-400 border-purple-500/20",
  "activities-mcp": "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
};

function JsonDisplay({ data }: { data: unknown }) {
  if (data == null) return <span className="text-slate-600 text-xs italic">null</span>;

  const json = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  const lines = json.split("\n");

  return (
    <pre className="overflow-x-auto rounded-lg bg-black/20 p-2 text-[10px] leading-relaxed">
      {lines.map((line, i) => (
        <div key={i}>
          {line.split(/("(?:[^"\\]|\\.)*")/g).map((part, j) => {
            if (j % 2 === 1) {
              // Check if it's a key (followed by colon) or string value
              const isKey = line.trimStart().startsWith(part);
              return (
                <span key={j} className={isKey ? "text-brand-300" : "text-emerald-300"}>
                  {part}
                </span>
              );
            }
            // Highlight numbers and booleans
            return (
              <span key={j}>
                {part.split(/(\b\d+\.?\d*\b|true|false|null)/g).map((sub, k) =>
                  k % 2 === 1 ? (
                    <span
                      key={k}
                      className={
                        sub === "true" || sub === "false"
                          ? "text-amber-300"
                          : sub === "null"
                            ? "text-slate-500"
                            : "text-blue-300"
                      }
                    >
                      {sub}
                    </span>
                  ) : (
                    <span key={k} className="text-slate-400">{sub}</span>
                  ),
                )}
              </span>
            );
          })}
        </div>
      ))}
    </pre>
  );
}

function ToolCallCard({ tc }: { tc: ToolCallEvent }) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon =
    tc.status === "success" ? (
      <CheckCircle className="h-3 w-3 text-emerald-400" />
    ) : tc.status === "error" ? (
      <XCircle className="h-3 w-3 text-red-400" />
    ) : (
      <Loader2 className="h-3 w-3 animate-spin text-brand-400" />
    );

  const serverClass = SERVER_COLORS[tc.server] ?? "bg-white/10 text-slate-300";

  return (
    <div
      className={cn(
        "rounded-lg border transition-colors",
        tc.status === "error"
          ? "border-red-500/20 bg-red-500/5"
          : "border-white/5 bg-white/[0.02]",
      )}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {statusIcon}
        <span className="flex-1 truncate text-xs font-medium text-slate-200">
          {tc.tool}
        </span>
        <span
          className={cn(
            "inline-flex items-center rounded-full border border-transparent px-2 py-0.5 text-[9px] font-medium",
            serverClass,
          )}
        >
          {tc.server}
        </span>
        {tc.duration_ms != null && (
          <span className="flex items-center gap-0.5 text-[10px] text-slate-500">
            <Clock className="h-2.5 w-2.5" />
            {tc.duration_ms.toFixed(0)}ms
          </span>
        )}
        <ChevronDown
          className={cn(
            "h-3 w-3 text-slate-500 transition-transform",
            expanded && "rotate-180",
          )}
        />
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-white/5 px-3 py-2 space-y-2">
          <div>
            <p className="text-[10px] font-medium text-slate-500 mb-1">Parameters</p>
            <JsonDisplay data={tc.params} />
          </div>
          {tc.result != null && (
            <div>
              <p className="text-[10px] font-medium text-slate-500 mb-1">Result</p>
              <JsonDisplay data={tc.result} />
            </div>
          )}
          {tc.error && (
            <div>
              <p className="text-[10px] font-medium text-red-400 mb-1">Error</p>
              <p className="text-xs text-red-300">{tc.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolCallsPanel() {
  const toolCalls = useOrchestratorStore((s) => s.toolCalls);

  const metrics = useMemo(() => {
    const total = toolCalls.length;
    const completed = toolCalls.filter((tc) => tc.status !== "pending");
    const successes = toolCalls.filter((tc) => tc.status === "success");
    const withDuration = completed.filter((tc) => tc.duration_ms != null);
    const avgLatency =
      withDuration.length > 0
        ? withDuration.reduce((sum, tc) => sum + (tc.duration_ms ?? 0), 0) / withDuration.length
        : 0;
    const successRate = completed.length > 0 ? (successes.length / completed.length) * 100 : 100;

    return { total, avgLatency, successRate };
  }, [toolCalls]);

  return (
    <GlassPanel className="flex flex-col space-y-3">
      <div className="flex items-center gap-2">
        <Wrench className="h-4 w-4 text-slate-400" />
        <h4 className="text-sm font-semibold text-slate-200">MCP Tool Calls</h4>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-white/[0.03] px-2.5 py-1.5 text-center">
          <p className="text-lg font-bold text-slate-100">{metrics.total}</p>
          <p className="text-[9px] text-slate-500">Total Calls</p>
        </div>
        <div className="rounded-lg bg-white/[0.03] px-2.5 py-1.5 text-center">
          <p className="text-lg font-bold text-slate-100">
            {metrics.avgLatency.toFixed(0)}
          </p>
          <p className="text-[9px] text-slate-500">Avg Latency (ms)</p>
        </div>
        <div className="rounded-lg bg-white/[0.03] px-2.5 py-1.5 text-center">
          <p
            className={cn(
              "text-lg font-bold",
              metrics.successRate >= 90
                ? "text-emerald-400"
                : metrics.successRate >= 70
                  ? "text-amber-400"
                  : "text-red-400",
            )}
          >
            {metrics.successRate.toFixed(0)}%
          </p>
          <p className="text-[9px] text-slate-500">Success Rate</p>
        </div>
      </div>

      {/* Tool call list */}
      <div className="max-h-[320px] space-y-1.5 overflow-y-auto pr-1">
        {toolCalls.length === 0 ? (
          <p className="py-8 text-center text-xs text-slate-600">
            No tool calls yet
          </p>
        ) : (
          toolCalls.map((tc) => <ToolCallCard key={tc.id} tc={tc} />)
        )}
      </div>
    </GlassPanel>
  );
}
