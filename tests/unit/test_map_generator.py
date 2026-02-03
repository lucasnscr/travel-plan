"""Unit tests for the interactive map generator."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from travel_orchestrator.output.map_generator import (
    ACTIVITY_MARKER_ICON,
    ACTIVITY_MARKER_PREFIX,
    DEFAULT_MAP_ZOOM,
    DEFAULT_TILE_PROVIDER,
    HOTEL_MARKER_COLOR,
    HOTEL_MARKER_ICON,
    HOTEL_MARKER_PREFIX,
    MAP_DAY_COLORS,
    ROUTE_DASH_ARRAY,
    ROUTE_OPACITY,
    ROUTE_WEIGHT,
    _POLYLINE_COLORS,
    _build_activities_by_day,
    _build_day_route_points,
    _build_popup_html,
    _has_valid_coordinates,
    add_route_layer,
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
        "description": "World-famous art museum housing the Mona Lisa.",
        "score": 0.95,
    }
    activity.update(overrides)
    return activity


def _make_slot(
    activity_id: str = "act-001",
    activity_name: str = "Louvre Museum",
) -> dict[str, Any]:
    return {
        "activity_id": activity_id,
        "activity_name": activity_name,
        "start_time": "09:00",
        "end_time": "12:00",
        "travel_time_from_previous_minutes": 15,
        "notes": "",
    }


def _make_state(
    *,
    with_itinerary: bool = True,
    num_days: int = 2,
    activities_per_day: int = 2,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a complete TravelPlannerCore state for testing."""
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
            slots.append(_make_slot(activity_id=act_id, activity_name=f"Activity {act_counter}"))
        days.append({
            "date": f"2025-07-{day_num:02d}",
            "day_number": day_num,
            "theme": f"Day {day_num} Theme",
            "slots": slots,
            "weather_condition": "sunny",
            "notes": "",
        })

    itinerary: dict[str, Any] | None = None
    if with_itinerary:
        itinerary = {
            "days": days,
            "unscheduled_activity_ids": [],
            "optimization_method": "deterministic_fallback",
            "validation_iterations": 0,
            "validation_warnings": [],
        }

    state: dict[str, Any] = {
        "plan_id": "plan_test",
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
        "optimized_itinerary": itinerary,
    }
    state.update(overrides)
    return state


# ===================================================================
# _has_valid_coordinates
# ===================================================================


class TestHasValidCoordinates:
    def test_valid(self) -> None:
        assert _has_valid_coordinates({"coordinates": {"lat": 48.85, "lng": 2.35}}) is True

    def test_missing_coordinates_key(self) -> None:
        assert _has_valid_coordinates({"name": "no coords"}) is False

    def test_coordinates_not_dict(self) -> None:
        assert _has_valid_coordinates({"coordinates": "bad"}) is False

    def test_missing_lat(self) -> None:
        assert _has_valid_coordinates({"coordinates": {"lng": 2.35}}) is False

    def test_missing_lng(self) -> None:
        assert _has_valid_coordinates({"coordinates": {"lat": 48.85}}) is False

    def test_non_numeric_lat(self) -> None:
        assert _has_valid_coordinates({"coordinates": {"lat": "bad", "lng": 2.35}}) is False

    def test_none_coordinates(self) -> None:
        assert _has_valid_coordinates({"coordinates": None}) is False

    def test_integer_coordinates(self) -> None:
        assert _has_valid_coordinates({"coordinates": {"lat": 48, "lng": 2}}) is True

    def test_zero_coordinates(self) -> None:
        assert _has_valid_coordinates({"coordinates": {"lat": 0.0, "lng": 0.0}}) is True


# ===================================================================
# _build_activities_by_day
# ===================================================================


