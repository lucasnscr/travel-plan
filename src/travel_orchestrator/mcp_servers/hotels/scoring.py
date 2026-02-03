"""Hotel scoring and normalisation.

score = 0.30 * price_score
     + 0.25 * location_score
     + 0.25 * reviews_score
     + 0.20 * amenities_score

All sub-scores are normalised to [0, 1].
"""

from __future__ import annotations

from travel_orchestrator.mcp_servers.hotels.models import HotelResult


def _normalise_minmax(value: float, lo: float, hi: float, *, invert: bool = False) -> float:
    """Map *value* into [0, 1] given observed [lo, hi].

    When *invert* is True lower raw values produce higher scores
    (e.g. price, distance).
    """
    if hi <= lo:
        return 1.0
    clamped = max(lo, min(value, hi))
    norm = (clamped - lo) / (hi - lo)
    return 1.0 - norm if invert else norm


def compute_scores(
    hotels: list[HotelResult],
    *,
    desired_amenities: list[str] | None = None,
    weight_price: float = 0.30,
    weight_location: float = 0.25,
    weight_reviews: float = 0.25,
    weight_amenities: float = 0.20,
) -> list[HotelResult]:
    """Compute and assign ``score`` for each hotel, return sorted desc."""
    if not hotels:
        return hotels

    desired = {a.lower() for a in (desired_amenities or [])}

    # Collect ranges for normalisation
    prices = [h.price_total for h in hotels if h.price_total is not None]
    distances = [h.distance_to_center_km for h in hotels if h.distance_to_center_km is not None]
    reviews = [h.review_score for h in hotels if h.review_score is not None]

    price_lo = min(prices) if prices else 0.0
    price_hi = max(prices) if prices else 1.0
    dist_lo = min(distances) if distances else 0.0
    dist_hi = max(distances) if distances else 1.0
    review_lo = min(reviews) if reviews else 0.0
    review_hi = max(reviews) if reviews else 10.0

    for hotel in hotels:
        # Price: cheaper → higher score
        price_score = (
            _normalise_minmax(hotel.price_total, price_lo, price_hi, invert=True)
            if hotel.price_total is not None
            else 0.5
        )

        # Location: closer to centre → higher score
        location_score = (
            _normalise_minmax(hotel.distance_to_center_km, dist_lo, dist_hi, invert=True)
            if hotel.distance_to_center_km is not None
            else 0.5
        )

        # Reviews: higher review → higher score
        review_score = (
            _normalise_minmax(hotel.review_score, review_lo, review_hi)
            if hotel.review_score is not None
            else 0.5
        )

        # Amenities: proportion of desired amenities present
        if desired:
            present = {a.lower() for a in hotel.amenities}
            amenities_score = len(desired & present) / len(desired)
        else:
            amenities_score = min(len(hotel.amenities) / 5.0, 1.0)

        hotel.score = round(
            weight_price * price_score
            + weight_location * location_score
            + weight_reviews * review_score
            + weight_amenities * amenities_score,
            4,
        )

    hotels.sort(key=lambda h: h.score, reverse=True)
    return hotels
