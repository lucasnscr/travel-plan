import { useMemo, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useMapStore } from "@/stores/map-store";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { LeafletMarker } from "./LeafletMarker";
import { DayFilterBar } from "./DayFilterBar";
import { WeatherOverlay } from "./WeatherOverlay";
import type { MapImplProps } from "./map-types";

/** Syncs Leaflet map view with Zustand store */
function MapSync() {
  const map = useMap();
  const { viewState, setViewState } = useMapStore();

  // Sync store → map on viewState changes
  useEffect(() => {
    const center = map.getCenter();
    const zoom = map.getZoom();

    if (
      Math.abs(center.lat - viewState.latitude) > 0.0001 ||
      Math.abs(center.lng - viewState.longitude) > 0.0001 ||
      zoom !== viewState.zoom
    ) {
      map.setView([viewState.latitude, viewState.longitude], viewState.zoom, {
        animate: true,
      });
    }
  }, [viewState.latitude, viewState.longitude, viewState.zoom, map, setViewState]);

  // Sync map → store on move
  useEffect(() => {
    const handler = () => {
      const center = map.getCenter();
      setViewState({
        latitude: center.lat,
        longitude: center.lng,
        zoom: map.getZoom(),
      });
    };

    map.on("moveend", handler);
    return () => {
      map.off("moveend", handler);
    };
  }, [map, setViewState]);

  return null;
}

export function LeafletMap({
  markers,
  routes,
  selectedDayNumber,
  selectedMarkerId,
  weatherForDay,
  totalDays,
  onMarkerSelect,
  onDaySelect,
}: MapImplProps) {
  const { viewState } = useMapStore();

  // Filter markers by selected day
  const visibleMarkers = useMemo(() => {
    if (selectedDayNumber === null) return markers;
    return markers.filter(
      (m) => m.dayNumber === selectedDayNumber || m.type === "hotel",
    );
  }, [markers, selectedDayNumber]);

  // Route polylines — Leaflet uses [lat, lng] (opposite of GeoJSON)
  const polylines = useMemo(
    () =>
      routes.map((r) => ({
        dayNumber: r.dayNumber,
        color: r.color,
        positions: r.coordinates.map(
          ([lng, lat]) => [lat, lng] as [number, number],
        ),
        opacity:
          selectedDayNumber === null
            ? 0.5
            : r.dayNumber === selectedDayNumber
              ? 1.0
              : 0.15,
      })),
    [routes, selectedDayNumber],
  );

  return (
    <GlassPanel padding="none" className="relative overflow-hidden">
      <MapContainer
        center={[viewState.latitude, viewState.longitude]}
        zoom={viewState.zoom}
        style={{ width: "100%", height: "60vh", minHeight: 400 }}
        className="z-0"
        zoomControl={false}
      >
        <MapSync />

        {/* CartoDB dark tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Route polylines */}
        {polylines.map((p) => {
          if (p.positions.length < 2) return null;
          return (
            <Polyline
              key={p.dayNumber}
              positions={p.positions}
              pathOptions={{
                color: p.color,
                weight: 3,
                opacity: p.opacity,
                lineCap: "round",
                lineJoin: "round",
              }}
            />
          );
        })}

        {/* Markers */}
        {visibleMarkers.map((marker) => (
          <LeafletMarker
            key={marker.id}
            marker={marker}
            selected={selectedMarkerId === marker.id}
            dimmed={
              selectedDayNumber !== null &&
              marker.dayNumber !== undefined &&
              marker.dayNumber !== selectedDayNumber &&
              marker.type !== "hotel"
            }
            onSelect={onMarkerSelect}
          />
        ))}
      </MapContainer>

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
