import { useMemo, useEffect, useRef, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { motion } from "framer-motion";
import { Hotel, MapPin, Car, UtensilsCrossed } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { usePlan } from "@/hooks/use-plan";
import { formatCurrency } from "@/utils/format";

/* ------------------------------------------------------------------ */
/*  Count-up hook                                                      */
/* ------------------------------------------------------------------ */

function useCountUp(target: number, duration = 1500) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(0);

  useEffect(() => {
    if (target === 0) {
      setValue(0);
      return;
    }

    const start = performance.now();

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}

/* ------------------------------------------------------------------ */
/*  Category configs                                                   */
/* ------------------------------------------------------------------ */

const CATEGORIES = [
  { key: "hotels",     label: "Hotels",      color: "#3b82f6", icon: Hotel },
  { key: "activities", label: "Activities",   color: "#f59e0b", icon: MapPin },
  { key: "transport",  label: "Transport",    color: "#22c55e", icon: Car },
  { key: "food",       label: "Food & Drink", color: "#8b5cf6", icon: UtensilsCrossed },
] as const;

/* ------------------------------------------------------------------ */
/*  Custom tooltip                                                     */
/* ------------------------------------------------------------------ */

function DonutTooltip({ active, payload, currency }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number }>;
  currency: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0]!;
  return (
    <div className="rounded-lg border border-white/10 bg-surface-900/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      <span className="text-slate-300">{item.name}: </span>
      <span className="font-semibold text-slate-100">
        {formatCurrency(item.value, currency)}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  BudgetTracker                                                      */
/* ------------------------------------------------------------------ */

export function BudgetTracker() {
  const { plan, tripNights, selectedHotel, budgetTotal, budgetStatus } = usePlan();
  if (!plan) return null;

  const currency = plan.budget.currency;

  // Compute category costs
  const costs = useMemo(() => {
    const hotelCost = selectedHotel
      ? selectedHotel.price_per_night * tripNights
      : 0;

    const activityCost = plan.activity_options
      .filter((a) => plan.selected_activity_ids.includes(a.id))
      .reduce((sum, a) => sum + a.price, 0);

    // Transport heuristic: sum of travel_time minutes × 0.5 unit of currency
    let transportCost = 0;
    if (plan.optimized_itinerary) {
      for (const day of plan.optimized_itinerary.days) {
        for (const slot of day.slots) {
          transportCost += slot.travel_time_from_previous_minutes * 0.5;
        }
      }
    }
    transportCost = Math.round(transportCost);

    // Food estimate: 25% of budget
    const foodCost = Math.max(0, Math.round(budgetTotal * 0.25));

    return { hotelCost, activityCost, transportCost, foodCost };
  }, [plan, selectedHotel, tripNights, budgetTotal]);

  const totalSpent = costs.hotelCost + costs.activityCost + costs.transportCost + costs.foodCost;

  // Chart data — filter out zero categories
  const chartData = useMemo(() => {
    const items = [
      { name: "Hotels", value: costs.hotelCost },
      { name: "Activities", value: costs.activityCost },
      { name: "Transport", value: costs.transportCost },
      { name: "Food & Drink", value: costs.foodCost },
    ];
    return items.filter((d) => d.value > 0);
  }, [costs]);

  // Top 3 most expensive items
  const topExpensive = useMemo(() => {
    const items: Array<{ name: string; cost: number; type: string }> = [];

    if (selectedHotel) {
      items.push({
        name: selectedHotel.name,
        cost: selectedHotel.price_per_night * tripNights,
        type: "hotel",
      });
    }

    for (const a of plan.activity_options) {
      if (plan.selected_activity_ids.includes(a.id) && a.price > 0) {
        items.push({ name: a.name, cost: a.price, type: "activity" });
      }
    }

    return items.sort((a, b) => b.cost - a.cost).slice(0, 3);
  }, [plan, selectedHotel, tripNights]);

  // Count-up animation
  const animTotal = useCountUp(Math.round(totalSpent));
  const progressPct = budgetTotal > 0 ? (totalSpent / budgetTotal) * 100 : 0;
  const progressVariant = budgetStatus === "ok" ? "success" : budgetStatus === "warning" ? "warning" : "default";

  return (
    <GlassPanel className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-sm font-semibold text-slate-200">
          Budget
        </h3>
        <motion.span
          className="font-heading text-lg font-bold tabular-nums text-slate-100"
          key={animTotal}
        >
          {formatCurrency(animTotal, currency)}
        </motion.span>
      </div>

      {/* Donut chart with center label */}
      <div className="relative">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
              strokeWidth={0}
            >
              {chartData.map((entry) => {
                const cat = CATEGORIES.find((c) => c.label === entry.name);
                return (
                  <Cell
                    key={entry.name}
                    fill={cat?.color ?? "#64748b"}
                    opacity={0.85}
                  />
                );
              })}
            </Pie>
            <Tooltip content={<DonutTooltip currency={currency} />} />
          </PieChart>
        </ResponsiveContainer>

        {/* Center label */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-[10px] text-slate-500">of</p>
          <p className="font-heading text-sm font-bold text-slate-300">
            {formatCurrency(budgetTotal, currency)}
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        {CATEGORIES.map((cat) => (
          <div key={cat.key} className="flex items-center gap-1.5 text-[10px] text-slate-400">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: cat.color }}
            />
            {cat.label}
          </div>
        ))}
      </div>

      {/* Budget progress bar */}
      <ProgressBar
        value={progressPct}
        label="Budget consumed"
        variant={progressVariant}
      />

      {/* Top 3 expensive items */}
      {topExpensive.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-400">Top Expenses</p>
          {topExpensive.map((item, i) => {
            const cat = item.type === "hotel" ? CATEGORIES[0] : CATEGORIES[1];
            const Icon = cat.icon;
            return (
              <motion.div
                key={item.name}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1, duration: 0.25 }}
                className="flex items-center gap-2.5"
              >
                <div
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
                  style={{ backgroundColor: `${cat.color}20` }}
                >
                  <Icon className="h-3.5 w-3.5" style={{ color: cat.color }} />
                </div>
                <span className="flex-1 truncate text-xs text-slate-300">
                  {item.name}
                </span>
                <span className="text-xs font-medium text-slate-200 tabular-nums">
                  {formatCurrency(item.cost, currency)}
                </span>
              </motion.div>
            );
          })}
        </div>
      )}
    </GlassPanel>
  );
}
