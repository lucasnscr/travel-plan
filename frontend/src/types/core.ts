/** Core data types mirroring backend state/models.py */

export type ApprovalStatus = "pending" | "in_review" | "approved" | "rejected";
export type BudgetTier = "budget" | "mid" | "luxury";

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface DateRange {
  start_date: string;
  end_date: string;
}

export interface Budget {
  total: number;
  currency: string;
  flexibility: number;
}

export interface TravelerProfile {
  interests: string[];
  pace: string;
  group_size: number;
}

export interface FlightOption {
  id: string;
  airline: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  price: number;
  currency: string;
  stops: number;
  booking_class: string;
  carbon_footprint_kg: number;
  score: number;
}

export interface HotelOption {
  id: string;
  name: string;
  address: string;
  coordinates: Coordinates;
  stars: number;
  price_per_night: number;
  currency: string;
  amenities: string[];
  reviews_score: number;
  distance_to_center_km: number;
  score: number;
}

export interface Activity {
  id: string;
  name: string;
  category: string;
  address: string;
  coordinates: Coordinates;
  duration_minutes: number;
  price: number;
  currency: string;
  opening_hours: Record<string, string>;
  requires_booking: boolean;
  indoor: boolean;
  description: string;
  score: number;
  data_source?: string;
}

export interface ItinerarySlot {
  activity_id: string;
  activity_name: string;
  start_time: string;
  end_time: string;
  travel_time_from_previous_minutes: number;
  notes: string;
}

export interface ItineraryDay {
  date: string;
  day_number: number;
  theme: string;
  slots: ItinerarySlot[];
  weather_condition: string;
  notes: string;
}

export interface OptimizedItinerary {
  days: ItineraryDay[];
  unscheduled_activity_ids: string[];
  optimization_method: string;
  validation_iterations: number;
  validation_warnings: string[];
}

export interface WeatherForecast {
  date: string;
  condition: string;
  temp_max: number;
  temp_min: number;
  rain_chance: number;
  rain_start: string | null;
  wind_speed: number;
}

export interface WeatherSummary {
  avg_temp_max: number;
  avg_temp_min: number;
  avg_rain_chance: number;
  dominant_condition: string;
  severe_weather_days: number;
  packing_suggestions: string[];
}

export interface SeasonalEvent {
  name: string;
  category: string;
  description: string;
  month_start: number;
  month_end: number;
}

export interface DestinationAnalysis {
  forecast: WeatherForecast[];
  alerts: Record<string, string>[];
  weather_summary: WeatherSummary;
  seasonal_events: SeasonalEvent[];
  travel_advisories: string[];
  analysis_timestamp: string;
}

export interface ValidationResult {
  is_valid: boolean;
  issues: string[];
  severity: "error" | "warning" | "info";
  suggested_fixes: string[];
}

export interface TravelVibe {
  destination_suggestions: string[];
  vibe_tags: string[];
  budget_tier_guess: BudgetTier;
  season_preference: string;
  activity_bias: string[];
}

export interface TravelPlannerCore {
  plan_id: string;
  destination: string;
  dates: DateRange;
  budget: Budget;
  traveler_profile: TravelerProfile;
  selected_flight_id: string | null;
  selected_hotel_id: string | null;
  selected_activity_ids: string[];
  current_cost: number;
  revision_count: number;
  approval_status: ApprovalStatus;
  risk_flags: string[];
  alternative_plans: Record<string, unknown>;
  destination_analysis: DestinationAnalysis | null;
  hotel_options: HotelOption[];
  activity_options: Activity[];
  optimized_itinerary: OptimizedItinerary | null;
}
