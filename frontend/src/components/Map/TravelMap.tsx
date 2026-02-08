import { lazy, Suspense, useState, useCallback, useRef, useEffect } from "react";
import { useMapStore } from "@/stores/map-store";
import { MapboxMap } from "./MapboxMap";
import { Spinner } from "@/components/ui/Spinner";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Maximize2, Minimize2 } from "lucide-react";
import { cn } from "@/utils/cn";
import type { MapImplProps } from "./map-types";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

const LeafletMap = lazy(() =>
  import("./LeafletMap").then((m) => ({ default: m.LeafletMap })),
);

export function TravelMap() {
  const store = useMapStore();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement && containerRef.current) {
      containerRef.current.requestFullscreen().catch(() => {
        // Fallback: use CSS fullscreen
        setIsFullscreen(true);
      });
    } else if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      setIsFullscreen((prev) => !prev);
    }
  }, []);

  useEffect(() => {
    function handleChange() {
      setIsFullscreen(!!document.fullscreenElement);
    }
    document.addEventListener("fullscreenchange", handleChange);
    return () => document.removeEventListener("fullscreenchange", handleChange);
  }, []);

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

  const mapContent = !MAPBOX_TOKEN ? (
    <Suspense
      fallback={
        <GlassPanel className="flex h-[60vh] min-h-[400px] items-center justify-center">
          <Spinner size="lg" />
        </GlassPanel>
      }
    >
      <LeafletMap {...props} />
    </Suspense>
  ) : (
    <MapboxMap {...props} />
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative",
        isFullscreen && !document.fullscreenElement && "fixed inset-0 z-50 bg-surface-950",
      )}
    >
      {mapContent}
      <button
        onClick={toggleFullscreen}
        className="absolute right-3 top-3 z-10 rounded-lg bg-surface-900/80 p-2 text-slate-400 backdrop-blur-sm transition-colors hover:bg-surface-800 hover:text-slate-200"
        aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen map"}
      >
        {isFullscreen ? (
          <Minimize2 className="h-4 w-4" />
        ) : (
          <Maximize2 className="h-4 w-4" />
        )}
      </button>
    </div>
  );
}
