"""PDF itinerary generator using ReportLab.

Produces a styled A4 PDF document with:
- Cover page with destination and travel dates
- Executive summary (budget, hotel, risk flags)
- Day-by-day itinerary with activity tables and placeholders
- Budget breakdown with variance indicator
- Mock vouchers for hotel and bookable activities
"""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime
from typing import Any

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from typing_extensions import TypedDict

from travel_orchestrator.state.models import (
    Activity,
    HotelOption,
    ItineraryDay,
    TravelPlannerCore,
)
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_PRIMARY = colors.HexColor("#1a5490")
_ACCENT = colors.HexColor("#e8833a")
_LIGHT_BG = colors.HexColor("#f5f7fa")
_DARK_TEXT = colors.HexColor("#2c3e50")
_SUCCESS = colors.HexColor("#27ae60")
_DANGER = colors.HexColor("#c0392b")
_GREY = colors.HexColor("#95a5a6")

# ---------------------------------------------------------------------------
# Weather icons (Unicode symbols)
# ---------------------------------------------------------------------------

_WEATHER_ICONS: dict[str, str] = {
    "sunny": "\u2600",        # ☀
    "clear": "\u2600",
    "partly_cloudy": "\u26c5",  # ⛅
    "cloudy": "\u2601",       # ☁
    "rain": "\u2614",         # ☂
    "storm": "\u26a1",        # ⚡
    "snow": "\u2744",         # ❄
    "wind": "\U0001f4a8",     # 💨
    "fog": "\U0001f32b",      # 🌫
}

# Category colours for stock placeholders
_CATEGORY_COLORS: dict[str, colors.HexColor] = {
    "museum": colors.HexColor("#8e44ad"),
    "tour": colors.HexColor("#2980b9"),
    "park": colors.HexColor("#27ae60"),
    "food": colors.HexColor("#e67e22"),
    "beach": colors.HexColor("#16a085"),
    "adventure": colors.HexColor("#d35400"),
    "nightlife": colors.HexColor("#2c3e50"),
    "shopping": colors.HexColor("#e74c3c"),
}
_DEFAULT_CATEGORY_COLOR = colors.HexColor("#7f8c8d")


# ---------------------------------------------------------------------------
# Local TypedDict for cost breakdown
# ---------------------------------------------------------------------------


