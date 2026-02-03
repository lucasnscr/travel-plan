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
    score: float = 0.0
    raw: dict[str, object] = Field(default_factory=dict)
