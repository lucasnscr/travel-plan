import { useCallback, useMemo } from "react";
import Map, {
  NavigationControl,
  type ViewStateChangeEvent,
} from "react-map-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useMapStore } from "@/stores/map-store";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { MapMarkerComponent } from "./MapMarker";
import { RichPopup } from "./RichPopup";
import { RouteLayer } from "./RouteLayer";
import { DayFilterBar } from "./DayFilterBar";
import { WeatherOverlay } from "./WeatherOverlay";
import type { MapImplProps } from "./map-types";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

export function MapboxMap({
  markers,
  routes,
  selectedDayNumber,
  selectedMarkerId,
  hoveredMarkerId,
  weatherForDay,
  totalDays,
  onMarkerSelect,
  onMarkerHover,
  onDaySelect,
}: MapImplProps) {
  const { viewState, setViewState } = useMapStore();

  const onMove = useCallback(
    (evt: ViewStateChangeEvent) => setViewState(evt.viewState),
    [setViewState],
  );

  // Filter markers by selected day
  const visibleMarkers = useMemo(() => {
    if (selectedDayNumber === null) return markers;
    return markers.filter(
      (m) => m.dayNumber === selectedDayNumber || m.type === "hotel",
    );
  }, [markers, selectedDayNumber]);

  // Compute route visibility
  const routeProps = useMemo(
    () =>
      routes.map((r) => ({
        route: r,
        visible: true,
        animated: r.dayNumber === selectedDayNumber,
        opacity:
          selectedDayNumber === null
            ? 0.5
            : r.dayNumber === selectedDayNumber
              ? 1.0
              : 0.15,
      })),
    [routes, selectedDayNumber],
  );

  const selectedMarker = selectedMarkerId
    ? markers.find((m) => m.id === selectedMarkerId)
    : null;

  return (
    <GlassPanel padding="none" className="relative overflow-hidden">
      <Map
        {...viewState}
        onMove={onMove}
        onClick={() => onMarkerSelect(null)}
        style={{ width: "100%", height: "60vh", minHeight: 400 }}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
      >
        <NavigationControl position="top-right" />

        {/* Route layers */}
        {routeProps.map((rp) => (
          <RouteLayer key={rp.route.dayNumber} {...rp} />
        ))}

        {/* Markers */}
        {visibleMarkers.map((marker) => (
          <MapMarkerComponent
            key={marker.id}
            marker={marker}
            selected={selectedMarkerId === marker.id}
            hovered={hoveredMarkerId === marker.id}
            dimmed={
              selectedDayNumber !== null &&
              marker.dayNumber !== undefined &&
              marker.dayNumber !== selectedDayNumber &&
              marker.type !== "hotel"
            }
            onSelect={onMarkerSelect}
            onHover={onMarkerHover}
          />
        ))}

        {/* Rich popup */}
        {selectedMarker && (
          <RichPopup
            marker={selectedMarker}
            onClose={() => onMarkerSelect(null)}
          />
        )}
      </Map>

      {/* Overlays */}
      <DayFilterBar
        totalDays={totalDays}
        selectedDay={selectedDayNumber}
        onDaySelect={onDaySelect}
      />
      <WeatherOverlay forecast={weatherForDay} />
    </GlassPanel>
  );
}
