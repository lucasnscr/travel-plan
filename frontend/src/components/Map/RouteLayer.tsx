import { useEffect, useRef } from "react";
import { Source, Layer, useMap } from "react-map-gl";
import type { DayRoute } from "./map-types";
import type { LineLayer } from "react-map-gl";

interface RouteLayerProps {
  route: DayRoute;
  visible: boolean;
  animated: boolean;
  opacity: number;
}

export function RouteLayer({
  route,
  visible,
  animated,
  opacity,
}: RouteLayerProps) {
  const { current: mapRef } = useMap();
  const animRef = useRef<number>(0);

  const sourceId = `route-src-${route.dayNumber}`;
  const layerId = `route-${route.dayNumber}`;
  const animLayerId = `route-anim-${route.dayNumber}`;

  const geojson: GeoJSON.Feature<GeoJSON.LineString> = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: route.coordinates,
    },
  };

  // Drawing animation
  useEffect(() => {
    if (!animated || !mapRef) return;

    const map = mapRef.getMap();
    let step = 0;
    const totalSteps = 100;

    const animate = () => {
      step++;
      const t = step / totalSteps;

      if (map.getLayer(animLayerId)) {
        map.setPaintProperty(animLayerId, "line-dasharray", [
          t * 4,
          Math.max(0.01, (1 - t) * 4),
        ]);
      }

      if (step < totalSteps) {
        animRef.current = requestAnimationFrame(animate);
      }
    };

    // Small delay to ensure layer is mounted
    const timer = setTimeout(() => {
      animRef.current = requestAnimationFrame(animate);
    }, 100);

    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(animRef.current);
    };
  }, [animated, mapRef, animLayerId]);

  if (!visible || route.coordinates.length < 2) return null;

  const baseLayer: LineLayer = {
    id: layerId,
    type: "line",
    source: sourceId,
    paint: {
      "line-color": route.color,
      "line-width": 3,
      "line-opacity": opacity * 0.3,
    },
    layout: {
      "line-join": "round",
      "line-cap": "round",
    },
  };

  const animLayer: LineLayer = {
    id: animLayerId,
    type: "line",
    source: sourceId,
    paint: {
      "line-color": route.color,
      "line-width": 3,
      "line-opacity": opacity,
      "line-dasharray": animated ? [0, 4] : [4, 0],
    },
    layout: {
      "line-join": "round",
      "line-cap": "round",
    },
  };

  return (
    <Source id={sourceId} type="geojson" data={geojson}>
      <Layer {...baseLayer} />
      <Layer {...animLayer} />
    </Source>
  );
}
