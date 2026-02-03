"""Core data models for the travel orchestrator state machine.

All models are TypedDicts designed for use as LangGraph state schemas,
ensuring serialization compatibility and clear type contracts between agents.
"""

from typing import Any, Optional

from typing_extensions import Literal, TypedDict


class TravelPlannerCore(TypedDict):
    """Root state for the LangGraph travel planning workflow.

    Holds the full context of a single travel plan as it flows through
    the graph nodes — from initial request through research, validation,
    and final approval. Every node reads from and writes back to this state.
    """

    plan_id: str
    destination: str
    dates: dict[str, str]  # start_date, end_date (ISO 8601)
    budget: dict[str, float | str]  # total (float), currency (str), flexibility (float 0-1)
    traveler_profile: dict[str, list[str] | str | int]  # interests, pace, group_size
    selected_flight_id: Optional[str]
    selected_hotel_id: Optional[str]
    selected_activity_ids: list[str]
    current_cost: float
    revision_count: int
    approval_status: Literal["pending", "in_review", "approved", "rejected"]
    risk_flags: list[str]
    alternative_plans: dict[str, Any]  # plan_name -> plan_data
    destination_analysis: Optional["DestinationAnalysis"]
    hotel_options: list["HotelOption"]
    activity_options: list["Activity"]
    optimized_itinerary: Optional["OptimizedItinerary"]


class FlightOption(TypedDict):
    """A single flight option returned by the flights research agent.

    Scored on a 0-1 scale that balances price, duration, stops,
    and carbon footprint relative to the traveler's preferences.
    """

    id: str
    airline: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    price: float
    currency: str
    stops: int
    booking_class: str
    carbon_footprint_kg: float
    score: float


class HotelOption(TypedDict):
    """A single hotel option returned by the accommodation research agent.

    Scored on a 0-1 scale considering price, location, amenities,
    and review quality relative to the traveler's preferences.
    """

    id: str
    name: str
    address: str
    coordinates: dict[str, float]  # lat, lng
    stars: int
    price_per_night: float
    currency: str
    amenities: list[str]
    reviews_score: float
    distance_to_center_km: float
    score: float


class Activity(TypedDict):
    """A bookable or visitable activity at the destination.

    Carries scheduling metadata (duration, opening hours, booking requirement)
    so the itinerary builder can slot activities into valid time windows.
    """

    id: str
    name: str
    category: str
    address: str
    coordinates: dict[str, float]  # lat, lng
    duration_minutes: int
    price: float
    currency: str
    opening_hours: dict[str, str]  # day -> hours (e.g. "monday" -> "09:00-18:00")
    requires_booking: bool
    indoor: bool
    description: str
    score: float


class ItinerarySlot(TypedDict):
    """A single scheduled activity within an itinerary day."""

    activity_id: str
    activity_name: str
    start_time: str  # "HH:MM" (24h format)
    end_time: str  # "HH:MM" (24h format)
    travel_time_from_previous_minutes: int  # 0 for the first slot
    notes: str


class ItineraryDay(TypedDict):
    """A single day in the optimized itinerary."""

    date: str  # ISO 8601 date, e.g. "2025-07-01"
    day_number: int  # 1-indexed
    theme: str  # e.g., "Art & Culture", "Nature Day"
    slots: list[ItinerarySlot]
    weather_condition: str  # from forecast, e.g., "sunny", "rain"
    notes: str  # day-level notes


class OptimizedItinerary(TypedDict):
    """The complete day-by-day itinerary produced by optimize_itinerary."""

    days: list[ItineraryDay]
    unscheduled_activity_ids: list[str]  # activities that could not be fit
    optimization_method: str  # "llm" or "deterministic_fallback"
    validation_iterations: int  # how many LLM-repair loops ran
    validation_warnings: list[str]  # remaining non-blocking issues


class WeatherForecast(TypedDict):
    """Weather forecast for a single day at the destination.

    Used by the itinerary optimizer to prefer indoor activities on
    rainy days and to flag weather-related risk in the validation step.
    """

    date: str
    condition: str
    temp_max: float
    temp_min: float
    rain_chance: float  # 0-100 percentage
    rain_start: Optional[str]  # expected start hour (e.g. "14:00")
    wind_speed: float


class SeasonalEvent(TypedDict):
    """A seasonal or cultural event at the destination during travel dates."""

    name: str
    category: str
    description: str
    month_start: int
    month_end: int


class WeatherSummary(TypedDict):
    """Aggregated weather statistics for the full travel period."""

    avg_temp_max: float
    avg_temp_min: float
    avg_rain_chance: float
    dominant_condition: str
    severe_weather_days: int
    packing_suggestions: list[str]


class DestinationAnalysis(TypedDict):
    """Complete destination intelligence produced by the analyze_destination node."""

    forecast: list[WeatherForecast]
    alerts: list[dict[str, str]]
    weather_summary: WeatherSummary
    seasonal_events: list[SeasonalEvent]
    travel_advisories: list[str]
    analysis_timestamp: str


class ValidationResult(TypedDict):
    """Output of a deterministic validation pass over the travel plan.

    Validators produce these to surface budget overruns, scheduling
    conflicts, missing bookings, and other issues before approval.
    """

    is_valid: bool
    issues: list[str]
    severity: Literal["error", "warning", "info"]
    suggested_fixes: list[str]


class TravelVibe(TypedDict):
    """Result of an image-based travel vibe analysis.

    Produced when a user uploads an inspiration image. The vision model
    extracts destination hints, mood tags, and preference signals that
    seed the initial planning state.
    """

    destination_suggestions: list[str]
    vibe_tags: list[str]
    budget_tier_guess: Literal["budget", "mid", "luxury"]
    season_preference: str
    activity_bias: list[str]