class CostBreakdown(TypedDict):
    """Itemised cost breakdown for the PDF budget section."""

    flight_cost: float
    hotel_cost: float
    activity_cost: float
    total_cost: float
    budget_total: float
    currency: str


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create the custom paragraph styles used throughout the PDF."""
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Heading1"],
            fontSize=28,
            textColor=_PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=6,
            leading=34,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base["Heading2"],
            fontSize=18,
            textColor=_ACCENT,
            alignment=TA_CENTER,
            spaceAfter=20,
            leading=22,
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Heading1"],
            fontSize=16,
            textColor=_PRIMARY,
            spaceAfter=12,
            spaceBefore=6,
        ),
        "day_title": ParagraphStyle(
            "day_title",
            parent=base["Heading2"],
            fontSize=14,
            textColor=_ACCENT,
            spaceAfter=8,
            spaceBefore=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=11,
            textColor=_DARK_TEXT,
            leading=14,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontSize=9,
            textColor=_GREY,
            leading=11,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_pdf_from_state(
    state: TravelPlannerCore,
    output_path: str,
) -> str:
    """Generate a styled PDF itinerary from the full planner state.

    Returns:
        Absolute path of the generated PDF, or ``""`` when the PDF
        cannot be generated (missing destination or itinerary).
    """
    destination = state.get("destination", "")
    if not destination:
        logger.warning("pdf_skipped_no_destination")
        return ""

    dates = state.get("dates", {})
    budget = state.get("budget", {})
    hotel = _resolve_hotel(state)
    itinerary = state.get("optimized_itinerary")
    itinerary_days: list[ItineraryDay] = []
    if itinerary:
        itinerary_days = itinerary.get("days", [])

    activities_by_day = _build_activities_by_day(state)
    cost_breakdown = _compute_cost_breakdown(state)
    risk_flags = list(state.get("risk_flags", []))
    plan_id = state.get("plan_id", "")

    return generate_itinerary_pdf(
        destination=destination,
        dates=dates,
        budget=budget,
        hotel=hotel,
        activities_by_day=activities_by_day,
        itinerary_days=itinerary_days,
        cost_breakdown=cost_breakdown,
        risk_flags=risk_flags,
        plan_id=plan_id,
        output_path=output_path,
    )


def generate_itinerary_pdf(
    destination: str,
    dates: dict[str, str],
    budget: dict[str, Any],
    hotel: HotelOption | None,
    activities_by_day: dict[int, list[Activity]],
    itinerary_days: list[ItineraryDay],
    cost_breakdown: CostBreakdown,
    risk_flags: list[str],
    plan_id: str,
    output_path: str,
) -> str:
    """Build and save the styled PDF itinerary.

    Returns:
        Absolute path to the generated PDF file.
    """
    styles = _build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: list[Any] = []
    story.extend(_build_cover_page(destination, dates, plan_id, styles))
    story.extend(
        _build_summary_section(destination, dates, budget, hotel, cost_breakdown, risk_flags, styles)
    )
    if itinerary_days:
        story.extend(_build_itinerary_section(itinerary_days, activities_by_day, styles))
    story.extend(_build_budget_section(cost_breakdown, styles))
    story.extend(_build_vouchers_section(hotel, activities_by_day, plan_id, dates, styles))

    doc.build(story)
    logger.info("pdf_generated", destination=destination, output_path=output_path)
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_cover_page(
    destination: str,
    dates: dict[str, str],
    plan_id: str,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the cover page elements."""
    elements: list[Any] = []
    elements.append(Spacer(1, 3 * inch))
    elements.append(Paragraph("Roteiro de Viagem", styles["cover_title"]))
    elements.append(Paragraph(destination, styles["cover_subtitle"]))
    elements.append(Spacer(1, 0.3 * inch))

    start = dates.get("start_date", "")
    end = dates.get("end_date", "")
    if start and end:
        elements.append(
            Paragraph(f"{start}  \u2192  {end}", styles["body"])
        )
        # Centre the date line
        elements[-1].style = ParagraphStyle(
            "cover_date", parent=styles["body"], alignment=TA_CENTER
        )

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(
        HRFlowable(width="60%", thickness=2, color=_ACCENT, spaceAfter=20)
    )

    if plan_id:
        elements.append(
            Paragraph(f"Plan ID: {plan_id}", styles["small"])
        )
        elements[-1].style = ParagraphStyle(
            "cover_planid", parent=styles["small"], alignment=TA_CENTER
        )

    elements.append(PageBreak())
    return elements


