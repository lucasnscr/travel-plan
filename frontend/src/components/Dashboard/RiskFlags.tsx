import { AlertTriangle, ShieldAlert, Info } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { usePlan } from "@/hooks/use-plan";

export function RiskFlags() {
  const { plan } = usePlan();
  if (!plan) return null;

  const flags = plan.risk_flags;

  return (
    <GlassPanel className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-brand-400" />
        <h3 className="font-heading text-sm font-semibold text-slate-200">
          Risk Assessment
        </h3>
      </div>

      {flags.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-emerald-400">
          <Info className="h-4 w-4" />
          No risk flags identified
        </div>
      ) : (
        <ul className="space-y-2">
          {flags.map((flag) => (
            <li key={flag} className="flex items-start gap-2 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
              <span className="text-slate-300">{flag}</span>
            </li>
          ))}
        </ul>
      )}
    </GlassPanel>
  );
}
