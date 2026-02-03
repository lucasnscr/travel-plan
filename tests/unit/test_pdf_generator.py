"""Unit and integration tests for the PDF itinerary generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from reportlab.platypus import PageBreak, Paragraph, Table

from travel_orchestrator.output.pdf_generator import (
    CostBreakdown,
    _build_activities_by_day,
    _build_budget_section,
    _build_cover_page,
    _build_itinerary_section,
    _build_stock_placeholder,
    _build_styles,
    _build_summary_section,
    _build_vouchers_section,
    _compute_cost_breakdown,
    _compute_nights,
    _make_confirmation_code,
    _stars_str,
    _weather_icon,
    generate_itinerary_pdf,
    generate_pdf_from_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hotel(
    *,
    id: str = "htl-001",
    name: str = "Hotel Paris Centre",
    **overrides: Any,
) -> dict[str, Any]:
    hotel: dict[str, Any] = {
        "id": id,
        "name": name,
        "address": "Le Marais, Paris",
        "coordinates": {"lat": 48.8566, "lng": 2.3522},
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
    requires_booking: bool = True,
    **overrides: Any,
) -> dict[str, Any]:
    activity: dict[str, Any] = {
        "id": id,
        "name": name,
        "category": "museum",
        "address": "Rue de Rivoli, Paris",
        "coordinates": {"lat": 48.8606, "lng": 2.3376},
        "duration_minutes": 180,
        "price": 25.0,
        "currency": "EUR",
        "opening_hours": {"monday": "09:00-18:00"},
        "requires_booking": requires_booking,
        "indoor": True,
        "description": "World-famous art museum.",
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


def _make_day(
    day_number: int = 1,
    slots: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    day: dict[str, Any] = {
        "date": f"2025-07-{day_number:02d}",
        "day_number": day_number,
        "theme": f"Day {day_number} Theme",
        "slots": slots or [],
        "weather_condition": "sunny",
        "notes": "",
    }
    day.update(overrides)
    return day


def _make_cost_breakdown(**overrides: Any) -> CostBreakdown:
    cb: dict[str, Any] = {
        "flight_cost": 500.0,
        "hotel_cost": 1620.0,
        "activity_cost": 120.0,
        "total_cost": 2240.0,
        "budget_total": 5000.0,
        "currency": "EUR",
    }
    cb.update(overrides)
    return CostBreakdown(**cb)


def _make_state(
    *,
    with_itinerary: bool = True,
    num_days: int = 2,
    activities_per_day: int = 2,
    **overrides: Any,
) -> dict[str, Any]:
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
                _make_activity(id=act_id, name=f"Activity {act_counter}")
            )
            activity_ids.append(act_id)
            slots.append(_make_slot(activity_id=act_id, activity_name=f"Activity {act_counter}"))
        days.append(_make_day(day_number=day_num, slots=slots))

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
# _compute_nights
# ===================================================================


class TestComputeNights:
    def test_multi_day(self) -> None:
        assert _compute_nights({"start_date": "2025-07-01", "end_date": "2025-07-10"}) == 9

    def test_same_day(self) -> None:
        assert _compute_nights({"start_date": "2025-07-01", "end_date": "2025-07-01"}) == 1

    def test_missing_dates(self) -> None:
        assert _compute_nights({}) == 0

    def test_invalid_dates(self) -> None:
        assert _compute_nights({"start_date": "bad", "end_date": "bad"}) == 0


# ===================================================================
# _compute_cost_breakdown
# ===================================================================


class TestComputeCostBreakdown:
    def test_full_breakdown(self) -> None:
        state = _make_state(num_days=1, activities_per_day=2)
        cb = _compute_cost_breakdown(state)
        assert cb["hotel_cost"] == 180.0 * 9  # 9 nights
        assert cb["activity_cost"] == 25.0 * 2  # 2 activities
        assert cb["flight_cost"] == 0.0  # no flight selected
        assert cb["total_cost"] == cb["hotel_cost"] + cb["activity_cost"]
        assert cb["currency"] == "EUR"
        assert cb["budget_total"] == 5000.0

    def test_no_hotel(self) -> None:
        state = _make_state()
        state["selected_hotel_id"] = None
        cb = _compute_cost_breakdown(state)
        assert cb["hotel_cost"] == 0.0

    def test_no_activities(self) -> None:
        state = _make_state()
        state["selected_activity_ids"] = []
        cb = _compute_cost_breakdown(state)
        assert cb["activity_cost"] == 0.0

    def test_with_flight(self) -> None:
        state = _make_state()
        state["selected_flight_id"] = "flt-001"
        state["flight_options"] = [{"id": "flt-001", "price": 350.0}]
        cb = _compute_cost_breakdown(state)
        assert cb["flight_cost"] == 350.0 * 2  # group_size=2

    def test_rounding(self) -> None:
        state = _make_state(num_days=1, activities_per_day=1)
        state["activity_options"][0]["price"] = 33.33
        cb = _compute_cost_breakdown(state)
        assert cb["activity_cost"] == 33.33
        # total should be rounded to 2 decimals
        assert cb["total_cost"] == round(cb["hotel_cost"] + 33.33, 2)


# ===================================================================
# _build_activities_by_day
# ===================================================================


class TestBuildActivitiesByDay:
    def test_multi_day(self) -> None:
        state = _make_state(num_days=3, activities_per_day=1)
        result = _build_activities_by_day(state)
        assert set(result.keys()) == {1, 2, 3}

    def test_missing_activity_skipped(self) -> None:
        state = _make_state(num_days=1, activities_per_day=1)
        state["activity_options"] = []
        result = _build_activities_by_day(state)
        assert result == {}

    def test_no_itinerary(self) -> None:
        state = _make_state(with_itinerary=False)
        result = _build_activities_by_day(state)
        assert result == {}

    def test_empty_days(self) -> None:
        state = _make_state(num_days=1, activities_per_day=0)
        result = _build_activities_by_day(state)
        assert result == {}


# ===================================================================
# _weather_icon
# ===================================================================


class TestWeatherIcon:
    def test_sunny(self) -> None:
        assert _weather_icon("sunny") == "\u2600"

    def test_rain(self) -> None:
        assert _weather_icon("rain") == "\u2614"

    def test_unknown(self) -> None:
        assert _weather_icon("blizzard") == ""

    def test_empty(self) -> None:
        assert _weather_icon("") == ""


# ===================================================================
# _stars_str
# ===================================================================


class TestStarsStr:
    def test_four_stars(self) -> None:
        assert _stars_str(4) == "\u2605\u2605\u2605\u2605"

    def test_zero_stars(self) -> None:
        assert _stars_str(0) == ""

    def test_five_stars(self) -> None:
        assert len(_stars_str(5)) == 5


# ===================================================================
# _make_confirmation_code
# ===================================================================


class TestMakeConfirmationCode:
    def test_deterministic(self) -> None:
        a = _make_confirmation_code("HTL", "htl-001")
        b = _make_confirmation_code("HTL", "htl-001")
        assert a == b

    def test_different_inputs_differ(self) -> None:
        a = _make_confirmation_code("HTL", "htl-001")
        b = _make_confirmation_code("HTL", "htl-002")
        assert a != b

    def test_prefix_included(self) -> None:
        code = _make_confirmation_code("ACT", "act-001")
        assert code.startswith("ACT-")
        assert len(code) == 12  # "ACT-" + 8 hex chars


# ===================================================================
# _build_cover_page
# ===================================================================


class TestBuildCoverPage:
    def test_contains_title_paragraph(self) -> None:
        styles = _build_styles()
        elements = _build_cover_page("Paris", {"start_date": "2025-07-01", "end_date": "2025-07-10"}, "plan_1", styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("Roteiro de Viagem" in t for t in texts)

    def test_contains_destination(self) -> None:
        styles = _build_styles()
        elements = _build_cover_page("Tokyo", {}, "", styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("Tokyo" in t for t in texts)

    def test_ends_with_page_break(self) -> None:
        styles = _build_styles()
        elements = _build_cover_page("Paris", {}, "", styles)
        assert isinstance(elements[-1], PageBreak)


# ===================================================================
# _build_summary_section
# ===================================================================


class TestBuildSummarySection:
    def test_contains_summary_table(self) -> None:
        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_summary_section("Paris", {"start_date": "2025-07-01", "end_date": "2025-07-10"}, {}, _make_hotel(), cb, [], styles)
        tables = [e for e in elements if isinstance(e, Table)]
        assert len(tables) >= 1

    def test_hotel_info_present(self) -> None:
        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_summary_section("Paris", {}, {}, _make_hotel(name="Grand Hotel"), cb, [], styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("Grand Hotel" in t for t in texts)

    def test_no_hotel(self) -> None:
        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_summary_section("Paris", {}, {}, None, cb, [], styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("Nao selecionada" in t for t in texts)

    def test_risk_flags_shown(self) -> None:
        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_summary_section("Paris", {}, {}, None, cb, ["risk: test flag"], styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("test flag" in t for t in texts)


# ===================================================================
# _build_itinerary_section
# ===================================================================


class TestBuildItinerarySection:
    def test_day_header_present(self) -> None:
        styles = _build_styles()
        day = _make_day(day_number=1, slots=[_make_slot()])
        acts = {1: [_make_activity()]}
        elements = _build_itinerary_section([day], acts, styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("Dia 1" in t for t in texts)

    def test_activity_table_present(self) -> None:
        styles = _build_styles()
        day = _make_day(day_number=1, slots=[_make_slot()])
        acts = {1: [_make_activity()]}
        elements = _build_itinerary_section([day], acts, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        assert len(tables) >= 1

    def test_weather_icon_in_header(self) -> None:
        styles = _build_styles()
        day = _make_day(day_number=1, weather_condition="rain")
        elements = _build_itinerary_section([day], {}, styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("\u2614" in t for t in texts)

    def test_empty_day(self) -> None:
        styles = _build_styles()
        day = _make_day(day_number=1)
        elements = _build_itinerary_section([day], {}, styles)
        paragraphs = [e for e in elements if isinstance(e, Paragraph)]
        texts = [p.text for p in paragraphs]
        assert any("Nenhuma atividade" in t for t in texts)

    def test_stock_placeholder_present(self) -> None:
        from reportlab.graphics.shapes import Drawing

        styles = _build_styles()
        day = _make_day(day_number=1, slots=[_make_slot()])
        acts = {1: [_make_activity()]}
        elements = _build_itinerary_section([day], acts, styles)
        drawings = [e for e in elements if isinstance(e, Drawing)]
        assert len(drawings) >= 1


# ===================================================================
# _build_budget_section
# ===================================================================


class TestBuildBudgetSection:
    def test_table_has_rows(self) -> None:
        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_budget_section(cb, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        assert len(tables) >= 1
        # Header + 3 items + total = 5 rows
        first_table = tables[0]
        assert len(first_table._cellvalues) == 5

    def test_total_row_present(self) -> None:
        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_budget_section(cb, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        last_row = tables[0]._cellvalues[-1]
        assert last_row[0] == "TOTAL"

    def test_variance_bar_present(self) -> None:
        from reportlab.graphics.shapes import Drawing

        styles = _build_styles()
        cb = _make_cost_breakdown()
        elements = _build_budget_section(cb, styles)
        drawings = [e for e in elements if isinstance(e, Drawing)]
        assert len(drawings) >= 1


# ===================================================================
# _build_vouchers_section
# ===================================================================


class TestBuildVouchersSection:
    def test_hotel_voucher_present(self) -> None:
        styles = _build_styles()
        hotel = _make_hotel()
        elements = _build_vouchers_section(hotel, {}, "plan_1", {}, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        assert len(tables) >= 1
        # First row should be hotel voucher header
        assert "HOSPEDAGEM" in str(tables[0]._cellvalues[0][0])

    def test_activity_voucher_for_bookable(self) -> None:
        styles = _build_styles()
        act = _make_activity(id="a1", requires_booking=True)
        elements = _build_vouchers_section(None, {1: [act]}, "plan_1", {}, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        assert len(tables) >= 1
        assert "ATIVIDADE" in str(tables[0]._cellvalues[0][0])

    def test_no_hotel_skips_hotel_voucher(self) -> None:
        styles = _build_styles()
        act = _make_activity(id="a1", requires_booking=False)
        elements = _build_vouchers_section(None, {1: [act]}, "plan_1", {}, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        # No hotel voucher and activity doesn't require booking
        assert len(tables) == 0

    def test_non_bookable_activities_skipped(self) -> None:
        styles = _build_styles()
        act = _make_activity(id="a1", requires_booking=False)
        elements = _build_vouchers_section(_make_hotel(), {1: [act]}, "plan_1", {}, styles)
        tables = [e for e in elements if isinstance(e, Table)]
        # Only hotel voucher
        assert len(tables) == 1


# ===================================================================
# _build_stock_placeholder
# ===================================================================


class TestBuildStockPlaceholder:
    def test_returns_drawing(self) -> None:
        from reportlab.graphics.shapes import Drawing

        d = _build_stock_placeholder("museum", 400, 100)
        assert isinstance(d, Drawing)

    def test_unknown_category(self) -> None:
        d = _build_stock_placeholder("unknown_cat", 400, 100)
        assert d is not None


# ===================================================================
# generate_itinerary_pdf
# ===================================================================


class TestGenerateItineraryPdf:
    def test_returns_absolute_path(self, tmp_path: Path) -> None:
        out = tmp_path / "test.pdf"
        result = generate_itinerary_pdf(
            destination="Paris",
            dates={"start_date": "2025-07-01", "end_date": "2025-07-10"},
            budget={"total": 5000.0, "currency": "EUR"},
            hotel=_make_hotel(),
            activities_by_day={1: [_make_activity()]},
            itinerary_days=[_make_day(day_number=1, slots=[_make_slot()])],
            cost_breakdown=_make_cost_breakdown(),
            risk_flags=[],
            plan_id="plan_1",
            output_path=str(out),
        )
        assert result.endswith("test.pdf")
        assert out.exists()

    def test_handles_empty_itinerary(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.pdf"
        result = generate_itinerary_pdf(
            destination="Paris",
            dates={},
            budget={},
            hotel=None,
            activities_by_day={},
            itinerary_days=[],
            cost_breakdown=_make_cost_breakdown(),
            risk_flags=[],
            plan_id="",
            output_path=str(out),
        )
        assert out.exists()
        assert result.endswith("empty.pdf")

    def test_pdf_file_not_empty(self, tmp_path: Path) -> None:
        out = tmp_path / "nonempty.pdf"
        generate_itinerary_pdf(
            destination="Paris",
            dates={"start_date": "2025-07-01", "end_date": "2025-07-10"},
            budget={"total": 5000.0, "currency": "EUR"},
            hotel=_make_hotel(),
            activities_by_day={},
            itinerary_days=[],
            cost_breakdown=_make_cost_breakdown(),
            risk_flags=[],
            plan_id="plan_1",
            output_path=str(out),
        )
        assert out.stat().st_size > 0


# ===================================================================
# generate_pdf_from_state
# ===================================================================


class TestGenerateFromState:
    def test_full_pipeline(self, tmp_path: Path) -> None:
        state = _make_state(num_days=2, activities_per_day=2)
        out = tmp_path / "full.pdf"
        result = generate_pdf_from_state(state, str(out))
        assert out.exists()
        assert result.endswith("full.pdf")

    def test_no_destination_returns_empty(self, tmp_path: Path) -> None:
        state = _make_state()
        state["destination"] = ""
        result = generate_pdf_from_state(state, str(tmp_path / "x.pdf"))
        assert result == ""

    def test_no_itinerary_still_generates(self, tmp_path: Path) -> None:
        state = _make_state(with_itinerary=False)
        out = tmp_path / "no_itin.pdf"
        result = generate_pdf_from_state(state, str(out))
        assert out.exists()
        assert result.endswith("no_itin.pdf")

    def test_preserves_plan_id(self, tmp_path: Path) -> None:
        state = _make_state(plan_id="plan_keep_me")
        out = tmp_path / "pid.pdf"
        result = generate_pdf_from_state(state, str(out))
        assert out.exists()


# ===================================================================
# Integration — real PDF generation
# ===================================================================


class TestPdfIntegration:
    def test_generates_valid_pdf(self, tmp_path: Path) -> None:
        """Full state produces a valid PDF file with %PDF header."""
        state = _make_state(num_days=3, activities_per_day=2)
        state["risk_flags"] = ["risk: Travel advisory YELLOW"]
        out = tmp_path / "integration.pdf"
        result = generate_pdf_from_state(state, str(out))
        assert out.exists()

        # Check PDF magic bytes
        with open(out, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_multi_day_pdf(self, tmp_path: Path) -> None:
        """Multi-day itinerary produces a multi-page PDF."""
        state = _make_state(num_days=5, activities_per_day=3)
        out = tmp_path / "multi.pdf"
        generate_pdf_from_state(state, str(out))
        # File size should be substantial for 5 days
        assert out.stat().st_size > 5000

    def test_with_flight(self, tmp_path: Path) -> None:
        """PDF with flight costs included."""
        state = _make_state(num_days=2, activities_per_day=1)
        state["selected_flight_id"] = "flt-001"
        state["flight_options"] = [
            {"id": "flt-001", "price": 450.0, "airline": "Air France"},
        ]
        out = tmp_path / "flight.pdf"
        result = generate_pdf_from_state(state, str(out))
        assert out.exists()
        assert result.endswith("flight.pdf")
