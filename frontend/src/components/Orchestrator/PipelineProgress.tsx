import { GlassPanel } from "@/components/ui/GlassPanel";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { NodeStatus } from "./NodeStatus";
import { useOrchestrator } from "@/hooks/use-orchestrator";
import { LINEAR_PATH, NODE_DESCRIPTIONS } from "@/utils/constants";

export function PipelineProgress() {
  const { nodeStatuses, currentNode, progress } = useOrchestrator();

  return (
    <GlassPanel className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-sm font-semibold text-slate-200">
          Pipeline Progress
        </h3>
        {currentNode && (
          <span className="text-xs text-slate-500">
            {NODE_DESCRIPTIONS[currentNode]}
          </span>
        )}
      </div>

      <ProgressBar value={progress} label="Overall" />

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {LINEAR_PATH.map((node) => (
          <NodeStatus key={node} node={node} status={nodeStatuses[node]} />
        ))}
      </div>
    </GlassPanel>
  );
}
