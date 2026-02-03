"""Interactive map generation using Folium.

Produces a self-contained HTML file with:
- Hotel marker (red, home icon)
- Activity markers colour-coded by day
- Straight-line routes per day (hotel → activities → hotel)
- FeatureGroups with LayerControl for toggling days on/off
- Rich popups with detailed information
"""

from __future__ import annotations

import os
from typing import Any

import folium

from travel_orchestrator.state.models import Activity, HotelOption, TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Named colours assigned to day markers; cycle via modulo for 10+ day trips.
MAP_DAY_COLORS: list[str] = [
    "blue",
    "green",
    "purple",
    "orange",
    "darkblue",
    "darkgreen",
    "cadetblue",
    "darkpurple",
    "pink",
    "lightred",
]

# Hex equivalents for PolyLine (folium PolyLine uses hex strings).
_POLYLINE_COLORS: list[str] = [
    "#3186cc",  # blue
    "#2ca02c",  # green
    "#9467bd",  # purple
    "#ff7f0e",  # orange
    "#17375e",  # darkblue
    "#006400",  # darkgreen
    "#5f9ea0",  # cadetblue
    "#5b2c6f",  # darkpurple
    "#e91e63",  # pink
    "#cd5c5c",  # lightred
]

HOTEL_MARKER_COLOR: str = "red"
HOTEL_MARKER_ICON: str = "home"
HOTEL_MARKER_PREFIX: str = "glyphicon"

ACTIVITY_MARKER_ICON: str = "info-sign"
ACTIVITY_MARKER_PREFIX: str = "glyphicon"

DEFAULT_MAP_ZOOM: int = 13
DEFAULT_TILE_PROVIDER: str = "OpenStreetMap"

ROUTE_WEIGHT: int = 3
ROUTE_OPACITY: float = 0.7
ROUTE_DASH_ARRAY: str = "5 10"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_map_from_state(
    state: TravelPlannerCore,
    output_path: str,
) -> str:
    """Generate an interactive map from the full planner state.

    Extracts the selected hotel and resolves scheduled activities by day
    from the optimised itinerary, then delegates to
    :func:`generate_interactive_map`.

    Returns:
        Absolute path of the generated HTML file, or ``""`` when the
        map cannot be generated (no hotel, no itinerary, etc.).
    """
    hotel = _resolve_hotel_from_state(state)
    if hotel is None:
        logger.warning("map_skipped_no_hotel")
        return ""

    if not _has_valid_coordinates(hotel):
        logger.warning("map_skipped_hotel_missing_coordinates")
        return ""

    itinerary = state.get("optimized_itinerary")
    if itinerary is None:
        logger.warning("map_skipped_no_itinerary")
        return ""

    activities_by_day = _build_activities_by_day(state)
    destination = state.get("destination", "Travel Map")

    return generate_interactive_map(
        hotel=hotel,
        activities_by_day=activities_by_day,
        destination=destination,
        output_path=output_path,
    )


def generate_interactive_map(
    hotel: HotelOption,
    activities_by_day: dict[int, list[Activity]],
    destination: str,
    output_path: str,
) -> str:
    """Generate an interactive HTML map with hotel, activities and routes.

    Args:
        hotel: The selected hotel (must have valid coordinates).
        activities_by_day: ``{day_number: [activities]}``.  Activities
            without valid coordinates are silently skipped.
        destination: Destination name used for the map title.
        output_path: File path for the output HTML file.

    Returns:
        Absolute path to the generated HTML file.
    """
    center_lat = hotel["coordinates"]["lat"]
    center_lng = hotel["coordinates"]["lng"]

    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=DEFAULT_MAP_ZOOM,
        tiles=DEFAULT_TILE_PROVIDER,
    )

    # -- Hotel layer --------------------------------------------------------
    hotel_group = folium.FeatureGroup(name="Hotel")
    _add_hotel_marker(hotel_group, hotel)
    hotel_group.add_to(m)

    # -- Day layers ---------------------------------------------------------
    for day_number in sorted(activities_by_day.keys()):
        activities = activities_by_day[day_number]
        color_idx = (day_number - 1) % len(MAP_DAY_COLORS)
        marker_color = MAP_DAY_COLORS[color_idx]
        line_color = _POLYLINE_COLORS[color_idx]

        day_group = folium.FeatureGroup(name=f"Day {day_number}")

        activity_coords = _add_activity_markers(
            day_group, activities, marker_color, day_number
        )

        route_points = _build_day_route_points(hotel, activity_coords)
        add_route_layer(day_group, route_points, line_color)

        day_group.add_to(m)

    # -- Controls -----------------------------------------------------------
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(output_path)
    logger.info(
        "map_generated",
        destination=destination,
        output_path=output_path,
        day_count=len(activities_by_day),
    )
    return os.path.abspath(output_path)


def add_route_layer(
    feature_group: folium.FeatureGroup,
    points: list[tuple[float, float]],
    color: str,
    *,
    weight: int = ROUTE_WEIGHT,
    opacity: float = ROUTE_OPACITY,
    dash_array: str | None = ROUTE_DASH_ARRAY,
) -> None:
    """Add a PolyLine route to a FeatureGroup.

    Silently skips when fewer than 2 points are provided.
    """
    if len(points) < 2:
        return

    folium.PolyLine(
        locations=points,
        color=color,
        weight=weight,
        opacity=opacity,
        dash_array=dash_array,
    ).add_to(feature_group)