def _build_summary_section(
    destination: str,
    dates: dict[str, str],
    budget: dict[str, Any],
    hotel: HotelOption | None,
    cost_breakdown: CostBreakdown,
    risk_flags: list[str],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the executive summary section."""
    elements: list[Any] = []
    elements.append(Paragraph("Sumario Executivo", styles["section_title"]))
    elements.append(Spacer(1, 0.2 * inch))

    currency = cost_breakdown["currency"]
    nights = _compute_nights(dates)
    variance = round(cost_breakdown["total_cost"] - cost_breakdown["budget_total"], 2)
    variance_label = f"+{variance:.2f}" if variance > 0 else f"{variance:.2f}"

    summary_data = [
        ["Destino", destination],
        [
            "Periodo",
            f"{dates.get('start_date', '')} \u2192 {dates.get('end_date', '')}"
            f"  ({nights} noite{'s' if nights != 1 else ''})",
        ],
        ["Orcamento", f"{currency} {cost_breakdown['budget_total']:.2f}"],
        ["Custo Total", f"{currency} {cost_breakdown['total_cost']:.2f}"],
        ["Variacao", f"{currency} {variance_label}"],
    ]

    table = Table(summary_data, colWidths=[3.5 * cm, 13 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), _PRIMARY),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, _LIGHT_BG]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    # Hotel card
    if hotel:
        stars = _stars_str(hotel.get("stars", 0))
        hotel_text = (
            f"<b>{hotel.get('name', '')}</b> {stars}<br/>"
            f"{hotel.get('address', '')}<br/>"
            f"{hotel.get('currency', '')} {hotel.get('price_per_night', 0):.2f} / noite"
        )
        elements.append(Paragraph("Hospedagem", styles["day_title"]))
        elements.append(Paragraph(hotel_text, styles["body"]))
    else:
        elements.append(Paragraph("Hospedagem: Nao selecionada", styles["body"]))

    elements.append(Spacer(1, 0.2 * inch))

    # Risk flags
    if risk_flags:
        elements.append(Paragraph("Alertas", styles["day_title"]))
        for flag in risk_flags:
            elements.append(Paragraph(f"\u26a0 {flag}", styles["body"]))
        elements.append(Spacer(1, 0.1 * inch))

    elements.append(PageBreak())
    return elements


def _build_itinerary_section(
    itinerary_days: list[ItineraryDay],
    activities_by_day: dict[int, list[Activity]],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the day-by-day itinerary section."""
    elements: list[Any] = []
    elements.append(Paragraph("Itinerario Dia-a-Dia", styles["section_title"]))
    elements.append(Spacer(1, 0.15 * inch))

    for idx, day in enumerate(itinerary_days):
        day_number = day.get("day_number", idx + 1)
        date_str = day.get("date", "")
        theme = day.get("theme", "")
        weather = day.get("weather_condition", "")
        weather_sym = _weather_icon(weather)
        notes = day.get("notes", "")

        header = f"Dia {day_number} \u2014 {date_str}"
        if theme:
            header += f"  |  {theme}"
        if weather_sym:
            header += f"  {weather_sym}"
        elements.append(Paragraph(header, styles["day_title"]))

        day_activities = activities_by_day.get(day_number, [])
        slots = day.get("slots", [])

        if not day_activities and not slots:
            elements.append(Paragraph("Nenhuma atividade agendada.", styles["small"]))
        else:
            # Build activity table
            table_data: list[list[str]] = [
                ["Horario", "Atividade", "Categoria", "Duracao", "Preco"],
            ]

            slot_lookup: dict[str, dict[str, str]] = {}
            for slot in slots:
                slot_lookup[slot.get("activity_id", "")] = {
                    "start": slot.get("start_time", ""),
                    "end": slot.get("end_time", ""),
                }

            for act in day_activities:
                act_id = act.get("id", "")
                slot_info = slot_lookup.get(act_id, {})
                time_range = ""
                if slot_info.get("start") and slot_info.get("end"):
                    time_range = f"{slot_info['start']}\u2013{slot_info['end']}"

                duration = act.get("duration_minutes", 0)
                price = act.get("price", 0)
                currency = act.get("currency", "")
                indoor = "Interior" if act.get("indoor") else "Exterior"
                category = act.get("category", "")

                table_data.append([
                    time_range,
                    _truncate(act.get("name", ""), 30),
                    f"{category} ({indoor})",
                    f"{duration} min",
                    f"{currency} {price:.0f}",
                ])

            col_widths = [2.5 * cm, 5 * cm, 4 * cm, 2 * cm, 3 * cm]
            act_table = Table(table_data, colWidths=col_widths)
            act_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_BG]),
            ]))
            elements.append(act_table)

            # Stock photo placeholder for first activity
            if day_activities:
                first_cat = day_activities[0].get("category", "")
                elements.append(Spacer(1, 0.1 * inch))
                elements.append(_build_stock_placeholder(first_cat, 16 * cm, 3 * cm))

        if notes:
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(Paragraph(f"<i>{notes}</i>", styles["small"]))

        # Page break between days except after the last
        if idx < len(itinerary_days) - 1:
            elements.append(PageBreak())
        else:
            elements.append(Spacer(1, 0.3 * inch))

    elements.append(PageBreak())
    return elements


