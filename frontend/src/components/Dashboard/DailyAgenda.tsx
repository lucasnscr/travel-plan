import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sun,
  Cloud,
  CloudRain,
  CloudSnow,
  Clock,
  Car,
  Footprints,
  Umbrella,
  Wind,
  Snowflake,
  MapPin,
  Landmark,
  UtensilsCrossed,
  TreePine,
  Church,
  ShoppingBag,
  Waves,
  Camera,
  Ticket,
  Compass,
} from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/Badge";
import { usePlan } from "@/hooks/use-plan";
import { useMapStore } from "@/stores/map-store";
import { formatDuration, formatDate } from "@/utils/format";
import { cn } from "@/utils/cn";
import { DAY_COLORS } from "@/components/Map/map-types";
import type { Activity, WeatherForecast } from "@/types/core";

/* ------------------------------------------------------------------ */
/*  Condition icons                                                    */
/* ------------------------------------------------------------------ */

const conditionIcons: Record<string, typeof Sun> = {
  sunny: Sun, clear: Sun,
  cloudy: Cloud, overcast: Cloud,
  rain: CloudRain, drizzle: CloudRain,
  snow: CloudSnow,
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
  if (lower.includes("sunny") || lower.includes("clear")) return "text-amber-400";
  if (lower.includes("rain") || lower.includes("drizzle")) return "text-blue-400";
  if (lower.includes("snow")) return "text-cyan-300";
  return "text-slate-400";
}

/* ------------------------------------------------------------------ */
/*  Category icons                                                     */
/* ------------------------------------------------------------------ */

const categoryIcons: Record<string, typeof MapPin> = {
  museum: Landmark, restaurant: UtensilsCrossed, food: UtensilsCrossed,
  dining: UtensilsCrossed, cafe: UtensilsCrossed, park: TreePine,
  garden: TreePine, nature: TreePine, temple: Church, church: Church,
  shopping: ShoppingBag, market: ShoppingBag, beach: Waves,
  tour: Compass, sightseeing: Camera, entertainment: Ticket,
  landmark: Landmark,
};

function getCategoryIcon(category: string) {
  const lower = category.toLowerCase();
  for (const [key, icon] of Object.entries(categoryIcons)) {
    if (lower.includes(key)) return icon;
  }
  return MapPin;
}

/* ------------------------------------------------------------------ */
/*  Smart alerts                                                       */
/* ------------------------------------------------------------------ */

interface WeatherAlert {
  icon: typeof Sun;
  message: string;
  variant: "warning" | "info" | "danger";
}

function generateAlerts(forecast: WeatherForecast | undefined): WeatherAlert[] {
  if (!forecast) return [];
  const alerts: WeatherAlert[] = [];

  if (forecast.rain_chance > 60) {
    alerts.push({
      icon: Umbrella,
      message: `${forecast.rain_chance.toFixed(0)}% chance of rain — bring an umbrella`,
      variant: "warning",
    });
  }

  if (forecast.temp_max > 35) {
    alerts.push({
      icon: Sun,
      message: "High UV expected — use sunscreen and stay hydrated",
      variant: "warning",
    });
  }

  if (forecast.wind_speed > 40) {
    alerts.push({
      icon: Wind,
      message: `Strong winds (${forecast.wind_speed.toFixed(0)} km/h) expected`,
      variant: "info",
    });
  }

  if (forecast.condition.toLowerCase().includes("snow")) {
    alerts.push({
      icon: Snowflake,
      message: "Snow expected — dress warmly and wear appropriate footwear",
      variant: "info",
    });
  }

  return alerts;
}

/* ------------------------------------------------------------------ */
/*  DailyAgenda                                                        */
/* ------------------------------------------------------------------ */

