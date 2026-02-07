"""Pydantic models for the Activities/Places MCP server.

Provides validated input/output models for Google Places API integration
and all 9 MCP tools (discover_activities + 8 new tools).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Location models
# ---------------------------------------------------------------------------


class GeoLocation(BaseModel):
    """Geographic coordinates."""

    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class Viewport(BaseModel):
    """Geographic viewport (bounding box)."""

    low: GeoLocation
    high: GeoLocation


# ---------------------------------------------------------------------------
# Place models
# ---------------------------------------------------------------------------


class PlacePhoto(BaseModel):
    """A photo associated with a place."""

    photo_reference: str = Field("", description="Google photo resource name")
    url: str = Field("", description="Resolved photo URL")
    width: int = Field(0, description="Photo width in pixels")
    height: int = Field(0, description="Photo height in pixels")
    attributions: list[str] = Field(default_factory=list)


class PlaceReview(BaseModel):
    """A user review for a place."""

    author: str = Field("", description="Reviewer display name")
    rating: float = Field(0.0, ge=0, le=5, description="Individual rating 0-5")
    text: str = Field("", description="Review text")
    time: str = Field("", description="ISO timestamp or relative time")
    language: str = Field("", description="Review language code")


class PlaceOpeningHours(BaseModel):
    """Opening hours for a place."""

    open_now: bool | None = Field(None, description="Whether currently open")
    weekday_text: list[str] = Field(
        default_factory=list, description="Human-readable hours per day"
    )


class Place(BaseModel):
    """A place/activity from Google Places or mock provider."""

    place_id: str = Field("", description="Google Place ID or mock ID")
    name: str = Field("", description="Place name")
    category: str = Field("", description="Activity category")
    address: str = Field("", description="Formatted address")
    location: GeoLocation = Field(
        default_factory=lambda: GeoLocation(lat=0.0, lng=0.0)
    )
    rating: float = Field(0.0, ge=0, le=5, description="Average rating 0-5")
    user_ratings_total: int = Field(0, ge=0, description="Number of ratings")
    price_level: int | None = Field(
        None, ge=0, le=4, description="Price level 0-4"
    )
    types: list[str] = Field(default_factory=list, description="Google place types")
    photos: list[PlacePhoto] = Field(default_factory=list)
    opening_hours: PlaceOpeningHours | None = None
    website: str | None = None
    phone: str | None = None
    description: str = Field("", description="Editorial summary or description")
    data_source: str = Field("mock", description="Data provider identifier")


class PlaceDetail(Place):
    """Extended place details with reviews, full hours, etc."""

    reviews: list[PlaceReview] = Field(default_factory=list)
    viewport: Viewport | None = None
    url: str = Field("", description="Google Maps URL")
    business_status: str = Field("OPERATIONAL")
    editorial_summary: str = Field("")


# ---------------------------------------------------------------------------
# Direction models
# ---------------------------------------------------------------------------


class DirectionStep(BaseModel):
    """A single step in a route."""

    instruction: str = Field("", description="HTML instruction text")
    distance_meters: int = Field(0)
    duration_seconds: int = Field(0)
    travel_mode: str = Field("WALKING")


class DirectionRoute(BaseModel):
    """A complete route between two points."""

    summary: str = Field("")
    distance_meters: int = Field(0)
    duration_seconds: int = Field(0)
    start_address: str = Field("")
    end_address: str = Field("")
    steps: list[DirectionStep] = Field(default_factory=list)
    polyline: str = Field("", description="Encoded polyline string")
    data_source: str = Field("mock")


# ---------------------------------------------------------------------------
# Geocoding models
# ---------------------------------------------------------------------------


class GeocodeResult(BaseModel):
    """A geocoding result (address <-> coordinates)."""

    place_id: str = Field("")
    formatted_address: str = Field("")
    location: GeoLocation = Field(
        default_factory=lambda: GeoLocation(lat=0.0, lng=0.0)
    )
    types: list[str] = Field(default_factory=list)
    data_source: str = Field("mock")


# ---------------------------------------------------------------------------
# Input models for MCP tools
# ---------------------------------------------------------------------------


class SearchActivitiesInput(BaseModel):
    """Input for search_activities tool."""

    query: str = Field(..., min_length=1, description="Search query text")
    location: str = Field(..., min_length=1, description="City or area name")
    language: str = Field("pt-BR", description="Language code")
    max_results: int = Field(20, ge=1, le=60)


class SearchRestaurantsInput(BaseModel):
    """Input for search_restaurants tool."""

    location: str = Field(..., min_length=1, description="City or area name")
    cuisine: str | None = Field(None, description="Cuisine type filter")
    price_level: int | None = Field(None, ge=0, le=4)
    language: str = Field("pt-BR")
    max_results: int = Field(20, ge=1, le=60)


class NearbySearchInput(BaseModel):
    """Input for nearby_search tool."""

    latitude: float = Field(..., description="Center latitude")
    longitude: float = Field(..., description="Center longitude")
    radius_meters: int = Field(1000, ge=100, le=50000)
    place_type: str = Field("tourist_attraction", description="Google place type")
    language: str = Field("pt-BR")
    max_results: int = Field(20, ge=1, le=60)


class GetPlaceDetailsInput(BaseModel):
    """Input for get_place_details tool."""

    place_id: str = Field(..., min_length=1, description="Google Place ID")
    language: str = Field("pt-BR")


class GetPlacePhotosInput(BaseModel):
    """Input for get_place_photos tool."""

    place_id: str = Field(..., min_length=1, description="Google Place ID")
    max_photos: int = Field(5, ge=1, le=10)


class GetDirectionsInput(BaseModel):
    """Input for get_directions tool."""

    origin: str = Field(..., min_length=1, description="Origin address or place")
    destination: str = Field(..., min_length=1, description="Destination address")
    mode: str = Field(
        "walking",
        description="Travel mode: walking, driving, transit, bicycling",
    )
    language: str = Field("pt-BR")


class GeocodeInput(BaseModel):
    """Input for geocode tool."""

    address: str = Field(..., min_length=1, description="Address to geocode")
    language: str = Field("pt-BR")


class ReverseGeocodeInput(BaseModel):
    """Input for reverse_geocode tool."""

    latitude: float
    longitude: float
    language: str = Field("pt-BR")
