import { useEffect, useRef } from "react";
import { Workflow, Play, RotateCcw } from "lucide-react";
import { GraphVisualizer } from "./GraphVisualizer";
import { AgentActivityLog } from "./AgentActivityLog";
import { ToolCallsPanel } from "./ToolCallsPanel";
import { StateInspector } from "./StateInspector";
import { PipelineProgress } from "./PipelineProgress";
import { Button } from "@/components/ui/Button";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import { useOrchestrator } from "@/hooks/use-orchestrator";
import { OrchestratorSocket } from "@/services/websocket";

export function OrchestratorPage() {
  const resetPipeline = useOrchestratorStore((s) => s.resetPipeline);
  const { isRunning } = useOrchestrator();
  const socketRef = useRef<OrchestratorSocket | null>(null);

  useEffect(() => {
    const socket = new OrchestratorSocket();
    socketRef.current = socket;
    socket.connect();

    return () => {
      socket.disconnect();
    };
  }, []);

  function handleDemo() {
    resetPipeline();
    const socket = socketRef.current;
    if (socket) {
      socket.startDemo();
    }
  }

  function handleReset() {
    const socket = socketRef.current;
    if (socket) {
      socket.stop();
    }
    resetPipeline();
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500/20 to-brand-600/10">
            <Workflow className="h-4 w-4 text-brand-400" />
          </div>
          <h2 className="font-heading text-lg font-bold text-slate-100">
            Orchestrator Observability
          </h2>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<RotateCcw className="h-3.5 w-3.5" />}
            onClick={handleReset}
            disabled={isRunning}
          >
            Reset
          </Button>
          <Button
            size="sm"
            icon={<Play className="h-3.5 w-3.5" />}
            onClick={handleDemo}
            disabled={isRunning}
          >
            Demo
          </Button>
        </div>
      </div>

      {/* Progress bar */}
      <PipelineProgress />

      {/* Graph */}
      <GraphVisualizer />

      {/* 3-column panels */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <AgentActivityLog />
        <ToolCallsPanel />
        <StateInspector />
      </div>
    </div>
  );
}
