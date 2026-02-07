import {
  Sun,
  Cloud,
  CloudRain,
  CloudSnow,
  Droplets,
  Wind,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { formatTemperature } from "@/utils/format";
import type { WeatherForecast } from "@/types/core";
import { cn } from "@/utils/cn";
import { CONDITION_BG, CONDITION_COLORS } from "./map-types";

const conditionIcons: Record<string, typeof Sun> = {
  sunny: Sun,
  clear: Sun,
  cloudy: Cloud,
  overcast: Cloud,
  rain: CloudRain,
  drizzle: CloudRain,
  snow: CloudSnow,
};

interface WeatherOverlayProps {
  forecast: WeatherForecast | null;
}

export function WeatherOverlay({ forecast }: WeatherOverlayProps) {
  return (
    <AnimatePresence>
      {forecast && (
        <motion.div
          key={forecast.date}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ duration: 0.2 }}
          className={cn(
            "absolute bottom-4 left-4 z-10 rounded-xl border p-3 backdrop-blur-lg",
            CONDITION_BG[forecast.condition] ?? "bg-slate-500/15 border-slate-500/20",
          )}
        >
          <div className="flex items-center gap-3">
            {(() => {
              const Icon = conditionIcons[forecast.condition] ?? Cloud;
              const color =
                CONDITION_COLORS[forecast.condition] ?? "text-slate-400";
              return <Icon className={cn("h-8 w-8", color)} />;
            })()}
            <div className="space-y-0.5">
              <p className="text-sm font-medium capitalize text-slate-200">
                {forecast.condition}
              </p>
              <p className="text-xs text-slate-300">
                {formatTemperature(forecast.temp_max)} /{" "}
                {formatTemperature(forecast.temp_min)}
              </p>
              <div className="flex items-center gap-2 text-[10px] text-slate-400">
                <span className="flex items-center gap-0.5">
                  <Droplets className="h-3 w-3" />
                  {forecast.rain_chance}%
                </span>
                <span className="flex items-center gap-0.5">
                  <Wind className="h-3 w-3" />
                  {forecast.wind_speed.toFixed(0)} km/h
                </span>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
