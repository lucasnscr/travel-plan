/** Hotel types mirroring backend hotels/models.py */

export interface HotelLocation {
  lat: number;
  lng: number;
  area: string | null;
}

export interface HotelSearchInput {
  destination: string;
  check_in: string;
  check_out: string;
  guests: number;
  preferences: Record<string, unknown>;
  location_centrality: number;
  min_stars: number | null;
  amenities: string[];
}

export interface HotelResult {
  provider: string;
  name: string;
  stars: number | null;
  review_score: number | null;
  price_total: number | null;
  currency: string | null;
  nightly_price_avg: number | null;
  location: HotelLocation;
  distance_to_center_km: number | null;
  amenities: string[];
  deep_link: string | null;
  photos: string[];
  score: number;
  data_source: string;
  raw: Record<string, unknown>;
}

export interface Room {
  room_id: string | null;
  name: string;
  type: string;
  max_occupancy: number;
  bed_type: string | null;
  size_sqm: number | null;
  price_per_night: number | null;
  currency: string | null;
  breakfast_included: boolean;
  cancellation_policy: string | null;
}

export interface Rate {
  rate_id: string | null;
  room_name: string;
  price_per_night: number;
  total_price: number;
  currency: string;
  meal_plan: string;
  cancellation: string;
  payment: string;
}

export interface HotelReview {
  overall_score: number;
  total_reviews: number;
  categories: Record<string, number>;
  recent_highlights: string[];
}

export interface Facility {
  name: string;
  category: string;
  available: boolean;
}

export interface HotelDetail {
  hotel_id: string;
  name: string;
  description: string | null;
  stars: number | null;
  address: string | null;
  location: HotelLocation;
  check_in_time: string | null;
  check_out_time: string | null;
  photos: string[];
  rooms: Room[];
  rates: Rate[];
  review: HotelReview | null;
  facilities: Facility[];
  policies: Record<string, string>;
  data_source: string;
}

export interface HotelSearchByCoordinatesInput {
  latitude: number;
  longitude: number;
  radius_km: number;
  check_in: string;
  check_out: string;
  adults: number;
}

export interface HotelCompareInput {
  hotel_ids: string[];
}
