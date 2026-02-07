import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Calendar, Compass, DollarSign, Building } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { usePlan } from "@/hooks/use-plan";
import { formatCurrency, computeNights } from "@/utils/format";
import { cn } from "@/utils/cn";

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
      // ease-out cubic
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
/*  Stat card                                                          */
/* ------------------------------------------------------------------ */

interface StatCardProps {
  icon: typeof Calendar;
  iconBg: string;
  iconColor: string;
  value: string;
  label: string;
  index: number;
}

function StatCard({ icon: Icon, iconBg, iconColor, value, label, index }: StatCardProps) {
  return (
    <GlassPanel
      padding="sm"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.35 }}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
            iconBg,
          )}
        >
          <Icon className={cn("h-5 w-5", iconColor)} />
        </div>
        <div className="min-w-0">
          <motion.p
            className="font-heading text-xl font-bold text-slate-100 tabular-nums"
            key={value}
          >
            {value}
          </motion.p>
          <p className="text-xs text-slate-500">{label}</p>
        </div>
      </div>
    </GlassPanel>
  );
}

/* ------------------------------------------------------------------ */
/*  TripStats                                                          */
/* ------------------------------------------------------------------ */

export function TripStats() {
  const { plan } = usePlan();
  if (!plan) return null;

  const totalDays = computeNights(plan.dates.start_date, plan.dates.end_date) + 1;
  const activitiesCount = plan.activity_options.length;
  const hotelsCount = plan.hotel_options.length;

  const animDays = useCountUp(totalDays);
  const animActivities = useCountUp(activitiesCount);
  const animCost = useCountUp(Math.round(plan.current_cost));
  const animHotels = useCountUp(hotelsCount);

  const stats: StatCardProps[] = [
    {
      icon: Calendar,
      iconBg: "bg-blue-500/15",
      iconColor: "text-blue-400",
      value: String(animDays),
      label: "Total Days",
      index: 0,
    },
    {
      icon: Compass,
      iconBg: "bg-brand-500/15",
      iconColor: "text-brand-400",
      value: String(animActivities),
      label: "Activities",
      index: 1,
    },
    {
      icon: DollarSign,
      iconBg: "bg-emerald-500/15",
      iconColor: "text-emerald-400",
      value: formatCurrency(animCost, plan.budget.currency),
      label: "Budget Used",
      index: 2,
    },
    {
      icon: Building,
      iconBg: "bg-purple-500/15",
      iconColor: "text-purple-400",
      value: String(animHotels),
      label: "Hotels Compared",
      index: 3,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {stats.map((s) => (
        <StatCard key={s.label} {...s} />
      ))}
    </div>
  );
}
