import { Check, Loader2, Circle, AlertCircle } from "lucide-react";
import { cn } from "@/utils/cn";
import type { NodeStatus as NodeStatusType, OrchestratorNode } from "@/types/api";
import { NODE_LABELS } from "@/utils/constants";

interface NodeStatusProps {
  node: OrchestratorNode;
  status: NodeStatusType;
}

const statusConfig: Record<NodeStatusType, { icon: typeof Check; color: string; ring: string }> = {
  idle: { icon: Circle, color: "text-slate-600", ring: "ring-slate-700" },
  running: { icon: Loader2, color: "text-brand-400", ring: "ring-brand-500/40" },
  completed: { icon: Check, color: "text-emerald-400", ring: "ring-emerald-500/30" },
  error: { icon: AlertCircle, color: "text-red-400", ring: "ring-red-500/30" },
};

export function NodeStatus({ node, status }: NodeStatusProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-full ring-2",
          config.ring,
          status === "running" && "animate-node-pulse",
          status === "completed" && "bg-emerald-500/15",
        )}
      >
        <Icon
          className={cn(
            "h-3.5 w-3.5",
            config.color,
            status === "running" && "animate-spin",
          )}
        />
      </div>
      <span
        className={cn(
          "text-xs font-medium",
          status === "running" ? "text-brand-300" : status === "completed" ? "text-emerald-400" : "text-slate-500",
        )}
      >
        {NODE_LABELS[node]}
      </span>
    </div>
  );
}