def _build_budget_section(
    cost_breakdown: CostBreakdown,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the budget breakdown section."""
    elements: list[Any] = []
    elements.append(Paragraph("Detalhamento de Custos", styles["section_title"]))
    elements.append(Spacer(1, 0.15 * inch))

    currency = cost_breakdown["currency"]
    table_data = [
        ["Item", "Valor"],
        ["Voos", f"{currency} {cost_breakdown['flight_cost']:.2f}"],
        ["Hospedagem", f"{currency} {cost_breakdown['hotel_cost']:.2f}"],
        ["Atividades", f"{currency} {cost_breakdown['activity_cost']:.2f}"],
        ["TOTAL", f"{currency} {cost_breakdown['total_cost']:.2f}"],
    ]

    table = Table(table_data, colWidths=[8 * cm, 8 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_BG]),
        # Bold total row
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _LIGHT_BG),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, _PRIMARY),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    # Variance bar
    budget_total = cost_breakdown["budget_total"]
    total_cost = cost_breakdown["total_cost"]
    if budget_total > 0:
        elements.append(_build_variance_bar(total_cost, budget_total))
        elements.append(Spacer(1, 0.1 * inch))

    elements.append(PageBreak())
    return elements


def _build_vouchers_section(
    hotel: HotelOption | None,
    activities_by_day: dict[int, list[Activity]],
    plan_id: str,
    dates: dict[str, str],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build the mock vouchers section."""
    elements: list[Any] = []
    elements.append(Paragraph("Vouchers", styles["section_title"]))
    elements.append(Spacer(1, 0.15 * inch))

    # Hotel voucher
    if hotel:
        conf_code = _make_confirmation_code("HTL", hotel.get("id", ""))
        hotel_data = [
            ["VOUCHER DE HOSPEDAGEM", ""],
            ["Hotel", hotel.get("name", "")],
            ["Endereco", hotel.get("address", "")],
            ["Check-in", dates.get("start_date", "")],
            ["Check-out", dates.get("end_date", "")],
            ["Confirmacao", conf_code],
        ]
        hotel_table = Table(hotel_data, colWidths=[4 * cm, 12 * cm])
        hotel_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("SPAN", (0, 0), (-1, 0)),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 1.5, _ACCENT),
            ("GRID", (0, 1), (-1, -1), 0.5, colors.lightgrey),
        ]))
        elements.append(hotel_table)
        elements.append(Spacer(1, 0.3 * inch))

    # Activity vouchers
    for day_number in sorted(activities_by_day.keys()):
        for act in activities_by_day[day_number]:
            if not act.get("requires_booking"):
                continue
            conf_code = _make_confirmation_code("ACT", act.get("id", ""))
            act_data = [
                ["VOUCHER DE ATIVIDADE", ""],
                ["Atividade", act.get("name", "")],
                ["Categoria", act.get("category", "")],
                ["Dia", str(day_number)],
                ["Confirmacao", conf_code],
            ]
            act_table = Table(act_data, colWidths=[4 * cm, 12 * cm])
            act_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("SPAN", (0, 0), (-1, 0)),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 1.5, _PRIMARY),
                ("GRID", (0, 1), (-1, -1), 0.5, colors.lightgrey),
            ]))
            elements.append(act_table)
            elements.append(Spacer(1, 0.2 * inch))

    return elements


# ---------------------------------------------------------------------------
# Private helpers — state extraction
# ---------------------------------------------------------------------------


def _resolve_hotel(state: TravelPlannerCore) -> HotelOption | None:
    """Find the selected hotel from ``hotel_options``."""
    selected_id = state.get("selected_hotel_id")
    if not selected_id:
        return None
    for hotel in state.get("hotel_options", []):
        if hotel.get("id") == selected_id:
            return hotel
    return None


def _build_activities_by_day(
    state: TravelPlannerCore,
) -> dict[int, list[Activity]]:
    """Map ``day_number`` → list of ``Activity`` dicts from the itinerary."""
    itinerary = state.get("optimized_itinerary")
    if itinerary is None:
        return {}

    activity_lookup: dict[str, Activity] = {
        a["id"]: a for a in state.get("activity_options", [])
    }

    result: dict[int, list[Activity]] = {}
    for day in itinerary.get("days", []):
        day_number = day.get("day_number", 0)
        day_activities: list[Activity] = []
        for slot in day.get("slots", []):
            act = activity_lookup.get(slot.get("activity_id", ""))
            if act is None:
                continue
            day_activities.append(act)
        if day_activities:
            result[day_number] = day_activities

    return result


