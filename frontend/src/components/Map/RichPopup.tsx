import { Popup } from "react-map-gl";
import { Star, Clock, DollarSign, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { formatCurrency } from "@/utils/format";
import type { MapMarker } from "@/stores/map-store";
import { MARKER_STYLES } from "./map-types";
import { cn } from "@/utils/cn";

interface RichPopupProps {
  marker: MapMarker;
  onClose: () => void;
}

export function RichPopup({ marker, onClose }: RichPopupProps) {
  const style = MARKER_STYLES[marker.type];

  return (
    <Popup
      longitude={marker.lng}
      latitude={marker.lat}
      anchor="bottom"
      offset={[0, -40] as [number, number]}
      closeOnClick={false}
      onClose={onClose}
      maxWidth="260px"
      className="[&_.mapboxgl-popup-content]:!rounded-xl [&_.mapboxgl-popup-content]:!bg-surface-900/95 [&_.mapboxgl-popup-content]:!p-0 [&_.mapboxgl-popup-content]:!backdrop-blur-xl [&_.mapboxgl-popup-content]:!border [&_.mapboxgl-popup-content]:!border-white/10 [&_.mapboxgl-popup-tip]:!border-t-[rgba(30,41,59,0.95)]"
    >
      <div className="w-[240px]">
        {/* Photo / placeholder */}
        <div
          className="flex h-[100px] items-center justify-center rounded-t-xl"
          style={{ backgroundColor: `${style.hexColor}15` }}
        >
          {marker.thumbnailUrl ? (
            <img
              src={marker.thumbnailUrl}
              alt={marker.label}
              className="h-full w-full rounded-t-xl object-cover"
            />
          ) : (
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ backgroundColor: `${style.hexColor}30` }}
            >
              <span
                className="text-2xl font-bold"
                style={{ color: style.hexColor }}
              >
                {marker.label.charAt(0)}
              </span>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="space-y-2 p-3">
          <div>
            <h4 className="text-sm font-semibold text-slate-100 line-clamp-1">
              {marker.label}
            </h4>
            <Badge
              label={marker.type}
              variant="default"
              className="mt-1 capitalize"
            />
          </div>

          {/* Rating */}
          {marker.rating != null && marker.rating > 0 && (
            <div className="flex items-center gap-1">
              {Array.from({ length: 5 }, (_, i) => (
                <Star
                  key={i}
                  className={cn(
                    "h-3 w-3",
                    i < Math.round(marker.rating ?? 0)
                      ? "fill-brand-400 text-brand-400"
                      : "text-slate-600",
                  )}
                />
              ))}
              <span className="ml-1 text-xs text-slate-400">
                {marker.rating.toFixed(1)}
              </span>
            </div>
          )}

          {/* Details row */}
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            {marker.timeSlot && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {marker.timeSlot}
              </span>
            )}
            {marker.price != null && marker.price > 0 && (
              <span className="flex items-center gap-1">
                <DollarSign className="h-3 w-3" />
                {formatCurrency(marker.price, marker.currency)}
              </span>
            )}
          </div>

          {/* Description */}
          {marker.description && (
            <p className="text-xs text-slate-500 line-clamp-2">
              {marker.description}
            </p>
          )}

          {/* Action */}
          <Button
            variant="ghost"
            size="sm"
            icon={<ExternalLink className="h-3 w-3" />}
            className="w-full text-xs"
          >
            View details
          </Button>
        </div>
      </div>
    </Popup>
  );
}
