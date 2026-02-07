/** Activity/Places types mirroring backend activities/models.py */

export interface GeoLocation {
  lat: number;
  lng: number;
}

export interface Viewport {
  low: GeoLocation;
  high: GeoLocation;
}

export interface PlacePhoto {
  photo_reference: string;
  url: string;
  width: number;
  height: number;
  attributions: string[];
}

export interface PlaceReview {
  author: string;
  rating: number;
  text: string;
  time: string;
  language: string;
}

export interface PlaceOpeningHours {
  open_now: boolean | null;
  weekday_text: string[];
}

export interface Place {
  place_id: string;
  name: string;
  category: string;
  address: string;
  location: GeoLocation;
  rating: number;
  user_ratings_total: number;
  price_level: number | null;
  types: string[];
  photos: PlacePhoto[];
  opening_hours: PlaceOpeningHours | null;
  website: string | null;
  phone: string | null;
  description: string;
  data_source: string;
}

export interface PlaceDetail extends Place {
  reviews: PlaceReview[];
  viewport: Viewport | null;
  url: string;
  business_status: string;
  editorial_summary: string;
}

export interface DirectionStep {
  instruction: string;
  distance_meters: number;
  duration_seconds: number;
  travel_mode: string;
}

export interface DirectionRoute {
  summary: string;
  distance_meters: number;
  duration_seconds: number;
  start_address: string;
  end_address: string;
  steps: DirectionStep[];
  polyline: string;
  data_source: string;
}

export interface GeocodeResult {
  place_id: string;
  formatted_address: string;
  location: GeoLocation;
  types: string[];
  data_source: string;
}

export interface SearchActivitiesInput {
  query: string;
  location: string;
  language?: string;
  max_results?: number;
}

export interface SearchRestaurantsInput {
  location: string;
  cuisine?: string;
  price_level?: number;
  language?: string;
  max_results?: number;
}

export interface NearbySearchInput {
  latitude: number;
  longitude: number;
  radius_meters?: number;
  place_type?: string;
  language?: string;
  max_results?: number;
}

export interface GetPlaceDetailsInput {
  place_id: string;
  language?: string;
}

export interface GetPlacePhotosInput {
  place_id: string;
  max_photos?: number;
}

export interface GetDirectionsInput {
  origin: string;
  destination: string;
  mode?: string;
  language?: string;
}

export interface GeocodeInput {
  address: string;
  language?: string;
}

export interface ReverseGeocodeInput {
  latitude: number;
  longitude: number;
  language?: string;
}