def _compute_cost_breakdown(state: TravelPlannerCore) -> CostBreakdown:
    """Compute itemised cost breakdown from the state."""
    budget = state.get("budget", {})
    currency = str(budget.get("currency", "USD"))
    budget_total = float(budget.get("total", 0))

    # Flight cost
    flight_cost = 0.0
    selected_flight_id = state.get("selected_flight_id")
    if selected_flight_id:
        for flight in state.get("flight_options", []):
            if flight.get("id") == selected_flight_id:
                group_size = int(
                    state.get("traveler_profile", {}).get("group_size", 1)
                )
                flight_cost = float(flight.get("price", 0)) * group_size
                break

    # Hotel cost
    hotel_cost = 0.0
    hotel = _resolve_hotel(state)
    if hotel:
        nights = _compute_nights(state.get("dates", {}))
        hotel_cost = float(hotel.get("price_per_night", 0)) * nights

    # Activity cost
    activity_cost = 0.0
    selected_ids = set(state.get("selected_activity_ids", []))
    for act in state.get("activity_options", []):
        if act.get("id") in selected_ids:
            activity_cost += float(act.get("price", 0))

    total_cost = round(flight_cost + hotel_cost + activity_cost, 2)

    return CostBreakdown(
        flight_cost=round(flight_cost, 2),
        hotel_cost=round(hotel_cost, 2),
        activity_cost=round(activity_cost, 2),
        total_cost=total_cost,
        budget_total=budget_total,
        currency=currency,
    )


# ---------------------------------------------------------------------------
# Private helpers — formatting
# ---------------------------------------------------------------------------


def _compute_nights(dates: dict[str, str]) -> int:
    """Compute the number of nights from ISO 8601 start/end dates."""
    start_raw = dates.get("start_date", "")
    end_raw = dates.get("end_date", "")
    if not start_raw or not end_raw:
        return 0
    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
        return max((end - start).days, 1)
    except (ValueError, TypeError):
        return 0


def _weather_icon(condition: str) -> str:
    """Return a Unicode weather symbol for the given condition string."""
    if not condition:
        return ""
    return _WEATHER_ICONS.get(condition.lower().strip(), "")


def _stars_str(n: int) -> str:
    """Return a Unicode star string for *n* stars."""
    return "\u2605" * n


def _make_confirmation_code(prefix: str, item_id: str) -> str:
    """Generate a deterministic mock confirmation code."""
    digest = hashlib.sha256(f"{prefix}:{item_id}".encode()).hexdigest()[:8].upper()
    return f"{prefix}-{digest}"


def _truncate(text: str, max_len: int) -> str:
    """Truncate *text* to *max_len* characters with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


def _build_stock_placeholder(
    category: str,
    width: float,
    height: float,
) -> Drawing:
    """Create a coloured rectangle placeholder representing a stock photo."""
    color = _CATEGORY_COLORS.get(category.lower(), _DEFAULT_CATEGORY_COLOR)
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=color, strokeColor=None))
    label = f"[ {category.upper()} ]" if category else "[ PHOTO ]"
    d.add(String(
        width / 2,
        height / 2 - 5,
        label,
        fontSize=14,
        fillColor=colors.white,
        textAnchor="middle",
    ))
    return d


def _build_variance_bar(
    total_cost: float,
    budget_total: float,
) -> Drawing:
    """Create a horizontal bar showing cost vs budget."""
    bar_width = 16 * cm
    bar_height = 1.2 * cm
    d = Drawing(bar_width, bar_height)

    # Background bar (budget)
    d.add(Rect(0, 4, bar_width, 20, fillColor=_LIGHT_BG, strokeColor=_GREY, strokeWidth=0.5))

    # Filled bar (cost)
    ratio = min(total_cost / budget_total, 1.5) if budget_total > 0 else 0
    fill_width = min(ratio * bar_width, bar_width)
    fill_color = _SUCCESS if total_cost <= budget_total else _DANGER
    d.add(Rect(0, 4, fill_width, 20, fillColor=fill_color, strokeColor=None))

    # Labels
    pct = ratio * 100
    d.add(String(
        4, 10, f"{pct:.0f}% do orcamento", fontSize=9, fillColor=_DARK_TEXT
    ))

    return d
