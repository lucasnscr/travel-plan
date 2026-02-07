import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  Sun,
  Cloud,
  CloudRain,
  CloudSnow,
  Wind,
  Droplets,
  Thermometer,
} from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  YAxis,
} from "recharts";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatTemperature, formatDate } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { WeatherForecast } from "@/types/core";

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

const conditionBg: Record<string, string> = {
  sunny: "from-amber-500/10 to-orange-500/5",
  clear: "from-amber-500/10 to-orange-500/5",
  cloudy: "from-slate-500/10 to-slate-600/5",
  overcast: "from-slate-600/10 to-slate-700/5",
  rain: "from-blue-500/10 to-indigo-500/5",
  drizzle: "from-blue-400/10 to-blue-500/5",
  snow: "from-cyan-400/10 to-blue-300/5",
};

const sparklineColors: Record<string, string> = {
  sunny: "#f59e0b",
  clear: "#f59e0b",
  cloudy: "#64748b",
  overcast: "#475569",
  rain: "#3b82f6",
  drizzle: "#60a5fa",
  snow: "#67e8f9",
};

/** Generate synthetic hourly temperature curve from min/max */
function generateHourlyCurve(
  min: number,
  max: number,
): { hour: number; temp: number }[] {
  return Array.from({ length: 12 }, (_, i) => {
    // Model a typical day: coldest at dawn (hour 0→6am), warmest at hour 6 (→2pm)
    const t = i / 11;
    const temp = min + (max - min) * Math.sin(t * Math.PI * 0.85);
    return { hour: 6 + i, temp: Math.round(temp * 10) / 10 };
  });
}

interface WeatherCardProps {
  forecast: WeatherForecast;
  loading?: boolean;
  index?: number;
}

export function WeatherCardSkeleton() {
  return (
    <div className="glass-panel overflow-hidden p-4">
      <div className="flex items-center gap-4">
        <Skeleton variant="circular" className="h-14 w-14" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-6 w-16" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
      <Skeleton variant="rectangular" className="mt-3 h-12 w-full" />
      <div className="mt-3 flex gap-3">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-16" />
      </div>
    </div>
  );
}

export function WeatherCard({
  forecast,
  loading = false,
  index = 0,
}: WeatherCardProps) {
  if (loading) return <WeatherCardSkeleton />;

  const Icon = conditionIcons[forecast.condition] ?? Cloud;
  const color = conditionColors[forecast.condition] ?? "text-slate-400";
  const animation = conditionAnimations[forecast.condition] ?? "";
  const bg = conditionBg[forecast.condition] ?? "from-slate-500/10 to-slate-600/5";
  const sparkColor = sparklineColors[forecast.condition] ?? "#64748b";

  const avgTemp = (forecast.temp_max + forecast.temp_min) / 2;
  // Rough "feels like" approximation using wind chill factor
  const feelsLike = avgTemp - forecast.wind_speed * 0.1;

  const hourlyData = useMemo(
    () => generateHourlyCurve(forecast.temp_min, forecast.temp_max),
    [forecast.temp_min, forecast.temp_max],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3, ease: "easeOut" }}
    >
      <div
        className={cn(
          "card-hover-lift glass-panel overflow-hidden bg-gradient-to-br",
          bg,
        )}
      >
        <div className="p-4">
          {/* Header: icon + temps */}
          <div className="flex items-start gap-4">
            <div className="shrink-0">
              <Icon className={cn("h-14 w-14", color, animation)} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-500">
                {formatDate(forecast.date)}
              </p>
              <p className="text-sm font-medium capitalize text-slate-200">
                {forecast.condition}
              </p>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-100">
                  {formatTemperature(forecast.temp_max)}
                </span>
                <span className="text-sm text-slate-500">
                  / {formatTemperature(forecast.temp_min)}
                </span>
              </div>
              <div className="mt-0.5 flex items-center gap-1 text-[10px] text-slate-500">
                <Thermometer className="h-3 w-3" />
                Feels like {formatTemperature(feelsLike)}
              </div>
            </div>
          </div>

          {/* Sparkline */}
          <div className="mt-3 -mx-1">
            <ResponsiveContainer width="100%" height={48}>
              <AreaChart
                data={hourlyData}
                margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
              >
                <defs>
                  <linearGradient id={`wg-${forecast.date}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={sparkColor} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={sparkColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis domain={["dataMin - 1", "dataMax + 1"]} hide />
                <Area
                  type="monotone"
                  dataKey="temp"
                  stroke={sparkColor}
                  fill={`url(#wg-${forecast.date})`}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Detail chips */}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Droplets className="h-3.5 w-3.5 text-blue-400" />
              {forecast.rain_chance}%
            </span>
            <span className="flex items-center gap-1">
              <Wind className="h-3.5 w-3.5 text-slate-400" />
              {forecast.wind_speed.toFixed(0)} km/h
            </span>
            {forecast.rain_start && (
              <span className="text-blue-300">
                Rain from {forecast.rain_start}
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
