import { useEffect } from "react";
import { useMapStore } from "@/stores/map-store";
import type { MapMarker, MarkerType } from "@/stores/map-store";
import type { TravelPlannerCore, WeatherForecast } from "@/types/core";
import type { DayRoute } from "./map-types";
import { DAY_COLORS } from "./map-types";

/** Map activity categories to marker types */
function categorizeActivity(category: string): MarkerType {
  const lower = category.toLowerCase();
  if (
    lower.includes("restaurant") ||
    lower.includes("food") ||
    lower.includes("dining") ||
    lower.includes("cafe")
  )
    return "restaurant";
  if (
    lower.includes("transport") ||
    lower.includes("transfer") ||
    lower.includes("taxi") ||
    lower.includes("flight")
  )
    return "transport";
  if (
    lower.includes("museum") ||
    lower.includes("landmark") ||
    lower.includes("monument") ||
    lower.includes("sight") ||
    lower.includes("tour") ||
    lower.includes("temple") ||
    lower.includes("church") ||
    lower.includes("palace")
  )
    return "attraction";
  return "activity";
}

/**
 * Transforms TravelPlannerCore data into map store state.
 * Call once when the plan loads (e.g. in ResultsPage).
 */
export function useMapData(plan: TravelPlannerCore | null) {
  const loadPlanData = useMapStore((s) => s.loadPlanData);

  useEffect(() => {
    if (!plan) return;

    const markers: MapMarker[] = [];
    const activityMap = new Map(
      plan.activity_options.map((a) => [a.id, a]),
    );

    // Hotels
    for (const hotel of plan.hotel_options) {
      markers.push({
        id: `hotel-${hotel.id}`,
        lat: hotel.coordinates.lat,
        lng: hotel.coordinates.lng,
        type: "hotel",
        label: hotel.name,
        rating: hotel.reviews_score,
        price: hotel.price_per_night,
        currency: hotel.currency,
        hotelId: hotel.id,
      });
    }

    // Itinerary slots → activity markers + routes
    const routes: DayRoute[] = [];

    if (plan.optimized_itinerary) {
      for (const day of plan.optimized_itinerary.days) {
        const dayCoords: [number, number][] = [];

        for (const slot of day.slots) {
          const activity = activityMap.get(slot.activity_id);
          if (!activity) continue;

          markers.push({
            id: `act-${activity.id}-d${day.day_number}`,
            lat: activity.coordinates.lat,
            lng: activity.coordinates.lng,
            type: categorizeActivity(activity.category),
            label: activity.name,
            dayNumber: day.day_number,
            rating: activity.score * 5,
            price: activity.price,
            currency: activity.currency,
            timeSlot: `${slot.start_time} - ${slot.end_time}`,
            description: activity.description,
            activityId: activity.id,
          });

          dayCoords.push([activity.coordinates.lng, activity.coordinates.lat]);
        }

        if (dayCoords.length >= 2) {
          const colorIdx = (day.day_number - 1) % DAY_COLORS.length;
          routes.push({
            dayNumber: day.day_number,
            color: DAY_COLORS[colorIdx] ?? "#3b82f6",
            coordinates: dayCoords,
          });
        }
      }
    }

    // Weather by day
    const weatherByDay: Record<number, WeatherForecast> = {};
    if (plan.destination_analysis?.forecast && plan.optimized_itinerary) {
      for (const day of plan.optimized_itinerary.days) {
        const forecast = plan.destination_analysis.forecast.find(
          (f) => f.date === day.date,
        );
        if (forecast) {
          weatherByDay[day.day_number] = forecast;
        }
      }
    }

    // Auto-center
    let center: { lat: number; lng: number } | undefined;
    if (markers.length > 0) {
      const lats = markers.map((m) => m.lat);
      const lngs = markers.map((m) => m.lng);
      center = {
        lat: (Math.min(...lats) + Math.max(...lats)) / 2,
        lng: (Math.min(...lngs) + Math.max(...lngs)) / 2,
      };
    }

    loadPlanData({
      markers,
      routes,
      weatherByDay,
      totalDays: plan.optimized_itinerary?.days.length ?? 0,
      center,
    });
  }, [plan, loadPlanData]);
}