class TestBuildActivitiesByDay:
    def test_multi_day_mapping(self) -> None:
        state = _make_state(num_days=3, activities_per_day=2)
        result = _build_activities_by_day(state)
        assert set(result.keys()) == {1, 2, 3}
        assert len(result[1]) == 2
        assert len(result[2]) == 2
        assert len(result[3]) == 2

    def test_missing_activity_id_skipped(self) -> None:
        state = _make_state(num_days=1, activities_per_day=1)
        # Replace activity_options with empty list so lookup fails
        state["activity_options"] = []
        result = _build_activities_by_day(state)
        assert result == {}

    def test_empty_itinerary_days(self) -> None:
        state = _make_state(with_itinerary=True, num_days=0)
        result = _build_activities_by_day(state)
        assert result == {}

    def test_no_itinerary_returns_empty(self) -> None:
        state = _make_state(with_itinerary=False)
        result = _build_activities_by_day(state)
        assert result == {}

    def test_day_with_no_slots(self) -> None:
        state = _make_state(num_days=1, activities_per_day=0)
        result = _build_activities_by_day(state)
        assert result == {}


# ===================================================================
# _build_day_route_points
# ===================================================================


class TestBuildDayRoutePoints:
    def test_hotel_to_activities_and_back(self) -> None:
        hotel = _make_hotel(lat=48.85, lng=2.35)
        coords = [(48.86, 2.34), (48.87, 2.33)]
        result = _build_day_route_points(hotel, coords)
        assert result == [(48.85, 2.35), (48.86, 2.34), (48.87, 2.33), (48.85, 2.35)]

    def test_no_activities_returns_empty(self) -> None:
        hotel = _make_hotel()
        result = _build_day_route_points(hotel, [])
        assert result == []

    def test_single_activity(self) -> None:
        hotel = _make_hotel(lat=10.0, lng=20.0)
        result = _build_day_route_points(hotel, [(11.0, 21.0)])
        assert result == [(10.0, 20.0), (11.0, 21.0), (10.0, 20.0)]


# ===================================================================
# _build_popup_html
# ===================================================================


class TestBuildPopupHtml:
    def test_contains_title(self) -> None:
        html = _build_popup_html("My Title", [])
        assert "<b>My Title</b>" in html

    def test_contains_all_rows(self) -> None:
        html = _build_popup_html("Test", [("Key1", "Val1"), ("Key2", "Val2")])
        assert "Key1" in html
        assert "Val1" in html
        assert "Key2" in html
        assert "Val2" in html

    def test_empty_value_rows_skipped(self) -> None:
        html = _build_popup_html("Test", [("Shown", "yes"), ("Hidden", "")])
        assert "Shown" in html
        assert "Hidden" not in html


# ===================================================================
# add_route_layer
# ===================================================================


class TestAddRouteLayer:
    def test_creates_polyline(self) -> None:
        fg = MagicMock()
        points = [(48.85, 2.35), (48.86, 2.34), (48.85, 2.35)]
        with patch("travel_orchestrator.output.map_generator.folium") as mock_folium:
            mock_polyline = MagicMock()
            mock_folium.PolyLine.return_value = mock_polyline
            add_route_layer(fg, points, "#3186cc")
            mock_folium.PolyLine.assert_called_once_with(
                locations=points,
                color="#3186cc",
                weight=ROUTE_WEIGHT,
                opacity=ROUTE_OPACITY,
                dash_array=ROUTE_DASH_ARRAY,
            )
            mock_polyline.add_to.assert_called_once_with(fg)

    def test_skips_single_point(self) -> None:
        fg = MagicMock()
        with patch("travel_orchestrator.output.map_generator.folium") as mock_folium:
            add_route_layer(fg, [(48.85, 2.35)], "#3186cc")
            mock_folium.PolyLine.assert_not_called()

    def test_skips_empty_points(self) -> None:
        fg = MagicMock()
        with patch("travel_orchestrator.output.map_generator.folium") as mock_folium:
            add_route_layer(fg, [], "#3186cc")
            mock_folium.PolyLine.assert_not_called()

    def test_custom_weight_and_opacity(self) -> None:
        fg = MagicMock()
        points = [(1.0, 2.0), (3.0, 4.0)]
        with patch("travel_orchestrator.output.map_generator.folium") as mock_folium:
            mock_folium.PolyLine.return_value = MagicMock()
            add_route_layer(fg, points, "#000", weight=5, opacity=0.5, dash_array=None)
            mock_folium.PolyLine.assert_called_once_with(
                locations=points,
                color="#000",
                weight=5,
                opacity=0.5,
                dash_array=None,
            )