export function DailyAgenda() {
  const { plan } = usePlan();
  const selectedDayNumber = useMapStore((s) => s.selectedDayNumber);
  const setSelectedDay = useMapStore((s) => s.setSelectedDay);

  const itinerary = plan?.optimized_itinerary;
  const forecast = plan?.destination_analysis?.forecast;

  // Build activity map for quick lookup
  const activityMap = useMemo(() => {
    const map = new Map<string, Activity>();
    if (plan) {
      for (const a of plan.activity_options) {
        map.set(a.id, a);
      }
    }
    return map;
  }, [plan]);

  // Current day (default to 1 if nothing selected)
  const currentDay = selectedDayNumber ?? 1;
  const days = itinerary?.days ?? [];
  const day = days.find((d) => d.day_number === currentDay);

  // Match forecast for the selected day
  const dayForecast = useMemo(() => {
    if (!day || !forecast) return undefined;
    return forecast.find((f) => f.date === day.date);
  }, [day, forecast]);

  // Smart alerts
  const alerts = useMemo(() => generateAlerts(dayForecast), [dayForecast]);

  if (!plan || !itinerary || days.length === 0) {
    return (
      <GlassPanel className="flex flex-col items-center justify-center gap-2 py-12">
        <Clock className="h-8 w-8 text-slate-600" />
        <p className="text-sm text-slate-500">No itinerary available</p>
      </GlassPanel>
    );
  }

  return (
    <GlassPanel className="space-y-4">
      {/* Header */}
      <h3 className="font-heading text-sm font-semibold text-slate-200">
        Daily Agenda
      </h3>

      {/* Day selector pills */}
      <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-thin">
        {days.map((d) => {
          const colorIdx = (d.day_number - 1) % DAY_COLORS.length;
          const isActive = d.day_number === currentDay;
          return (
            <button
              key={d.day_number}
              onClick={() => setSelectedDay(d.day_number)}
              className={cn(
                "shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                isActive
                  ? "text-white"
                  : "text-slate-500 hover:text-slate-300 hover:bg-white/5",
              )}
              style={
                isActive
                  ? { backgroundColor: `${DAY_COLORS[colorIdx]}30`, color: DAY_COLORS[colorIdx] }
                  : undefined
              }
            >
              Day {d.day_number}
            </button>
          );
        })}
      </div>

      {/* Weather alerts */}
      <AnimatePresence mode="wait">
        {alerts.length > 0 && (
          <motion.div
            key={`alerts-${currentDay}`}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-1.5 overflow-hidden"
          >
            {alerts.map((alert, i) => {
              const AlertIcon = alert.icon;
              return (
                <div
                  key={i}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-xs",
                    alert.variant === "warning" && "bg-amber-500/10 text-amber-400",
                    alert.variant === "info" && "bg-blue-500/10 text-blue-400",
                    alert.variant === "danger" && "bg-red-500/10 text-red-400",
                  )}
                >
                  <AlertIcon className="h-3.5 w-3.5 shrink-0" />
                  {alert.message}
                </div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Activity list */}
      <AnimatePresence mode="wait">
        {day && (
          <motion.div
            key={`day-${currentDay}`}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.2 }}
            className="space-y-1"
          >
            {day.slots.length === 0 ? (
              <p className="py-4 text-center text-xs text-slate-500">
                No activities scheduled for this day
              </p>
            ) : (
              day.slots.map((slot, i) => {
                const activity = activityMap.get(slot.activity_id);
                const category = activity?.category ?? "";
                const CategoryIcon = getCategoryIcon(category);
                const colorIdx = (currentDay - 1) % DAY_COLORS.length;
                const dayColor = DAY_COLORS[colorIdx] ?? "#3b82f6";

                return (
                  <div key={`${slot.activity_id}-${i}`}>
                    {/* Travel time between activities */}
                    {i > 0 && slot.travel_time_from_previous_minutes > 0 && (
                      <div className="flex items-center gap-1.5 py-1 pl-6">
                        <div className="h-px flex-1 bg-white/5" />
                        {slot.travel_time_from_previous_minutes <= 15 ? (
                          <Footprints className="h-3 w-3 text-slate-600" />
                        ) : (
                          <Car className="h-3 w-3 text-slate-600" />
                        )}
                        <span className="text-[10px] text-slate-600">
                          {slot.travel_time_from_previous_minutes} min
                        </span>
                        <div className="h-px flex-1 bg-white/5" />
                      </div>
                    )}

                    {/* Activity row */}
                    <div className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-white/[0.03]">
                      {/* Icon */}
                      <div
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                        style={{ backgroundColor: `${dayColor}15` }}
                      >
                        <CategoryIcon className="h-4 w-4" style={{ color: dayColor }} />
                      </div>

                      {/* Info */}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-slate-200">
                          {slot.activity_name}
                        </p>
                        <div className="flex items-center gap-2 text-[10px] text-slate-500">
                          <span>{slot.start_time} – {slot.end_time}</span>
                          {activity && (
                            <span className="flex items-center gap-0.5">
                              <Clock className="h-2.5 w-2.5" />
                              {formatDuration(activity.duration_minutes)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Weather for this time */}
                      {dayForecast && (
                        <div className="shrink-0">
                          {(() => {
                            const WeatherIcon = getConditionIcon(dayForecast.condition);
                            return (
                              <WeatherIcon
                                className={cn(
                                  "h-4 w-4",
                                  getConditionColor(dayForecast.condition),
                                )}
                              />
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Day info footer */}
      {day && (
        <div className="flex items-center justify-between border-t border-white/5 pt-2 text-[10px] text-slate-500">
          <span>{formatDate(day.date)}</span>
          {day.theme && <Badge label={day.theme} />}
        </div>
      )}
    </GlassPanel>
  );
}
