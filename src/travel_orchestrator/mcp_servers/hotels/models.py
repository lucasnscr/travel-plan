"""Pydantic models for the hotel search MCP server."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HotelLocation(BaseModel):
    """Geographic location of a hotel."""

    lat: float = 0.0
    lng: float = 0.0
    area: str | None = None


class HotelSearchInput(BaseModel):
    """Validated input for the search_hotels tool."""

    destination: str = Field(..., min_length=1, description="City or region name")
    check_in: str = Field(..., description="ISO date YYYY-MM-DD")
    check_out: str = Field(..., description="ISO date YYYY-MM-DD")
    guests: int = Field(1, ge=1, le=10)
    preferences: dict[str, object] = Field(default_factory=dict)
    location_centrality: float = Field(0.5, ge=0.0, le=1.0)
    min_stars: int | None = Field(None, ge=1, le=5)
    amenities: list[str] = Field(default_factory=list)


class HotelSearchByCoordinatesInput(BaseModel):
    """Validated input for search_by_coordinates tool."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(5.0, ge=0.1, le=50.0)
    check_in: str = Field(..., description="ISO date YYYY-MM-DD")
    check_out: str = Field(..., description="ISO date YYYY-MM-DD")
    adults: int = Field(1, ge=1, le=10)


class HotelCompareInput(BaseModel):
    """Validated input for compare_hotels tool."""

    hotel_ids: list[str] = Field(..., min_length=2, max_length=10)


# ---------------------------------------------------------------------------
# Hotel detail models
# ---------------------------------------------------------------------------


class Room(BaseModel):
    """A bookable room type."""

    room_id: str | None = None
    name: str = "Standard Room"
    type: str = "standard"
    max_occupancy: int = 2
    bed_type: str | None = None
    size_sqm: float | None = None
    price_per_night: float | None = None
    currency: str | None = None
    breakfast_included: bool = False
    cancellation_policy: str | None = None


class Rate(BaseModel):
    """A pricing option for a room."""

    rate_id: str | None = None
    room_name: str = "Standard Room"
    price_per_night: float
    total_price: float
    currency: str = "USD"
    meal_plan: str = "room_only"
    cancellation: str = "non_refundable"
    payment: str = "pay_now"


class Review(BaseModel):
    """A guest review summary."""

    overall_score: float
    total_reviews: int = 0
    categories: dict[str, float] = Field(default_factory=dict)
    recent_highlights: list[str] = Field(default_factory=list)


class Facility(BaseModel):
    """A hotel facility/amenity."""

    name: str
    category: str = "general"
    available: bool = True


class HotelDetail(BaseModel):
    """Full hotel details returned by get_hotel_details."""

    hotel_id: str
    name: str
    description: str | None = None
    stars: int | None = None
    address: str | None = None
    location: HotelLocation = Field(default_factory=HotelLocation)
    check_in_time: str | None = None
    check_out_time: str | None = None
    photos: list[str] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    rates: list[Rate] = Field(default_factory=list)
    review: Review | None = None
    facilities: list[Facility] = Field(default_factory=list)
    policies: dict[str, str] = Field(default_factory=dict)
    data_source: str = "mock"


class HotelResult(BaseModel):
    """Normalised hotel option returned by the server."""

    provider: str = "enuygun"
    name: str
    stars: int | None = None
    review_score: float | None = None
    price_total: float | None = None
    currency: str | None = None
    nightly_price_avg: float | None = None
    location: HotelLocation = Field(default_factory=HotelLocation)
    distance_to_center_km: float | None = None
    amenities: list[str] = Field(default_factory=list)
    deep_link: str | None = None
    photos: list[str] = Field(default_factory=list)
    score: float = 0.0
    data_source: str = "mock"
    raw: dict[str, object] = Field(default_factory=dict)
