import { useEffect, useState } from "react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { TripStats } from "@/components/Dashboard/TripStats";
import { WeatherOverview } from "@/components/Dashboard/WeatherOverview";
import { BudgetTracker } from "@/components/Dashboard/BudgetTracker";
import { DailyAgenda } from "@/components/Dashboard/DailyAgenda";
import { AgentInsights } from "@/components/Dashboard/AgentInsights";
import { RiskFlags } from "@/components/Dashboard/RiskFlags";
import { usePlan } from "@/hooks/use-plan";
import { getHealth } from "@/services/rest";
import { Activity, Heart } from "lucide-react";

export function DashboardPage() {
  const { plan } = usePlan();
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then(() => setHealthy(true))
      .catch(() => setHealthy(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-xl font-bold text-slate-100">
          Dashboard
        </h2>
        <div className="flex items-center gap-2">
          <Heart
            className={`h-4 w-4 ${healthy ? "text-emerald-400" : healthy === false ? "text-red-400" : "text-slate-600"}`}
          />
          <Badge
            label={healthy ? "Backend Healthy" : healthy === false ? "Backend Down" : "Checking..."}
            variant={healthy ? "success" : healthy === false ? "danger" : "default"}
          />
        </div>
      </div>

      {!plan ? (
        <GlassPanel className="flex flex-col items-center justify-center gap-3 py-16">
          <Activity className="h-12 w-12 text-slate-600" />
          <p className="text-sm text-slate-500">
            Plan a trip first to see the dashboard
          </p>
        </GlassPanel>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* TripStats — full width */}
          <div className="lg:col-span-2">
            <TripStats />
          </div>

          {/* WeatherOverview — full width */}
          <div className="lg:col-span-2">
            <WeatherOverview />
          </div>

          {/* BudgetTracker + DailyAgenda — side by side on lg */}
          <BudgetTracker />
          <DailyAgenda />

          {/* AgentInsights — full width */}
          <div className="lg:col-span-2">
            <AgentInsights />
          </div>

          {/* RiskFlags — full width */}
          <div className="lg:col-span-2">
            <RiskFlags />
          </div>
        </div>
      )}
    </div>
  );
}
