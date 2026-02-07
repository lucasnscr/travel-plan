import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Area,
} from "recharts";
import { motion } from "framer-motion";
import {
  Sun,
  Cloud,
  CloudRain,
  CloudSnow,
  Droplets,
  Thermometer,
} from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { usePlan } from "@/hooks/use-plan";
import { formatTemperature, formatDate } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { WeatherForecast } from "@/types/core";

/* ------------------------------------------------------------------ */
/*  Condition look-ups                                                 */
/* ------------------------------------------------------------------ */

const conditionIcons: Record<string, typeof Sun> = {
  sunny: Sun,
  clear: Sun,
  cloudy: Cloud,
  overcast: Cloud,
  rain: CloudRain,
  drizzle: CloudRain,
  snow: CloudSnow,
};

const conditionColors: Record<string, string> = {
  sunny: "text-amber-400",
  clear: "text-amber-400",
  cloudy: "text-slate-400",
  overcast: "text-slate-500",
  rain: "text-blue-400",
  drizzle: "text-blue-400",
  snow: "text-cyan-300",
};

const conditionAnimations: Record<string, string> = {
  sunny: "animate-weather-sun",
  clear: "animate-weather-sun",
  cloudy: "animate-weather-cloud",
  overcast: "animate-weather-cloud",
  rain: "animate-weather-rain",
  drizzle: "animate-weather-rain",
  snow: "animate-weather-snow",
};

function getConditionIcon(condition: string) {
  const lower = condition.toLowerCase();
  for (const [key, icon] of Object.entries(conditionIcons)) {
    if (lower.includes(key)) return icon;
  }
  return Cloud;
}

function getConditionColor(condition: string) {
  const lower = condition.toLowerCase();
  for (const [key, color] of Object.entries(conditionColors)) {
    if (lower.includes(key)) return color;
  }
  return "text-slate-400";
}

function getConditionAnimation(condition: string) {
  const lower = condition.toLowerCase();
  for (const [key, anim] of Object.entries(conditionAnimations)) {
    if (lower.includes(key)) return anim;
  }
  return "";
}

/* ------------------------------------------------------------------ */
/*  Best / worst day scoring                                           */
/* ------------------------------------------------------------------ */

function scoreForecast(f: WeatherForecast): number {
  // Higher = better weather. Prefer high temp, low rain.
  return f.temp_max - f.rain_chance * 0.5 - (f.condition.toLowerCase().includes("snow") ? 20 : 0);
}

/* ------------------------------------------------------------------ */
/*  Day card in the scrollable strip                                   */
/* ------------------------------------------------------------------ */

interface DayChipProps {
  forecast: WeatherForecast;
  isBest: boolean;
  isWorst: boolean;
  index: number;
}

