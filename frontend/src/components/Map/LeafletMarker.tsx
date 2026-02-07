import { useMemo } from "react";
import { Marker as LMarker, Popup } from "react-leaflet";
import L from "leaflet";
import { formatCurrency } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { MapMarker, MarkerType } from "@/stores/map-store";
import { MARKER_STYLES, MARKER_SVG_PATHS } from "./map-types";

interface LeafletMarkerProps {
  marker: MapMarker;
  selected: boolean;
  dimmed: boolean;
  onSelect: (id: string) => void;
}

function buildSvgIcon(type: MarkerType, selected: boolean, dimmed: boolean) {
  const style = MARKER_STYLES[type];
  const svgPath = MARKER_SVG_PATHS[type];
  const size = selected ? 36 : 28;
  const opacity = dimmed ? 0.4 : 1;
  const ring = selected
    ? `<circle cx="${size / 2}" cy="${size / 2}" r="${size / 2 - 1}" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>`
    : "";

  const html = `
    <div style="opacity:${opacity};transition:opacity 0.2s">
      <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="${style.hexColor}"/>
        ${ring}
        <g transform="translate(${(size - 16) / 2},${(size - 16) / 2}) scale(0.667)">
          <path d="${svgPath}" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </g>
      </svg>
    </div>
  `;

  return L.divIcon({
    html,
    className: "leaflet-marker-custom",
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  });
}

export function LeafletMarker({
  marker,
  selected,
  dimmed,
  onSelect,
}: LeafletMarkerProps) {
  const icon = useMemo(
    () => buildSvgIcon(marker.type, selected, dimmed),
    [marker.type, selected, dimmed],
  );

  const style = MARKER_STYLES[marker.type];

  return (
    <LMarker
      position={[marker.lat, marker.lng]}
      icon={icon}
      eventHandlers={{
        click: () => onSelect(marker.id),
      }}
    >
      <Popup className="leaflet-dark-popup" maxWidth={240}>
        <div className="w-[220px] rounded-lg bg-surface-900/95 text-slate-200">
          {/* Header */}
          <div
            className="flex h-[80px] items-center justify-center rounded-t-lg"
            style={{ backgroundColor: `${style.hexColor}15` }}
          >
            {marker.thumbnailUrl ? (
              <img
                src={marker.thumbnailUrl}
                alt={marker.label}
                className="h-full w-full rounded-t-lg object-cover"
              />
            ) : (
              <div
                className="flex h-10 w-10 items-center justify-center rounded-full"
                style={{ backgroundColor: `${style.hexColor}30` }}
              >
                <span
                  className="text-xl font-bold"
                  style={{ color: style.hexColor }}
                >
                  {marker.label.charAt(0)}
                </span>
              </div>
            )}
          </div>

          {/* Content */}
          <div className="space-y-1.5 p-2.5">
            <h4 className="text-sm font-semibold text-slate-100 line-clamp-1">
              {marker.label}
            </h4>
            <span
              className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium capitalize"
              style={{
                backgroundColor: `${style.hexColor}20`,
                color: style.hexColor,
              }}
            >
              {marker.type}
            </span>

            {/* Rating */}
            {marker.rating != null && marker.rating > 0 && (
              <div className="flex items-center gap-1">
                {Array.from({ length: 5 }, (_, i) => (
                  <svg
                    key={i}
                    className={cn(
                      "h-3 w-3",
                      i < Math.round(marker.rating ?? 0)
                        ? "fill-amber-400 text-amber-400"
                        : "text-slate-600",
                    )}
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
                      fill="currentColor"
                      stroke="currentColor"
                      strokeWidth="1"
                    />
                  </svg>
                ))}
                <span className="ml-1 text-xs text-slate-400">
                  {marker.rating.toFixed(1)}
                </span>
              </div>
            )}

            {/* Details */}
            <div className="flex flex-wrap gap-2 text-[11px] text-slate-400">
              {marker.timeSlot && <span>{marker.timeSlot}</span>}
              {marker.price != null && marker.price > 0 && (
                <span>{formatCurrency(marker.price, marker.currency)}</span>
              )}
            </div>

            {/* Description */}
            {marker.description && (
              <p className="text-[11px] text-slate-500 line-clamp-2">
                {marker.description}
              </p>
            )}
          </div>
        </div>
      </Popup>
    </LMarker>
  );
}
