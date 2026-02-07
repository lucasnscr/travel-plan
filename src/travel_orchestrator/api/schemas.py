"""Pydantic schemas for the Travel Orchestrator REST & WebSocket API.

These models define the contract between the React frontend and the
FastAPI backend.  All models use ``from_attributes=True`` to allow
construction from LangGraph TypedDicts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """Incoming trip planning request."""

    destination: str
    start_date: str  # ISO 8601 date
    end_date: str
    budget: float = 5000.0
    currency: str = "USD"
    num_travelers: int = 2
    preferences: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class Coordinates(BaseModel):
    lat: float
    lng: float


class ActivitySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    place_id: str = ""
    name: str = ""
    type: str = ""  # category
    time_slot: str | None = None
    duration: int = 60  # minutes
    cost: float = 0.0
    currency: str = "USD"
    photos: list[str] = Field(default_factory=list)
    rating: float = 0.0
    coordinates: Coordinates | None = None


class TransportSegment(BaseModel):
    from_activity: str
    to_activity: str
    mode: str = "walk"  # walk, drive, transit
    duration_minutes: int = 0


class WeatherInfo(BaseModel):
    condition: str = "unknown"
    temp_max: float = 0.0
    temp_min: float = 0.0
    rain_chance: float = 0.0


class DayPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str = ""
    day_number: int = 1
    theme: str = ""
    activities: list[ActivitySchema] = Field(default_factory=list)
    hotel: str | None = None
    weather: WeatherInfo | None = None
    transport_segments: list[TransportSegment] = Field(default_factory=list)


class HotelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = ""
    name: str = ""
    address: str = ""
    stars: int = 0
    price_per_night: float = 0.0
    currency: str = "USD"
    reviews_score: float = 0.0
    score: float = 0.0
    amenities: list[str] = Field(default_factory=list)
    coordinates: Coordinates | None = None


class WeatherSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    avg_temp_max: float = 0.0
    avg_temp_min: float = 0.0
    dominant_condition: str = "unknown"
    packing_suggestions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trip plan (main response)
# ---------------------------------------------------------------------------


class TripPlan(BaseModel):
    """Full trip plan returned by POST /api/plan and GET /api/trip/{id}."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: str = ""
    destination: str = ""
    start_date: str = ""
    end_date: str = ""
    days: list[DayPlan] = Field(default_factory=list)
    hotels: list[HotelSchema] = Field(default_factory=list)
    activities: list[ActivitySchema] = Field(default_factory=list)
    total_cost: float = 0.0
    currency: str = "USD"
    weather_summary: WeatherSummarySchema | None = None
    approval_status: str = "pending"
    map_url: str = ""
    pdf_url: str = ""


# ---------------------------------------------------------------------------
# Itinerary update (PATCH)
# ---------------------------------------------------------------------------


class ItineraryUpdate(BaseModel):
    days: list[DayPlan]


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    feedback: str = ""


# ---------------------------------------------------------------------------
# Orchestrator events (WebSocket payloads)
# ---------------------------------------------------------------------------


class OrchestratorEventSchema(BaseModel):
    timestamp: int = 0
    node: str = ""
    agent: str = ""
    action: str = ""  # node_started, node_completed, tool_call, etc.
    status: str = ""  # running, completed, error, success
    latency: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chat message
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = ""
    rich_content: dict[str, Any] | None = None
    timestamp: int = 0
