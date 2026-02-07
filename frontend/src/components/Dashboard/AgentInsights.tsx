import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  CloudRain,
  DollarSign,
  ShieldAlert,
  Info,
  CheckCircle,
  X,
  Check,
} from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { usePlan } from "@/hooks/use-plan";
import { cn } from "@/utils/cn";

/* ------------------------------------------------------------------ */
/*  Insight types                                                      */
/* ------------------------------------------------------------------ */

interface Insight {
  id: string;
  agent: string;
  agentColor: string;
  barColor: string;
  icon: typeof CloudRain;
  message: string;
  severity: "suggestion" | "warning" | "info";
}

/* ------------------------------------------------------------------ */
/*  Insight generation                                                 */
/* ------------------------------------------------------------------ */

function generateInsights(
  plan: NonNullable<ReturnType<typeof usePlan>["plan"]>,
  budgetStatus: string,
): Insight[] {
  const insights: Insight[] = [];
  let idx = 0;

  const forecast = plan.destination_analysis?.forecast ?? [];
  const itinerary = plan.optimized_itinerary;

  // 1. Weather-based: rainy day with outdoor activities
  if (itinerary) {
    for (const day of itinerary.days) {
      const dayForecast = forecast.find((f) => f.date === day.date);
      if (!dayForecast || dayForecast.rain_chance <= 60) continue;

      // Check if any activity on this day is outdoor
      const outdoorSlot = day.slots.find((slot) => {
        const act = plan.activity_options.find((a) => a.id === slot.activity_id);
        return act && !act.indoor;
      });

      if (outdoorSlot) {
        // Find a better day (lower rain chance, no conflict)
        const betterDay = itinerary.days.find((d) => {
          const df = forecast.find((f) => f.date === d.date);
          return df && df.rain_chance < 30 && d.day_number !== day.day_number;
        });

        const suggestion = betterDay
          ? `Consider moving "${outdoorSlot.activity_name}" from Day ${day.day_number} to Day ${betterDay.day_number} — ${dayForecast.rain_chance.toFixed(0)}% rain expected.`
          : `"${outdoorSlot.activity_name}" on Day ${day.day_number} may be affected by rain (${dayForecast.rain_chance.toFixed(0)}%). Consider an indoor alternative.`;

        insights.push({
          id: `weather-${idx++}`,
          agent: "Weather Agent",
          agentColor: "text-blue-400",
          barColor: "bg-amber-500",
          icon: CloudRain,
          message: suggestion,
          severity: "suggestion",
        });
      }
    }
  }

  // 2. Budget-based
  if (budgetStatus === "over") {
    // Find most expensive selected activity
    const selectedActivities = plan.activity_options
      .filter((a) => plan.selected_activity_ids.includes(a.id) && a.price > 0)
      .sort((a, b) => b.price - a.price);

    if (selectedActivities.length > 0) {
      const expensive = selectedActivities[0]!;
      insights.push({
        id: `budget-${idx++}`,
        agent: "Budget Agent",
        agentColor: "text-amber-400",
        barColor: "bg-red-500",
        icon: DollarSign,
        message: `You're over budget. Consider removing "${expensive.name}" (${expensive.currency} ${expensive.price.toFixed(0)}) to save costs.`,
        severity: "warning",
      });
    }

    // Suggest cheaper hotel
    if (plan.selected_hotel_id) {
      const selected = plan.hotel_options.find((h) => h.id === plan.selected_hotel_id);
      const cheaper = plan.hotel_options
        .filter((h) => h.id !== plan.selected_hotel_id)
        .sort((a, b) => a.price_per_night - b.price_per_night);

      if (selected && cheaper.length > 0 && cheaper[0]!.price_per_night < selected.price_per_night) {
        const alt = cheaper[0]!;
        insights.push({
          id: `budget-hotel-${idx++}`,
          agent: "Budget Agent",
          agentColor: "text-amber-400",
          barColor: "bg-amber-500",
          icon: DollarSign,
          message: `Switch to "${alt.name}" to save ${selected.currency} ${(selected.price_per_night - alt.price_per_night).toFixed(0)}/night (${alt.reviews_score.toFixed(1)} rating).`,
          severity: "suggestion",
        });
      }
    }
  } else if (budgetStatus === "warning") {
    insights.push({
      id: `budget-warn-${idx++}`,
      agent: "Budget Agent",
      agentColor: "text-amber-400",
      barColor: "bg-amber-500",
      icon: DollarSign,
      message: "You're approaching your budget limit. Review your expenses to stay on track.",
      severity: "warning",
    });
  }

  // 3. Risk flags
  for (const flag of plan.risk_flags) {
    insights.push({
      id: `risk-${idx++}`,
      agent: "Risk Agent",
      agentColor: "text-red-400",
      barColor: "bg-red-500",
      icon: ShieldAlert,
      message: flag,
      severity: "warning",
    });
  }

  // 4. Travel advisories
  const advisories = plan.destination_analysis?.travel_advisories ?? [];
  for (const advisory of advisories) {
    insights.push({
      id: `advisory-${idx++}`,
      agent: "Destination Agent",
      agentColor: "text-blue-400",
      barColor: "bg-blue-500",
      icon: Info,
      message: advisory,
      severity: "info",
    });
  }

  return insights;
}

