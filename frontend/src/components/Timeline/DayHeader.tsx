import { motion } from "framer-motion";
import {
  ChevronDown,
  Sun,
  Cloud,
  CloudRain,
  CloudSnow,
  Clock,
  DollarSign,
  Route,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { formatDate, formatCurrency, formatDuration } from "@/utils/format";
import { cn } from "@/utils/cn";
import { DAY_COLORS } from "@/components/Map/map-types";
import type { DayTotals } from "./timeline-types";

interface DayHeaderProps {
  dayNumber: number;
  date: string;
  theme: string;
  weatherCondition: string;
  totals: DayTotals;
  slotsCount: number;
  collapsed: boolean;
  onToggle: () => void;
  /** Ref callback for scroll sync IntersectionObserver */
  headerRef?: (el: HTMLDivElement | null) => void;
}

const weatherIcons: Record<string, typeof Sun> = {
  sunny: Sun,
  clear: Sun,
  cloudy: Cloud,
  overcast: Cloud,
  rain: CloudRain,
  drizzle: CloudRain,
  snow: CloudSnow,
};

const weatherColors: Record<string, string> = {
  sunny: "text-amber-400",
  clear: "text-amber-400",
  cloudy: "text-slate-400",
  overcast: "text-slate-500",
  rain: "text-blue-400",
  drizzle: "text-blue-400",
  snow: "text-cyan-300",
};

export function DayHeader({
  dayNumber,
  date,
  theme,
  weatherCondition,
  totals,
  slotsCount,
  collapsed,
  onToggle,
  headerRef,
}: DayHeaderProps) {
  const colorIdx = (dayNumber - 1) % DAY_COLORS.length;
  const dayColor = DAY_COLORS[colorIdx] ?? "#3b82f6";
  const WeatherIcon = weatherIcons[weatherCondition] ?? Cloud;
  const weatherColor = weatherColors[weatherCondition] ?? "text-slate-400";

  return (
    <div ref={headerRef} data-day={dayNumber}>
      <button
        type="button"
        onClick={onToggle}
        className="group flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] p-3 backdrop-blur-sm transition-colors hover:bg-white/[0.07]"
      >
        {/* Day number pill */}
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white"
          style={{ backgroundColor: `${dayColor}30`, color: dayColor }}
        >
          {dayNumber}
        </div>

        {/* Main info */}
        <div className="flex-1 text-left min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-heading text-sm font-semibold text-slate-100">
              Day {dayNumber}
            </h4>
            <span className="text-xs text-slate-500">
              {formatDate(date)}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <Badge label={theme} variant="info" className="text-[10px]" />
            <span className="text-[10px] text-slate-500">
              {slotsCount} {slotsCount === 1 ? "activity" : "activities"}
            </span>
          </div>
        </div>

        {/* Weather */}
        <WeatherIcon className={cn("h-5 w-5 shrink-0", weatherColor)} />

        {/* Totals */}
        <div className="hidden sm:flex items-center gap-3 text-[10px] text-slate-500">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDuration(totals.totalDuration)}
          </span>
          <span className="flex items-center gap-1">
            <Route className="h-3 w-3" />
            {formatDuration(totals.totalTravel)}
          </span>
          {totals.totalCost > 0 && (
            <span className="flex items-center gap-1 text-brand-400">
              <DollarSign className="h-3 w-3" />
              {formatCurrency(totals.totalCost, totals.currency)}
            </span>
          )}
        </div>

        {/* Collapse chevron */}
        <motion.div
          animate={{ rotate: collapsed ? -90 : 0 }}
          transition={{ duration: 0.2 }}
          className="shrink-0"
        >
          <ChevronDown className="h-4 w-4 text-slate-500 group-hover:text-slate-300" />
        </motion.div>
      </button>

      {/* Mobile totals row */}
      {!collapsed && (
        <div className="flex items-center gap-3 px-3 pt-1.5 text-[10px] text-slate-500 sm:hidden">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDuration(totals.totalDuration)}
          </span>
          <span className="flex items-center gap-1">
            <Route className="h-3 w-3" />
            {formatDuration(totals.totalTravel)}
          </span>
          {totals.totalCost > 0 && (
            <span className="flex items-center gap-1 text-brand-400">
              <DollarSign className="h-3 w-3" />
              {formatCurrency(totals.totalCost, totals.currency)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
