import { useState } from "react";
import { Check, X } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { usePlan } from "@/hooks/use-plan";

export function ApprovalPanel() {
  const { approve, reject, plan } = usePlan();
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleApprove() {
    setLoading(true);
    const msg = await approve(feedback);
    setResult(msg);
    setLoading(false);
  }

  async function handleReject() {
    setLoading(true);
    const msg = await reject(feedback);
    setResult(msg);
    setLoading(false);
  }

  if (!plan) return null;

  return (
    <GlassPanel className="space-y-4">
      <div>
        <h3 className="font-heading text-lg font-semibold text-slate-100">
          Review & Approve
        </h3>
        <p className="text-sm text-slate-500">
          Review the plan and approve or request changes
        </p>
      </div>

      <Textarea
        label="Feedback (optional)"
        placeholder="Any changes you'd like? Tell us here..."
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
      />

      {result && (
        <div className="rounded-lg bg-brand-500/10 px-4 py-3 text-sm text-brand-300">
          {result}
        </div>
      )}

      <div className="flex gap-3">
        <Button
          variant="primary"
          icon={<Check className="h-4 w-4" />}
          onClick={handleApprove}
          loading={loading}
          className="flex-1"
        >
          Approve Plan
        </Button>
        <Button
          variant="danger"
          icon={<X className="h-4 w-4" />}
          onClick={handleReject}
          loading={loading}
          className="flex-1"
        >
          Request Changes
        </Button>
      </div>
    </GlassPanel>
  );
}
