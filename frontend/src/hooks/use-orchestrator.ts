import { useMemo } from "react";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import { LINEAR_PATH } from "@/utils/constants";

export function useOrchestrator() {
  const { nodeStatuses, currentNode, events, updateNodeStatus, resetPipeline } =
    useOrchestratorStore();

  const completedNodes = useMemo(
    () => LINEAR_PATH.filter((n) => nodeStatuses[n] === "completed"),
    [nodeStatuses],
  );

  const progress = useMemo(
    () => Math.round((completedNodes.length / LINEAR_PATH.length) * 100),
    [completedNodes],
  );

  const isRunning = useMemo(
    () => Object.values(nodeStatuses).some((s) => s === "running"),
    [nodeStatuses],
  );

  return {
    nodeStatuses,
    currentNode,
    events,
    completedNodes,
    progress,
    isRunning,
    updateNodeStatus,
    resetPipeline,
  };
}