/* ------------------------------------------------------------------ */
/*  Insight card                                                       */
/* ------------------------------------------------------------------ */

interface InsightCardProps {
  insight: Insight;
  dismissed: boolean;
  onAccept: () => void;
  onDismiss: () => void;
  index: number;
}

function InsightCard({ insight, dismissed, onAccept, onDismiss, index }: InsightCardProps) {
  const Icon = insight.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: dismissed ? 0.4 : 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.3 }}
      className={cn(
        "relative flex overflow-hidden rounded-lg border transition-all",
        dismissed
          ? "border-white/5 bg-white/[0.02]"
          : "border-white/10 bg-white/[0.04]",
      )}
    >
      {/* Left color bar */}
      <div className={cn("w-1 shrink-0", insight.barColor)} />

      <div className="flex flex-1 flex-col gap-2 p-3">
        {/* Agent badge + icon */}
        <div className="flex items-center gap-2">
          <Icon className={cn("h-4 w-4", insight.agentColor)} />
          <Badge
            label={insight.agent}
            variant={
              insight.severity === "warning"
                ? "warning"
                : insight.severity === "suggestion"
                  ? "default"
                  : "info"
            }
          />
          {dismissed && (
            <span className="text-[10px] text-slate-600">Dismissed</span>
          )}
        </div>

        {/* Message */}
        <p className={cn(
          "text-xs leading-relaxed",
          dismissed ? "text-slate-600" : "text-slate-300",
        )}>
          {insight.message}
        </p>

        {/* Actions */}
        {!dismissed && (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={<Check className="h-3 w-3" />}
              onClick={onAccept}
              className="text-emerald-400 hover:text-emerald-300"
            >
              Accept
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<X className="h-3 w-3" />}
              onClick={onDismiss}
              className="text-slate-500 hover:text-slate-400"
            >
              Dismiss
            </Button>
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  AgentInsights                                                      */
/* ------------------------------------------------------------------ */

export function AgentInsights() {
  const { plan, budgetStatus } = usePlan();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const insights = useMemo(() => {
    if (!plan) return [];
    return generateInsights(plan, budgetStatus);
  }, [plan, budgetStatus]);

  if (!plan) return null;

  const handleAccept = (id: string) => {
    setDismissed((prev) => new Set(prev).add(id));
  };

  const handleDismiss = (id: string) => {
    setDismissed((prev) => new Set(prev).add(id));
  };

  return (
    <GlassPanel className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-brand-400" />
        <h3 className="font-heading text-sm font-semibold text-slate-200">
          Agent Insights
        </h3>
        {insights.length > 0 && (
          <Badge
            label={`${insights.length - dismissed.size} active`}
            variant={
              insights.length - dismissed.size > 0 ? "warning" : "success"
            }
          />
        )}
      </div>

      {/* Insight cards */}
      {insights.length === 0 ? (
        <div className="flex items-center gap-2 py-4 text-sm text-emerald-400/80">
          <CheckCircle className="h-4 w-4" />
          All clear — no insights at this time
        </div>
      ) : (
        <AnimatePresence>
          <div className="space-y-2">
            {insights.map((insight, i) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                dismissed={dismissed.has(insight.id)}
                onAccept={() => handleAccept(insight.id)}
                onDismiss={() => handleDismiss(insight.id)}
                index={i}
              />
            ))}
          </div>
        </AnimatePresence>
      )}
    </GlassPanel>
  );
}
