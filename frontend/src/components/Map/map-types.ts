import type { WeatherForecast } from "@/types/core";
import type { MapMarker, MarkerType } from "@/stores/map-store";

/** Color palette for day-based routes */
export const DAY_COLORS = [
  "#3b82f6", // blue   (day 1)
  "#22c55e", // green  (day 2)
  "#a855f7", // purple (day 3)
  "#f97316", // orange (day 4)
  "#ec4899", // pink   (day 5)
  "#06b6d4", // cyan   (day 6)
  "#eab308", // yellow (day 7)
  "#ef4444", // red    (day 8)
] as const;

/** Pin icon/color config per marker type */
export interface MarkerStyle {
  color: string;
  hexColor: string;
}

export const MARKER_STYLES: Record<MarkerType, MarkerStyle> = {
  hotel: { color: "bg-blue-500", hexColor: "#3b82f6" },
  restaurant: { color: "bg-orange-500", hexColor: "#f97316" },
  attraction: { color: "bg-purple-500", hexColor: "#a855f7" },
  transport: { color: "bg-green-500", hexColor: "#22c55e" },
  activity: { color: "bg-brand-500", hexColor: "#f59e0b" },
};

/** A route between points for a single day */
export interface DayRoute {
  dayNumber: number;
  color: string;
  coordinates: [lng: number, lat: number][];
}

/** SVG path data for Leaflet divIcon markers */
export const MARKER_SVG_PATHS: Record<MarkerType, string> = {
  // Bed
  hotel:
    "M2 12V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v6M2 16h20M2 20h20M6 12v-2a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2M14 12v-2a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2",
  // UtensilsCrossed
  restaurant:
    "M14.5 2L19 9l-4.5 7M9.5 2L5 9l4.5 7M2 12h20",
  // Camera
  attraction:
    "M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3zM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  // Car
  transport:
    "M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C1.4 11.3 1 12.1 1 13v3c0 .6.4 1 1 1h2M7 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM13 17h4a2 2 0 1 0 4 0 2 2 0 0 0-4 0z",
  // MapPin
  activity:
    "M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0zM12 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
};

/** Props shared between Mapbox and Leaflet map implementations */
export interface MapImplProps {
  markers: MapMarker[];
  routes: DayRoute[];
  selectedDayNumber: number | null;
  selectedMarkerId: string | null;
  hoveredMarkerId: string | null;
  weatherForDay: WeatherForecast | null;
  totalDays: number;
  onMarkerSelect: (id: string | null) => void;
  onMarkerHover: (id: string | null) => void;
  onDaySelect: (day: number | null) => void;
}

/** Weather condition → icon name mapping */
export const CONDITION_ICONS: Record<string, string> = {
  sunny: "Sun",
  clear: "Sun",
  cloudy: "Cloud",
  overcast: "Cloud",
  rain: "CloudRain",
  drizzle: "CloudRain",
  snow: "CloudSnow",
};

/** Weather condition → background tint */
export const CONDITION_BG: Record<string, string> = {
  sunny: "bg-amber-500/15 border-amber-500/20",
  clear: "bg-amber-500/15 border-amber-500/20",
  cloudy: "bg-slate-500/15 border-slate-500/20",
  overcast: "bg-slate-600/15 border-slate-600/20",
  rain: "bg-blue-500/15 border-blue-500/20",
  drizzle: "bg-blue-400/15 border-blue-400/20",
  snow: "bg-cyan-400/15 border-cyan-400/20",
};

/** Weather condition → icon color */
export const CONDITION_COLORS: Record<string, string> = {
  sunny: "text-amber-400",
  clear: "text-amber-400",
  cloudy: "text-slate-400",
  overcast: "text-slate-500",
  rain: "text-blue-400",
  drizzle: "text-blue-400",
  snow: "text-cyan-300",
};
