import { lazy, Suspense } from "react";
import { useMapStore } from "@/stores/map-store";
import { MapboxMap } from "./MapboxMap";
import { Spinner } from "@/components/ui/Spinner";
import { GlassPanel } from "@/components/ui/GlassPanel";
import type { MapImplProps } from "./map-types";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

const LeafletMap = lazy(() =>
  import("./LeafletMap").then((m) => ({ default: m.LeafletMap })),
);

export function TravelMap() {
  const store = useMapStore();

  const weatherForDay =
    store.selectedDayNumber != null
      ? (store.weatherByDay[store.selectedDayNumber] ?? null)
      : null;

  const props: MapImplProps = {
    markers: store.markers,
    routes: store.routes,
    selectedDayNumber: store.selectedDayNumber,
    selectedMarkerId: store.selectedMarkerId,
    hoveredMarkerId: store.hoveredMarkerId,
    weatherForDay,
    totalDays: store.totalDays,
    onMarkerSelect: store.selectMarker,
    onMarkerHover: store.setHoveredMarker,
    onDaySelect: store.setSelectedDay,
  };

  if (!MAPBOX_TOKEN) {
    return (
      <Suspense
        fallback={
          <GlassPanel className="flex h-[60vh] min-h-[400px] items-center justify-center">
            <Spinner size="lg" />
          </GlassPanel>
        }
      >
        <LeafletMap {...props} />
      </Suspense>
    );
  }

  return <MapboxMap {...props} />;
}
