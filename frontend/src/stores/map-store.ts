import { create } from "zustand";
import type { WeatherForecast } from "@/types/core";
import type { DayRoute } from "@/components/Map/map-types";

export type MarkerType =
  | "hotel"
  | "activity"
  | "restaurant"
  | "attraction"
  | "transport";

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  type: MarkerType;
  label: string;
  dayNumber?: number;
  rating?: number;
  price?: number;
  currency?: string;
  timeSlot?: string;
  thumbnailUrl?: string;
  description?: string;
  activityId?: string;
  hotelId?: string;
}

interface MapState {
  viewState: {
    latitude: number;
    longitude: number;
    zoom: number;
  };
  markers: MapMarker[];
  selectedMarkerId: string | null;
  hoveredMarkerId: string | null;
  selectedDayNumber: number | null;
  totalDays: number;
  routes: DayRoute[];
  weatherByDay: Record<number, WeatherForecast>;

  setViewState: (vs: MapState["viewState"]) => void;
  addMarkers: (markers: MapMarker[]) => void;
  clearMarkers: () => void;
  selectMarker: (id: string | null) => void;
  setHoveredMarker: (id: string | null) => void;
  setSelectedDay: (day: number | null) => void;
  setRoutes: (routes: DayRoute[]) => void;
  setWeatherByDay: (weather: Record<number, WeatherForecast>) => void;
  setTotalDays: (n: number) => void;
  loadPlanData: (params: {
    markers: MapMarker[];
    routes: DayRoute[];
    weatherByDay: Record<number, WeatherForecast>;
    totalDays: number;
    center?: { lat: number; lng: number };
  }) => void;
}

export const useMapStore = create<MapState>((set) => ({
  viewState: {
    latitude: 48.8566,
    longitude: 2.3522,
    zoom: 12,
  },
  markers: [],
  selectedMarkerId: null,
  hoveredMarkerId: null,
  selectedDayNumber: null,
  totalDays: 0,
  routes: [],
  weatherByDay: {},

  setViewState: (viewState) => set({ viewState }),
  addMarkers: (markers) =>
    set((s) => ({ markers: [...s.markers, ...markers] })),
  clearMarkers: () =>
    set({ markers: [], selectedMarkerId: null, hoveredMarkerId: null }),
  selectMarker: (id) => set({ selectedMarkerId: id }),
  setHoveredMarker: (id) => set({ hoveredMarkerId: id }),
  setSelectedDay: (day) => set({ selectedDayNumber: day }),
  setRoutes: (routes) => set({ routes }),
  setWeatherByDay: (weather) => set({ weatherByDay: weather }),
  setTotalDays: (n) => set({ totalDays: n }),
  loadPlanData: ({ markers, routes, weatherByDay, totalDays, center }) =>
    set({
      markers,
      routes,
      weatherByDay,
      totalDays,
      selectedMarkerId: null,
      hoveredMarkerId: null,
      selectedDayNumber: null,
      ...(center && {
        viewState: { latitude: center.lat, longitude: center.lng, zoom: 13 },
      }),
    }),
}));
