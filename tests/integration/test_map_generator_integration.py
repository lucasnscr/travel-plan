"""Integration tests for the interactive map generator.

These tests use real Folium to produce HTML files and verify their content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from travel_orchestrator.output.map_generator import (
    generate_interactive_map,
    generate_map_from_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hotel(
    *,
    id: str = "htl-001",
    name: str = "Hotel Paris Centre",
    lat: float = 48.8566,
    lng: float = 2.3522,
    **overrides: Any,
) -> dict[str, Any]:
    hotel: dict[str, Any] = {
        "id": id,
        "name": name,
        "address": "Le Marais, Paris",
        "coordinates": {"lat": lat, "lng": lng},
        "stars": 4,
        "price_per_night": 180.0,
        "currency": "EUR",
        "amenities": ["wifi", "breakfast"],
        "reviews_score": 8.5,
        "distance_to_center_km": 0.5,
        "score": 0.9,
    }
    hotel.update(overrides)
    return hotel


def _make_activity(
    *,
    id: str = "act-001",
    name: str = "Louvre Museum",
    lat: float = 48.8606,
    lng: float = 2.3376,
    **overrides: Any,
) -> dict[str, Any]:
    activity: dict[str, Any] = {
        "id": id,
        "name": name,
        "category": "museum",
        "address": "Rue de Rivoli, Paris",
        "coordinates": {"lat": lat, "lng": lng},
        "duration_minutes": 180,
        "price": 25.0,
        "currency": "EUR",
        "opening_hours": {"monday": "09:00-18:00"},
        "requires_booking": True,
        "indoor": True,
        "description": "World-famous art museum.",
        "score": 0.95,
    }
    activity.update(overrides)
    return activity


def _make_slot(activity_id: str, activity_name: str) -> dict[str, Any]:
    return {
        "activity_id": activity_id,
        "activity_name": activity_name,
        "start_time": "09:00",
        "end_time": "12:00",
        "travel_time_from_previous_minutes": 15,
        "notes": "",
    }


def _make_full_state(
    num_days: int = 3,
    activities_per_day: int = 2,
) -> dict[str, Any]:
    """Build a complete TravelPlannerCore state."""
    activities: list[dict[str, Any]] = []
    days: list[dict[str, Any]] = []
    activity_ids: list[str] = []

    act_counter = 0
    for day_num in range(1, num_days + 1):
        slots: list[dict[str, Any]] = []
        for _ in range(activities_per_day):
            act_counter += 1
            act_id = f"act-{act_counter:03d}"
            activities.append(
                _make_activity(
                    id=act_id,
                    name=f"Activity {act_counter}",
                    lat=48.85 + act_counter * 0.005,
                    lng=2.35 + act_counter * 0.003,
                )
            )
            activity_ids.append(act_id)
            slots.append(_make_slot(act_id, f"Activity {act_counter}"))
        days.append({
            "date": f"2025-07-{day_num:02d}",
            "day_number": day_num,
            "theme": f"Day {day_num} Theme",
            "slots": slots,
            "weather_condition": "sunny",
            "notes": "",
        })

    return {
        "plan_id": "plan_integ",
        "destination": "Paris",
        "dates": {"start_date": "2025-07-01", "end_date": "2025-07-10"},
        "budget": {"total": 5000.0, "currency": "EUR", "flexibility": 0.1},
        "traveler_profile": {"interests": ["culture"], "pace": "moderate", "group_size": 2},
        "selected_flight_id": None,
        "selected_hotel_id": "htl-001",
        "selected_activity_ids": activity_ids,
        "current_cost": 3000.0,
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": [],
        "alternative_plans": {},
        "destination_analysis": None,
        "hotel_options": [_make_hotel()],
        "activity_options": activities,
        "optimized_itinerary": {
            "days": days,
            "unscheduled_activity_ids": [],
            "optimization_method": "deterministic_fallback",
            "validation_iterations": 0,
            "validation_warnings": [],
        },
    }


# ===================================================================
# Integration tests
# ===================================================================


@pytest.mark.integration
class TestMapGenerationIntegration:
    def test_generates_valid_html_file(self, tmp_path: Path) -> None:
        """Real Folium generates an HTML file with expected content."""
        hotel = _make_hotel()
        act1 = _make_activity(id="a1", name="Louvre Museum", lat=48.8606, lng=2.3376)
        act2 = _make_activity(id="a2", name="Seine Cruise", lat=48.8584, lng=2.3475)

        out = tmp_path / "map.html"
        result = generate_interactive_map(hotel, {1: [act1, act2]}, "Paris", str(out))

        assert out.exists()
        assert result.endswith("map.html")

        html = out.read_text()
        assert "<html>" in html.lower() or "<!doctype" in html.lower()
        assert "Hotel Paris Centre" in html
        assert "Louvre Museum" in html
        assert "Seine Cruise" in html

    def test_single_day_trip(self, tmp_path: Path) -> None:
        """Single day with activities produces valid map."""
        hotel = _make_hotel()
        act = _make_activity(id="a1", name="Eiffel Tower", lat=48.8584, lng=2.2945)

        out = tmp_path / "single.html"
        result = generate_interactive_map(hotel, {1: [act]}, "Paris", str(out))

        assert out.exists()
        html = out.read_text()
        assert "Eiffel Tower" in html
        assert "Day 1" in html

    def test_seven_day_trip(self, tmp_path: Path) -> None:
        """7-day trip uses all base colours without cycling."""
        hotel = _make_hotel()
        activities_by_day: dict[int, list[dict[str, Any]]] = {}
        for d in range(1, 8):
            activities_by_day[d] = [
                _make_activity(id=f"a-{d}", name=f"Day{d} Act", lat=48.85 + d * 0.01, lng=2.35)
            ]

        out = tmp_path / "seven_day.html"
        result = generate_interactive_map(hotel, activities_by_day, "Paris", str(out))

        assert out.exists()
        html = out.read_text()
        for d in range(1, 8):
            assert f"Day {d}" in html

    def test_ten_day_trip_cycles_colors(self, tmp_path: Path) -> None:
        """10-day trip forces colour cycling. No crash expected."""
        hotel = _make_hotel()
        activities_by_day: dict[int, list[dict[str, Any]]] = {}
        for d in range(1, 11):
            activities_by_day[d] = [
                _make_activity(id=f"a-{d}", name=f"Day{d} Act", lat=48.85 + d * 0.005, lng=2.35)
            ]

        out = tmp_path / "ten_day.html"
        result = generate_interactive_map(hotel, activities_by_day, "Paris", str(out))

        assert out.exists()
        html = out.read_text()
        assert "Day 10" in html

    def test_generate_from_state(self, tmp_path: Path) -> None:
        """Full pipeline from TravelPlannerCore state to HTML."""
        state = _make_full_state(num_days=3, activities_per_day=2)

        out = tmp_path / "from_state.html"
        result = generate_map_from_state(state, str(out))

        assert out.exists()
        assert result.endswith("from_state.html")

        html = out.read_text()
        assert "Hotel Paris Centre" in html
        assert "Activity 1" in html
        assert "Day 1" in html
        assert "Day 3" in html

    def test_activities_without_coords_graceful(self, tmp_path: Path) -> None:
        """Activities missing coordinates are skipped gracefully."""
        hotel = _make_hotel()
        good = _make_activity(id="good", name="Good Activity", lat=48.86, lng=2.34)
        bad = _make_activity(id="bad", name="Bad Activity")
        bad["coordinates"] = {}

        out = tmp_path / "graceful.html"
        result = generate_interactive_map(hotel, {1: [good, bad]}, "Paris", str(out))

        assert out.exists()
        html = out.read_text()
        assert "Good Activity" in html
        # Bad Activity should not appear as a marker but doesn't crash