# ---------------------------------------------------------------------------
# Private helpers — state extraction
# ---------------------------------------------------------------------------


def _resolve_hotel_from_state(state: TravelPlannerCore) -> HotelOption | None:
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
    """Map ``day_number`` → list of ``Activity`` dicts from the itinerary.

    Resolves ``activity_id`` in each :class:`ItinerarySlot` against
    ``activity_options``, preserving slot order within each day.
    """
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
                logger.warning(
                    "map_activity_not_found",
                    activity_id=slot.get("activity_id"),
                    day_number=day_number,
                )
                continue
            day_activities.append(act)
        if day_activities:
            result[day_number] = day_activities

    return result


# ---------------------------------------------------------------------------
# Private helpers — markers
# ---------------------------------------------------------------------------


def _add_hotel_marker(
    feature_group: folium.FeatureGroup,
    hotel: HotelOption,
) -> None:
    """Add the hotel marker with a detailed popup."""
    if not _has_valid_coordinates(hotel):
        return

    lat = hotel["coordinates"]["lat"]
    lng = hotel["coordinates"]["lng"]

    stars_str = "\u2605" * hotel.get("stars", 0)
    price = hotel.get("price_per_night", 0)
    currency = hotel.get("currency", "")

    popup_html = _build_popup_html(
        title=hotel.get("name", "Hotel"),
        rows=[
            ("Address", hotel.get("address", "")),
            ("Stars", stars_str or "N/A"),
            ("Price/night", f"{price:.0f} {currency}"),
            ("Amenities", ", ".join(hotel.get("amenities", []))),
        ],
    )

    folium.Marker(
        location=[lat, lng],
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=hotel.get("name", "Hotel"),
        icon=folium.Icon(
            color=HOTEL_MARKER_COLOR,
            icon=HOTEL_MARKER_ICON,
            prefix=HOTEL_MARKER_PREFIX,
        ),
    ).add_to(feature_group)


def _add_activity_markers(
    feature_group: folium.FeatureGroup,
    activities: list[Activity],
    color: str,
    day_number: int,
) -> list[tuple[float, float]]:
    """Add activity markers for a day, returning valid coordinate tuples.

    The returned list is used to build the day's route.
    """
    coords: list[tuple[float, float]] = []

    for idx, activity in enumerate(activities, 1):
        if not _has_valid_coordinates(activity):
            logger.warning(
                "map_activity_missing_coordinates",
                activity_id=activity.get("id"),
                day_number=day_number,
            )
            continue

        lat = activity["coordinates"]["lat"]
        lng = activity["coordinates"]["lng"]
        coords.append((lat, lng))

        indoor_label = "Indoor" if activity.get("indoor") else "Outdoor"
        price = activity.get("price", 0)
        currency = activity.get("currency", "")
        duration = activity.get("duration_minutes", 0)

        popup_html = _build_popup_html(
            title=f"Day {day_number} #{idx}: {activity.get('name', '')}",
            rows=[
                ("Category", activity.get("category", "")),
                ("Duration", f"{duration} min"),
                ("Price", f"{price:.0f} {currency}"),
                ("Type", indoor_label),
                ("Description", _truncate(activity.get("description", ""), 100)),
            ],
        )

        folium.Marker(
            location=[lat, lng],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"Day {day_number} #{idx}: {activity.get('name', '')}",
            icon=folium.Icon(
                color=color,
                icon=ACTIVITY_MARKER_ICON,
                prefix=ACTIVITY_MARKER_PREFIX,
            ),
        ).add_to(feature_group)

    return coords


# ---------------------------------------------------------------------------
# Private helpers — geometry & formatting
# ---------------------------------------------------------------------------


def _has_valid_coordinates(item: dict[str, Any]) -> bool:
    """Return ``True`` if *item* has a ``coordinates`` dict with numeric lat/lng."""
    coords = item.get("coordinates")
    if not isinstance(coords, dict):
        return False
    lat = coords.get("lat")
    lng = coords.get("lng")
    return isinstance(lat, (int, float)) and isinstance(lng, (int, float))


def _build_day_route_points(
    hotel: HotelOption,
    activity_coords: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Build route: hotel → activities in order → hotel.

    Returns an empty list when there are no activity coordinates.
    """
    if not activity_coords:
        return []

    hotel_point = (hotel["coordinates"]["lat"], hotel["coordinates"]["lng"])
    return [hotel_point, *activity_coords, hotel_point]


def _build_popup_html(title: str, rows: list[tuple[str, str]]) -> str:
    """Build a simple HTML popup with a title and key-value rows."""
    lines = [
        '<div style="font-family:sans-serif;font-size:12px;max-width:250px;">',
        f"<b>{title}</b>",
    ]
    if rows:
        lines.append("<table style='margin-top:4px;border-collapse:collapse;'>")
        for label, value in rows:
            if value:
                lines.append(
                    f"<tr><td style='padding:1px 6px 1px 0;color:#666;'>"
                    f"{label}</td><td>{value}</td></tr>"
                )
        lines.append("</table>")
    lines.append("</div>")
    return "\n".join(lines)


def _truncate(text: str, max_len: int) -> str:
    """Truncate *text* to *max_len* characters, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"
