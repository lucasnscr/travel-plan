import { MapPin, Calendar, DollarSign, AlertTriangle } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { usePlan } from "@/hooks/use-plan";
import { formatCurrency, formatDateRange } from "@/utils/format";

export function PlanSummaryCard() {
  const { plan, tripNights, budgetTotal, currentCost, budgetStatus } = usePlan();
  if (!plan) return null;

  return (
    <GlassPanel className="space-y-4">
      <h3 className="font-heading text-lg font-semibold text-slate-100">
        Trip Summary
      </h3>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex items-start gap-2">
          <MapPin className="mt-0.5 h-4 w-4 text-brand-400" />
          <div>
            <p className="text-xs text-slate-500">Destination</p>
            <p className="font-medium text-slate-200">{plan.destination}</p>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <Calendar className="mt-0.5 h-4 w-4 text-brand-400" />
          <div>
            <p className="text-xs text-slate-500">Dates</p>
            <p className="font-medium text-slate-200">
              {formatDateRange(plan.dates.start_date, plan.dates.end_date)}
            </p>
            <p className="text-xs text-slate-500">{tripNights} nights</p>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <DollarSign className="mt-0.5 h-4 w-4 text-brand-400" />
          <div>
            <p className="text-xs text-slate-500">Budget</p>
            <p className="font-medium text-slate-200">
              {formatCurrency(budgetTotal, plan.budget.currency)}
            </p>
          </div>
        </div>

        <div className="flex items-start gap-2">
          <DollarSign className="mt-0.5 h-4 w-4 text-brand-400" />
          <div>
            <p className="text-xs text-slate-500">Estimated Cost</p>
            <p className="font-medium text-slate-200">
              {formatCurrency(currentCost, plan.budget.currency)}
            </p>
            <Badge
              variant={budgetStatus === "ok" ? "success" : budgetStatus === "warning" ? "warning" : "danger"}
              label={budgetStatus === "ok" ? "Within budget" : budgetStatus === "warning" ? "Near limit" : "Over budget"}
            />
          </div>
        </div>
      </div>

      {plan.risk_flags.length > 0 && (
        <div className="space-y-2 border-t border-white/5 pt-3">
          <p className="flex items-center gap-1.5 text-xs font-medium text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            Risk Flags
          </p>
          <div className="flex flex-wrap gap-1.5">
            {plan.risk_flags.map((flag) => (
              <Badge key={flag} variant="warning" label={flag} />
            ))}
          </div>
        </div>
      )}
    </GlassPanel>
  );
}
