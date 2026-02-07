import { Marker } from "react-map-gl";
import {
  Bed,
  UtensilsCrossed,
  Camera,
  Car,
  MapPin,
  Star,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/utils/cn";
import type { MapMarker as MapMarkerType, MarkerType } from "@/stores/map-store";
import { MARKER_STYLES } from "./map-types";

interface MapMarkerProps {
  marker: MapMarkerType;
  selected: boolean;
  hovered: boolean;
  dimmed: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

const typeIcons: Record<MarkerType, typeof Bed> = {
  hotel: Bed,
  restaurant: UtensilsCrossed,
  attraction: Camera,
  transport: Car,
  activity: MapPin,
};

export function MapMarkerComponent({
  marker,
  selected,
  hovered,
  dimmed,
  onSelect,
  onHover,
}: MapMarkerProps) {
  const Icon = typeIcons[marker.type];
  const style = MARKER_STYLES[marker.type];

  return (
    <Marker
      longitude={marker.lng}
      latitude={marker.lat}
      anchor="bottom"
      onClick={(e) => {
        e.originalEvent.stopPropagation();
        onSelect(marker.id);
      }}
    >
      <div
        className="relative"
        onMouseEnter={() => onHover(marker.id)}
        onMouseLeave={() => onHover(null)}
      >
        {/* Pin */}
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-full shadow-lg transition-all duration-200",
            style.color,
            selected
              ? "scale-125 ring-2 ring-white/50"
              : "hover:scale-110",
            dimmed && "opacity-40",
          )}
        >
          <Icon className="h-4 w-4 text-white" />
        </div>

        {/* Hover preview tooltip */}
        <AnimatePresence>
          {hovered && !selected && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="absolute bottom-full left-1/2 z-20 mb-2 w-44 -translate-x-1/2 rounded-lg border border-white/10 bg-surface-900/95 p-2 shadow-xl backdrop-blur-lg pointer-events-none"
            >
              <div className="flex items-center gap-2">
                {marker.thumbnailUrl ? (
                  <img
                    src={marker.thumbnailUrl}
                    alt=""
                    className="h-8 w-8 shrink-0 rounded object-cover"
                  />
                ) : (
                  <div
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded"
                    style={{ backgroundColor: `${style.hexColor}20` }}
                  >
                    <Icon
                      className="h-4 w-4"
                      style={{ color: style.hexColor }}
                    />
                  </div>
                )}
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-slate-200">
                    {marker.label}
                  </p>
                  {marker.rating != null && marker.rating > 0 && (
                    <div className="flex items-center gap-0.5">
                      <Star className="h-2.5 w-2.5 fill-brand-400 text-brand-400" />
                      <span className="text-[10px] text-slate-400">
                        {marker.rating.toFixed(1)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Marker>
  );
}