function DayChip({ forecast, isBest, isWorst, index }: DayChipProps) {
  const Icon = getConditionIcon(forecast.condition);
  const color = getConditionColor(forecast.condition);
  const anim = getConditionAnimation(forecast.condition);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className={cn(
        "relative flex min-w-[100px] shrink-0 flex-col items-center gap-1.5 rounded-xl border p-3 transition-colors",
        isBest
          ? "border-emerald-500/40 bg-emerald-500/10"
          : isWorst
            ? "border-red-500/40 bg-red-500/10"
            : "border-white/5 bg-white/[0.03] hover:bg-white/[0.06]",
      )}
    >
      {/* Badge */}
      {isBest && (
        <span className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[9px] font-semibold text-emerald-400">
          Best
        </span>
      )}
      {isWorst && (
        <span className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full bg-red-500/20 px-2 py-0.5 text-[9px] font-semibold text-red-400">
          Worst
        </span>
      )}

      {/* Date */}
      <p className="text-[10px] font-medium text-slate-500">
        {formatDate(forecast.date).replace(/,.*/, "")}
      </p>

      {/* Animated icon */}
      <Icon className={cn("h-7 w-7", color, anim)} />

      {/* Temp */}
      <div className="flex items-baseline gap-1 text-xs">
        <span className="font-semibold text-slate-200">
          {formatTemperature(forecast.temp_max)}
        </span>
        <span className="text-slate-500">
          {formatTemperature(forecast.temp_min)}
        </span>
      </div>

      {/* Rain */}
      <div className="flex items-center gap-0.5 text-[10px] text-blue-400/70">
        <Droplets className="h-2.5 w-2.5" />
        {forecast.rain_chance.toFixed(0)}%
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Custom dark tooltip                                                */
/* ------------------------------------------------------------------ */

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const max = payload.find((p) => p.dataKey === "max");
  const min = payload.find((p) => p.dataKey === "min");

  return (
    <div className="rounded-lg border border-white/10 bg-surface-900/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      <p className="mb-1 text-slate-500">{label}</p>
      {max && (
        <p className="text-amber-400">
          <Thermometer className="mr-1 inline h-3 w-3" />
          Max: {formatTemperature(max.value)}
        </p>
      )}
      {min && (
        <p className="text-blue-400">
          <Thermometer className="mr-1 inline h-3 w-3" />
          Min: {formatTemperature(min.value)}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  WeatherOverview                                                    */
/* ------------------------------------------------------------------ */

export function WeatherOverview() {
  const { plan } = usePlan();
  const analysis = plan?.destination_analysis;
  if (!analysis) return null;

  const { weather_summary: summary, forecast } = analysis;

  // Best/worst day indices
  const { bestIdx, worstIdx } = useMemo(() => {
    if (forecast.length === 0) return { bestIdx: -1, worstIdx: -1 };
    let bIdx = 0;
    let wIdx = 0;
    let bScore = -Infinity;
    let wScore = Infinity;

    for (let i = 0; i < forecast.length; i++) {
      const s = scoreForecast(forecast[i]!);
      if (s > bScore) { bScore = s; bIdx = i; }
      if (s < wScore) { wScore = s; wIdx = i; }
    }
    return { bestIdx: bIdx, worstIdx: wIdx };
  }, [forecast]);

  // Chart data
  const chartData = useMemo(
    () =>
      forecast.map((f) => ({
        date: f.date.slice(5), // MM-DD
        max: f.temp_max,
        min: f.temp_min,
      })),
    [forecast],
  );

  return (
    <GlassPanel className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-sm font-semibold text-slate-200">
          Weather Forecast
        </h3>
        <Badge label={summary.dominant_condition} variant="info" />
      </div>

      {/* Scrollable day strip */}
      <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin">
        {forecast.map((f, i) => (
          <DayChip
            key={f.date}
            forecast={f}
            isBest={i === bestIdx}
            isWorst={i === worstIdx && worstIdx !== bestIdx}
            index={i}
          />
        ))}
      </div>

      {/* Temperature chart */}
      <div className="pt-1">
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={chartData}>
            <defs>
              <linearGradient id="weatherTempGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#64748b" }}
              axisLine={{ stroke: "#334155" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#64748b" }}
              width={32}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v}°`}
            />
            <Tooltip content={<ChartTooltip />} />
            <Area
              type="monotone"
              dataKey="max"
              stroke="transparent"
              fill="url(#weatherTempGrad)"
            />
            <Line
              type="monotone"
              dataKey="max"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={{ r: 3, fill: "#f59e0b", stroke: "#0f172a", strokeWidth: 2 }}
              activeDot={{ r: 5, fill: "#f59e0b" }}
            />
            <Line
              type="monotone"
              dataKey="min"
              stroke="#3b82f6"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={{ r: 2, fill: "#3b82f6", stroke: "#0f172a", strokeWidth: 2 }}
              activeDot={{ r: 4, fill: "#3b82f6" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Packing suggestions */}
      {summary.packing_suggestions.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-slate-400">Packing Tips</p>
          <div className="flex flex-wrap gap-1.5">
            {summary.packing_suggestions.map((tip) => (
              <Badge key={tip} label={tip} />
            ))}
          </div>
        </div>
      )}
    </GlassPanel>
  );
}
