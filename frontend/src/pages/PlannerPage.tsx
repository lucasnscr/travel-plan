import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { PlannerForm } from "@/components/Chat/PlannerForm";
import { PipelineProgress } from "@/components/Orchestrator/PipelineProgress";
import { usePlan } from "@/hooks/use-plan";
import { useOrchestrator } from "@/hooks/use-orchestrator";
import { OrchestratorSocket } from "@/services/websocket";
import { Spinner } from "@/components/ui/Spinner";

const socket = new OrchestratorSocket();

export function PlannerPage() {
  const { isPlanning, response, error } = usePlan();
  const { resetPipeline } = useOrchestrator();
  const navigate = useNavigate();

  useEffect(() => {
    socket.connect();
    return () => socket.disconnect();
  }, []);

  useEffect(() => {
    if (isPlanning) {
      resetPipeline();
      socket.simulateProgress();
    }
  }, [isPlanning, resetPipeline]);

  useEffect(() => {
    if (response) {
      navigate("/results");
    }
  }, [response, navigate]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PlannerForm />

      {isPlanning && (
        <div className="space-y-4">
          <div className="flex items-center justify-center gap-3 py-4">
            <Spinner size="lg" />
            <p className="text-sm text-slate-400">
              AI is crafting your perfect trip...
            </p>
          </div>
          <PipelineProgress />
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}
    </div>
  );
}