# ===================================================================
# generate_interactive_map
# ===================================================================


class TestGenerateInteractiveMap:
    @patch("travel_orchestrator.output.map_generator.folium")
    def test_creates_map_centered_on_hotel(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_folium.LayerControl.return_value = MagicMock()
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()

        hotel = _make_hotel(lat=48.85, lng=2.35)
        generate_interactive_map(hotel, {}, "Paris", "/tmp/test.html")

        mock_folium.Map.assert_called_once_with(
            location=[48.85, 2.35],
            zoom_start=DEFAULT_MAP_ZOOM,
            tiles=DEFAULT_TILE_PROVIDER,
        )

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_hotel_marker_added(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_fg = MagicMock()
        mock_folium.FeatureGroup.return_value = mock_fg
        mock_folium.LayerControl.return_value = MagicMock()
        mock_marker = MagicMock()
        mock_folium.Marker.return_value = mock_marker
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()

        hotel = _make_hotel()
        generate_interactive_map(hotel, {}, "Paris", "/tmp/test.html")

        # At least one Marker call with hotel coordinates
        marker_calls = mock_folium.Marker.call_args_list
        hotel_call = [c for c in marker_calls if c.kwargs.get("location") == [48.8566, 2.3522]]
        assert len(hotel_call) >= 1

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_activity_markers_per_day(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_folium.LayerControl.return_value = MagicMock()
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()
        mock_folium.PolyLine.return_value = MagicMock()

        hotel = _make_hotel()
        act1 = _make_activity(id="a1", name="Act1", lat=48.86, lng=2.34)
        act2 = _make_activity(id="a2", name="Act2", lat=48.87, lng=2.33)
        activities_by_day = {1: [act1], 2: [act2]}

        generate_interactive_map(hotel, activities_by_day, "Paris", "/tmp/test.html")

        # FeatureGroup called for: Hotel, Day 1, Day 2
        fg_calls = mock_folium.FeatureGroup.call_args_list
        fg_names = [c.kwargs.get("name") for c in fg_calls]
        assert "Hotel" in fg_names
        assert "Day 1" in fg_names
        assert "Day 2" in fg_names

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_layer_control_added(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_lc = MagicMock()
        mock_folium.LayerControl.return_value = mock_lc
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()

        hotel = _make_hotel()
        generate_interactive_map(hotel, {}, "Paris", "/tmp/test.html")

        mock_folium.LayerControl.assert_called_once_with(collapsed=False)
        mock_lc.add_to.assert_called_once_with(mock_map)

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_saves_to_output_path(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_folium.LayerControl.return_value = MagicMock()
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()

        hotel = _make_hotel()
        result = generate_interactive_map(hotel, {}, "Paris", "/tmp/my_map.html")

        mock_map.save.assert_called_once_with("/tmp/my_map.html")
        assert result.endswith("my_map.html")

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_color_cycling_for_many_days(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_folium.LayerControl.return_value = MagicMock()
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()
        mock_folium.PolyLine.return_value = MagicMock()

        hotel = _make_hotel()
        activities_by_day = {}
        for d in range(1, 13):
            activities_by_day[d] = [
                _make_activity(id=f"a-{d}", lat=48.85 + d * 0.01, lng=2.35)
            ]

        # Should not raise — colors cycle
        generate_interactive_map(hotel, activities_by_day, "Paris", "/tmp/test.html")

        # 12 day groups + 1 hotel group = 13 FeatureGroup calls
        assert mock_folium.FeatureGroup.call_count == 13

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_empty_activities_by_day(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_folium.LayerControl.return_value = MagicMock()
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()

        hotel = _make_hotel()
        generate_interactive_map(hotel, {}, "Paris", "/tmp/test.html")

        # Only hotel FeatureGroup
        assert mock_folium.FeatureGroup.call_count == 1

    @patch("travel_orchestrator.output.map_generator.folium")
    def test_activities_without_coordinates_skipped(self, mock_folium: MagicMock) -> None:
        mock_map = MagicMock()
        mock_folium.Map.return_value = mock_map
        mock_folium.FeatureGroup.return_value = MagicMock()
        mock_folium.LayerControl.return_value = MagicMock()
        mock_folium.Marker.return_value = MagicMock()
        mock_folium.Icon.return_value = MagicMock()
        mock_folium.Popup.return_value = MagicMock()
        mock_folium.PolyLine.return_value = MagicMock()

        hotel = _make_hotel()
        bad_act = _make_activity(id="bad")
        bad_act["coordinates"] = {}  # invalid
        good_act = _make_activity(id="good", lat=48.87, lng=2.33)

        generate_interactive_map(hotel, {1: [bad_act, good_act]}, "Paris", "/tmp/test.html")

        # Only 2 markers: hotel + good_act (bad_act skipped)
        assert mock_folium.Marker.call_count == 2


# ===================================================================
# generate_map_from_state
# ===================================================================


class TestGenerateMapFromState:
    @patch("travel_orchestrator.output.map_generator.generate_interactive_map")
    def test_extracts_hotel_and_activities(self, mock_gen: MagicMock) -> None:
        mock_gen.return_value = "/tmp/map.html"
        state = _make_state(num_days=2, activities_per_day=1)

        result = generate_map_from_state(state, "/tmp/map.html")

        assert result == "/tmp/map.html"
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["hotel"]["id"] == "htl-001"
        assert call_kwargs["destination"] == "Paris"
        assert 1 in call_kwargs["activities_by_day"]
        assert 2 in call_kwargs["activities_by_day"]

    @patch("travel_orchestrator.output.map_generator.generate_interactive_map")
    def test_no_hotel_returns_empty(self, mock_gen: MagicMock) -> None:
        state = _make_state()
        state["hotel_options"] = []

        result = generate_map_from_state(state, "/tmp/map.html")

        assert result == ""
        mock_gen.assert_not_called()

    @patch("travel_orchestrator.output.map_generator.generate_interactive_map")
    def test_no_itinerary_returns_empty(self, mock_gen: MagicMock) -> None:
        state = _make_state(with_itinerary=False)

        result = generate_map_from_state(state, "/tmp/map.html")

        assert result == ""
        mock_gen.assert_not_called()

    @patch("travel_orchestrator.output.map_generator.generate_interactive_map")
    def test_no_selected_hotel_id_returns_empty(self, mock_gen: MagicMock) -> None:
        state = _make_state()
        state["selected_hotel_id"] = None

        result = generate_map_from_state(state, "/tmp/map.html")

        assert result == ""
        mock_gen.assert_not_called()

    @patch("travel_orchestrator.output.map_generator.generate_interactive_map")
    def test_hotel_missing_coordinates_returns_empty(self, mock_gen: MagicMock) -> None:
        state = _make_state()
        state["hotel_options"] = [_make_hotel()]
        state["hotel_options"][0]["coordinates"] = {}

        result = generate_map_from_state(state, "/tmp/map.html")

        assert result == ""
        mock_gen.assert_not_called()


# ===================================================================
# Constants
# ===================================================================


class TestConstants:
    def test_day_colors_length(self) -> None:
        assert len(MAP_DAY_COLORS) == 10

    def test_polyline_colors_same_length(self) -> None:
        assert len(_POLYLINE_COLORS) == len(MAP_DAY_COLORS)

    def test_default_zoom_reasonable(self) -> None:
        assert 10 <= DEFAULT_MAP_ZOOM <= 18
