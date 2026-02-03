"""Deterministic mock provider for hotel search.

Generates realistic hotel data for popular destinations using seeded RNG.
Same inputs always produce the same outputs.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

# ---------------------------------------------------------------------------
# Hotel database per city (curated for realism)
# ---------------------------------------------------------------------------

_RawHotel = dict[str, Any]


def _h(
    *,
    name: str,
    stars: int,
    review: float,
    nightly: float,
    currency: str,
    lat: float,
    lng: float,
    area: str,
    distance_km: float,
    amenities: list[str],
) -> _RawHotel:
    """Shorthand to build a raw hotel entry."""
    return {
        "name": name,
        "stars": stars,
        "review_score": review,
        "nightly_price": nightly,
        "currency": currency,
        "lat": lat,
        "lng": lng,
        "area": area,
        "distance_to_center_km": distance_km,
        "amenities": amenities,
    }


_HOTELS_DB: dict[str, list[_RawHotel]] = {
    "paris": [
        _h(name="Hôtel Le Marais Boutique", stars=4, review=8.9, nightly=185, currency="EUR", lat=48.8566, lng=2.3522, area="Le Marais", distance_km=0.5, amenities=["wifi", "breakfast", "air_conditioning", "bar"]),
        _h(name="Pullman Tour Eiffel", stars=5, review=9.1, nightly=320, currency="EUR", lat=48.8555, lng=2.2920, area="7e Arrondissement", distance_km=1.2, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service"]),
        _h(name="Ibis Bastille Opéra", stars=3, review=7.5, nightly=95, currency="EUR", lat=48.8530, lng=2.3700, area="Bastille", distance_km=1.5, amenities=["wifi", "breakfast", "air_conditioning"]),
        _h(name="Hôtel des Arts Montmartre", stars=3, review=8.2, nightly=110, currency="EUR", lat=48.8867, lng=2.3431, area="Montmartre", distance_km=2.8, amenities=["wifi", "breakfast"]),
        _h(name="Le Cinq Codet", stars=5, review=9.4, nightly=450, currency="EUR", lat=48.8570, lng=2.3120, area="Invalides", distance_km=0.9, amenities=["wifi", "spa", "gym", "restaurant", "bar", "room_service", "concierge"]),
        _h(name="Novotel Les Halles", stars=4, review=8.1, nightly=165, currency="EUR", lat=48.8620, lng=2.3470, area="Les Halles", distance_km=0.3, amenities=["wifi", "gym", "bar", "breakfast"]),
        _h(name="Generator Paris", stars=2, review=7.8, nightly=55, currency="EUR", lat=48.8810, lng=2.3670, area="10e Arrondissement", distance_km=2.5, amenities=["wifi", "bar"]),
        _h(name="Hôtel Monge", stars=4, review=9.0, nightly=210, currency="EUR", lat=48.8450, lng=2.3510, area="Latin Quarter", distance_km=0.8, amenities=["wifi", "breakfast", "spa", "air_conditioning"]),
    ],
    "tokyo": [
        _h(name="Park Hyatt Tokyo", stars=5, review=9.3, nightly=450, currency="JPY", lat=35.6855, lng=139.6922, area="Shinjuku", distance_km=3.5, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service"]),
        _h(name="Shinjuku Granbell Hotel", stars=4, review=8.5, nightly=150, currency="JPY", lat=35.6920, lng=139.7030, area="Shinjuku", distance_km=3.0, amenities=["wifi", "restaurant", "bar", "air_conditioning"]),
        _h(name="Hotel Gracery Shinjuku", stars=4, review=8.7, nightly=130, currency="JPY", lat=35.6940, lng=139.7010, area="Kabukicho", distance_km=3.2, amenities=["wifi", "restaurant", "air_conditioning"]),
        _h(name="MUJI Hotel Ginza", stars=4, review=8.8, nightly=200, currency="JPY", lat=35.6710, lng=139.7650, area="Ginza", distance_km=0.8, amenities=["wifi", "restaurant", "breakfast"]),
        _h(name="Sakura Hotel Ikebukuro", stars=2, review=7.2, nightly=45, currency="JPY", lat=35.7300, lng=139.7130, area="Ikebukuro", distance_km=5.0, amenities=["wifi", "breakfast"]),
        _h(name="Aman Tokyo", stars=5, review=9.5, nightly=600, currency="JPY", lat=35.6867, lng=139.7640, area="Otemachi", distance_km=0.5, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service", "concierge"]),
        _h(name="Dormy Inn Asakusa", stars=3, review=8.3, nightly=85, currency="JPY", lat=35.7110, lng=139.7960, area="Asakusa", distance_km=4.2, amenities=["wifi", "breakfast", "spa"]),
    ],
    "rio de janeiro": [
        _h(name="Copacabana Palace", stars=5, review=9.2, nightly=500, currency="BRL", lat=-22.9660, lng=-43.1780, area="Copacabana", distance_km=4.5, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service", "beach_access"]),
        _h(name="Hotel Fasano Rio", stars=5, review=9.0, nightly=420, currency="BRL", lat=-22.9870, lng=-43.2020, area="Ipanema", distance_km=6.0, amenities=["wifi", "pool", "spa", "restaurant", "bar", "room_service"]),
        _h(name="Windsor Atlantica", stars=4, review=8.4, nightly=180, currency="BRL", lat=-22.9700, lng=-43.1830, area="Copacabana", distance_km=4.3, amenities=["wifi", "pool", "gym", "restaurant", "breakfast"]),
        _h(name="Ibis Copacabana", stars=3, review=7.6, nightly=90, currency="BRL", lat=-22.9680, lng=-43.1850, area="Copacabana", distance_km=4.4, amenities=["wifi", "breakfast", "air_conditioning"]),
        _h(name="Hotel Santa Teresa", stars=4, review=8.8, nightly=250, currency="BRL", lat=-22.9220, lng=-43.1810, area="Santa Teresa", distance_km=1.5, amenities=["wifi", "pool", "bar", "restaurant"]),
        _h(name="Selina Lapa", stars=2, review=7.4, nightly=60, currency="BRL", lat=-22.9130, lng=-43.1800, area="Lapa", distance_km=1.0, amenities=["wifi", "bar"]),
    ],
    "london": [
        _h(name="The Savoy", stars=5, review=9.3, nightly=550, currency="GBP", lat=51.5100, lng=-0.1200, area="Strand", distance_km=0.4, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service", "concierge"]),
        _h(name="Premier Inn London City", stars=3, review=7.8, nightly=95, currency="GBP", lat=51.5130, lng=-0.0890, area="Tower Hill", distance_km=1.8, amenities=["wifi", "breakfast", "air_conditioning"]),
        _h(name="The Hoxton Shoreditch", stars=4, review=8.6, nightly=175, currency="GBP", lat=51.5250, lng=-0.0810, area="Shoreditch", distance_km=2.5, amenities=["wifi", "restaurant", "bar", "gym"]),
        _h(name="citizenM Tower of London", stars=4, review=8.8, nightly=160, currency="GBP", lat=51.5085, lng=-0.0770, area="Tower Hill", distance_km=1.9, amenities=["wifi", "bar", "air_conditioning"]),
        _h(name="Generator London", stars=2, review=7.3, nightly=45, currency="GBP", lat=51.5280, lng=-0.1100, area="Kings Cross", distance_km=2.3, amenities=["wifi", "bar"]),
        _h(name="Claridge's", stars=5, review=9.5, nightly=680, currency="GBP", lat=51.5128, lng=-0.1480, area="Mayfair", distance_km=0.6, amenities=["wifi", "spa", "gym", "restaurant", "bar", "room_service", "concierge"]),
        _h(name="Hub by Premier Inn Westminster", stars=3, review=8.0, nightly=85, currency="GBP", lat=51.4990, lng=-0.1350, area="Westminster", distance_km=0.8, amenities=["wifi", "air_conditioning"]),
    ],
    "lisbon": [
        _h(name="Pestana Palace", stars=5, review=9.2, nightly=300, currency="EUR", lat=38.7000, lng=-9.1800, area="Alcântara", distance_km=3.0, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service"]),
        _h(name="Hotel Avenida Palace", stars=4, review=8.7, nightly=165, currency="EUR", lat=38.7150, lng=-9.1420, area="Baixa", distance_km=0.2, amenities=["wifi", "restaurant", "bar", "breakfast"]),
        _h(name="Lisboa Pessoa Hotel", stars=4, review=8.9, nightly=140, currency="EUR", lat=38.7130, lng=-9.1450, area="Chiado", distance_km=0.5, amenities=["wifi", "bar", "breakfast", "air_conditioning"]),
        _h(name="Ibis Lisboa Liberdade", stars=3, review=7.5, nightly=70, currency="EUR", lat=38.7200, lng=-9.1460, area="Avenida da Liberdade", distance_km=0.8, amenities=["wifi", "breakfast"]),
        _h(name="The Lumiares", stars=5, review=9.4, nightly=280, currency="EUR", lat=38.7140, lng=-9.1440, area="Bairro Alto", distance_km=0.4, amenities=["wifi", "pool", "spa", "restaurant", "bar", "room_service"]),
        _h(name="Home Lisbon Hostel", stars=2, review=8.5, nightly=35, currency="EUR", lat=38.7160, lng=-9.1400, area="Baixa", distance_km=0.3, amenities=["wifi", "breakfast"]),
    ],
    "são paulo": [
        _h(name="Hotel Unique", stars=5, review=9.0, nightly=380, currency="BRL", lat=-23.5730, lng=-46.6750, area="Jardins", distance_km=2.0, amenities=["wifi", "pool", "spa", "gym", "restaurant", "bar", "room_service"]),
        _h(name="Renaissance São Paulo", stars=5, review=8.8, nightly=300, currency="BRL", lat=-23.5660, lng=-46.6520, area="Jardins", distance_km=1.5, amenities=["wifi", "pool", "gym", "restaurant", "bar"]),
        _h(name="Ibis Paulista", stars=3, review=7.6, nightly=80, currency="BRL", lat=-23.5620, lng=-46.6560, area="Paulista", distance_km=1.0, amenities=["wifi", "breakfast", "air_conditioning"]),
        _h(name="Blue Tree Premium Faria Lima", stars=4, review=8.3, nightly=160, currency="BRL", lat=-23.5680, lng=-46.6870, area="Itaim Bibi", distance_km=3.5, amenities=["wifi", "pool", "gym", "restaurant"]),
        _h(name="WZ Hotel Jardins", stars=4, review=8.5, nightly=140, currency="BRL", lat=-23.5640, lng=-46.6660, area="Jardins", distance_km=1.8, amenities=["wifi", "pool", "gym", "breakfast"]),
        _h(name="São Paulo Hostel", stars=2, review=7.2, nightly=40, currency="BRL", lat=-23.5500, lng=-46.6340, area="Vila Buarque", distance_km=0.8, amenities=["wifi"]),
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _seed_for(destination: str, check_in: str, check_out: str) -> int:
    raw = f"{destination.lower().strip()}:{check_in}:{check_out}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def generate_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
) -> list[dict[str, Any]]:
    """Return mock hotel raw dicts for *destination*.

    Deterministic: same inputs always produce the same output.
    Format matches what ``normalise_raw`` in server.py expects.
    """
    import datetime

    key = destination.lower().strip()
    pool = _HOTELS_DB.get(key)

    if pool is None:
        # Unknown city: generate a small synthetic set
        pool = _generate_synthetic(key)

    nights = (
        datetime.date.fromisoformat(check_out)
        - datetime.date.fromisoformat(check_in)
    ).days
    if nights <= 0:
        nights = 1

    rng = random.Random(_seed_for(destination, check_in, check_out))

    results: list[dict[str, Any]] = []
    for hotel in pool:
        # Add small price jitter for realism (±10%)
        jitter = rng.uniform(0.90, 1.10)
        nightly = round(hotel["nightly_price"] * jitter, 2)
        total = round(nightly * nights, 2)

        results.append({
            "name": hotel["name"],
            "stars": hotel["stars"],
            "review_score": hotel["review_score"],
            "price_total": total,
            "currency": hotel["currency"],
            "nightly_price_avg": nightly,
            "latitude": hotel["lat"],
            "longitude": hotel["lng"],
            "area": hotel["area"],
            "distance_to_center_km": hotel["distance_to_center_km"],
            "amenities": list(hotel["amenities"]),
            "deep_link": None,
        })

    return results


def _generate_synthetic(city: str) -> list[_RawHotel]:
    """Generate a small set of generic hotels for unknown cities."""
    rng = random.Random(int(hashlib.sha256(city.encode()).hexdigest()[:8], 16))
    names = [
        f"Hotel Central {city.title()}",
        f"Grand {city.title()} Palace",
        f"{city.title()} Budget Inn",
        f"Boutique {city.title()}",
        f"{city.title()} Luxury Suites",
    ]
    hotels: list[_RawHotel] = []
    for i, name in enumerate(names):
        stars = [3, 5, 2, 4, 5][i]
        hotels.append(
            _h(
                name=name,
                stars=stars,
                review=round(rng.uniform(6.5, 9.5), 1),
                nightly=round(rng.uniform(40, 400), 0),
                currency="EUR",
                lat=round(rng.uniform(-40, 60), 4),
                lng=round(rng.uniform(-120, 140), 4),
                area="City Centre",
                distance_km=round(rng.uniform(0.2, 5.0), 1),
                amenities=["wifi", "breakfast"],
            )
        )
    return hotels
