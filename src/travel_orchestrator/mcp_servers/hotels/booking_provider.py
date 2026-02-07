"""Booking.com API provider via RapidAPI.

Provides real hotel search, details, and facility data using the
Booking.com API through RapidAPI. Falls back gracefully when no
API key is configured.

Reference: https://rapidapi.com/DataCrawler/api/booking-com15
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any

import httpx

from travel_orchestrator.mcp_servers.hotels.retry import RetryableError, with_retry
from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://booking-com15.p.rapidapi.com/api/v1"
_DEFAULT_TIMEOUT = 15.0
_CACHE_TTL = 3600  # 1 hour
_MAX_RPS = 5  # max requests per second


def _get_rapidapi_key() -> str | None:
    """Return the RapidAPI key from environment, or None."""
    return os.environ.get("RAPIDAPI_KEY")


# ---------------------------------------------------------------------------
# Rate limiter (token bucket)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple asyncio-based rate limiter using a semaphore."""

    def __init__(self, max_rps: int = _MAX_RPS) -> None:
        self._semaphore = asyncio.Semaphore(max_rps)
        self._max_rps = max_rps

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        # Release after 1 second so we maintain max_rps
        asyncio.get_event_loop().call_later(1.0, self._semaphore.release)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class BookingProvider:
    """Async client for the Booking.com RapidAPI."""

    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        cache: TTLCache | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._cache = cache or TTLCache(default_ttl_seconds=_CACHE_TTL)
        self._api_key = api_key or _get_rapidapi_key()
        self._rate_limiter = _RateLimiter(_MAX_RPS)

    @property
    def is_configured(self) -> bool:
        """True if a RapidAPI key is available."""
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "X-RapidAPI-Key": self._api_key or "",
            "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
        }

    async def _request(
        self, endpoint: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Make a rate-limited, retried GET request to the API."""
        if not self._api_key:
            raise RuntimeError("RAPIDAPI_KEY not configured")

        await self._rate_limiter.acquire()

        async def _do_request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/{endpoint}",
                    headers=self._headers(),
                    params=params,
                )
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "2"))
                    raise RetryableError(
                        "Rate limited",
                        status_code=429,
                        retry_after=retry_after,
                    )
                if resp.status_code >= 500:
                    raise RetryableError(
                        f"Server error {resp.status_code}",
                        status_code=resp.status_code,
                    )
                resp.raise_for_status()
                return resp.json()

        return await with_retry(
            _do_request, operation=f"booking_{endpoint}",
        )

    # ------------------------------------------------------------------
    # Destination ID lookup (required by Booking.com API)
    # ------------------------------------------------------------------

    async def _get_dest_id(self, destination: str) -> tuple[str, str]:
        """Resolve a city name to (dest_id, dest_type) via search API.

        Returns the first matching city result.
        """
        cache_key = TTLCache.make_key("booking_dest", destination.lower().strip())
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._request(
            "hotels/searchDestination",
            {"query": destination},
        )

        results = data.get("data", [])
        if not results:
            raise ValueError(f"No Booking.com destination found for: {destination!r}")

        # Prefer city type
        for r in results:
            if r.get("dest_type") == "city":
                pair = (str(r["dest_id"]), "city")
                self._cache.set(cache_key, pair, ttl=86400)
                return pair

        first = results[0]
        pair = (str(first["dest_id"]), str(first.get("dest_type", "city")))
        self._cache.set(cache_key, pair, ttl=86400)
        return pair

    # ------------------------------------------------------------------
    # Search hotels
    # ------------------------------------------------------------------

    async def search_hotels(
        self,
        destination: str,
        check_in: str,
        check_out: str,
        adults: int = 1,
        *,
        page: int = 1,
        currency: str = "USD",
    ) -> list[dict[str, Any]]:
        """Search for hotels at a destination.

        Returns a list of normalised hotel dicts compatible with
        ``normalise_raw()`` in server.py.
        """
        cache_key = TTLCache.make_key(
            "booking_search", destination.lower(), check_in, check_out,
            adults, page, currency,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        dest_id, dest_type = await self._get_dest_id(destination)

        data = await self._request(
            "hotels/searchHotels",
            {
                "dest_id": dest_id,
                "search_type": dest_type,
                "arrival_date": check_in,
                "departure_date": check_out,
                "adults": adults,
                "page_number": page,
                "currency_code": currency,
                "units": "metric",
                "temperature_unit": "c",
                "languagecode": "en-us",
            },
        )

        hotels_raw = data.get("data", {}).get("hotels", [])
        results = [self._normalise_search_result(h, currency) for h in hotels_raw]

        self._cache.set(cache_key, results)
        logger.info(
            "booking_search_completed",
            destination=destination,
            count=len(results),
        )
        return results

    def _normalise_search_result(
        self, raw: dict[str, Any], currency: str,
    ) -> dict[str, Any]:
        """Convert a Booking.com search result into our standard format."""
        prop = raw.get("property", {})
        price_info = prop.get("priceBreakdown", {})
        gross_price = price_info.get("grossPrice", {})

        lat = prop.get("latitude", 0.0)
        lng = prop.get("longitude", 0.0)

        photos = []
        if prop.get("photoUrls"):
            photos = list(prop["photoUrls"])[:5]

        review_score = prop.get("reviewScore")
        if review_score is not None:
            review_score = float(review_score)

        return {
            "hotel_id": str(prop.get("id", "")),
            "name": prop.get("name", "Unknown"),
            "stars": prop.get("propertyClass"),
            "review_score": review_score,
            "review_count": prop.get("reviewCount"),
            "price_total": float(gross_price.get("value", 0)) if gross_price else None,
            "currency": gross_price.get("currency", currency),
            "latitude": float(lat) if lat else 0.0,
            "longitude": float(lng) if lng else 0.0,
            "area": prop.get("wishlistName"),
            "distance_to_center_km": None,
            "amenities": [],
            "photos": photos,
            "deep_link": prop.get("externalUrl") or prop.get("deeplink"),
            "data_source": "booking",
        }

    # ------------------------------------------------------------------
    # Hotel details
    # ------------------------------------------------------------------

    async def get_hotel_details(
        self,
        hotel_id: str,
        check_in: str | None = None,
        check_out: str | None = None,
    ) -> dict[str, Any]:
        """Get full hotel details by ID."""
        cache_key = TTLCache.make_key(
            "booking_detail", hotel_id, check_in, check_out,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, Any] = {
            "hotel_id": hotel_id,
            "languagecode": "en-us",
        }
        if check_in:
            params["arrival_date"] = check_in
        if check_out:
            params["departure_date"] = check_out

        data = await self._request("hotels/getHotelDetails", params)
        detail = data.get("data", {})

        result = self._normalise_hotel_detail(detail, hotel_id)
        self._cache.set(cache_key, result)
        return result

    def _normalise_hotel_detail(
        self, raw: dict[str, Any], hotel_id: str,
    ) -> dict[str, Any]:
        """Convert Booking.com hotel detail into our standard format."""
        photos = []
        for photo in (raw.get("photos") or [])[:10]:
            url = photo.get("url_max") or photo.get("url_original")
            if url:
                photos.append(url)

        rooms: list[dict[str, Any]] = []
        for room_raw in (raw.get("rooms") or {}).values():
            rooms.append({
                "room_id": str(room_raw.get("id", "")),
                "name": room_raw.get("name", "Standard Room"),
                "type": room_raw.get("room_type", "standard"),
                "max_occupancy": room_raw.get("max_persons", 2),
                "bed_type": room_raw.get("bed_type"),
                "size_sqm": room_raw.get("room_surface_in_m2"),
                "photos": [
                    p.get("url_original")
                    for p in (room_raw.get("photos") or [])[:3]
                    if p.get("url_original")
                ],
            })

        review_data = raw.get("review_score_word")
        review_score = raw.get("review_score")

        facilities_raw = raw.get("facilities_block", {}).get("facilities", [])
        facilities = []
        for fac in facilities_raw:
            facilities.append({
                "name": fac.get("name", ""),
                "category": fac.get("facility_type_name", "general"),
                "available": True,
            })

        return {
            "hotel_id": hotel_id,
            "name": raw.get("hotel_name", "Unknown"),
            "description": raw.get("description"),
            "stars": raw.get("class"),
            "address": raw.get("address"),
            "location": {
                "lat": float(raw.get("latitude", 0)),
                "lng": float(raw.get("longitude", 0)),
                "area": raw.get("district"),
            },
            "check_in_time": raw.get("checkin", {}).get("from"),
            "check_out_time": raw.get("checkout", {}).get("until"),
            "photos": photos,
            "rooms": rooms,
            "review": {
                "overall_score": float(review_score) if review_score else 0.0,
                "total_reviews": raw.get("review_nr", 0),
                "score_word": review_data,
            },
            "facilities": facilities,
            "policies": {
                "check_in": raw.get("checkin", {}).get("from", ""),
                "check_out": raw.get("checkout", {}).get("until", ""),
            },
            "data_source": "booking",
        }

    # ------------------------------------------------------------------
    # Search by coordinates
    # ------------------------------------------------------------------

    async def search_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        check_in: str,
        check_out: str,
        adults: int = 1,
        *,
        currency: str = "USD",
    ) -> list[dict[str, Any]]:
        """Search hotels near a coordinate point."""
        cache_key = TTLCache.make_key(
            "booking_coords", round(latitude, 4), round(longitude, 4),
            radius_km, check_in, check_out, adults,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._request(
            "hotels/searchHotels",
            {
                "latitude": latitude,
                "longitude": longitude,
                "arrival_date": check_in,
                "departure_date": check_out,
                "adults": adults,
                "search_type": "latlong",
                "currency_code": currency,
                "units": "metric",
                "temperature_unit": "c",
                "languagecode": "en-us",
            },
        )

        hotels_raw = data.get("data", {}).get("hotels", [])
        results = [self._normalise_search_result(h, currency) for h in hotels_raw]

        self._cache.set(cache_key, results)
        return results

    # ------------------------------------------------------------------
    # Hotel facilities
    # ------------------------------------------------------------------

    async def get_hotel_facilities(
        self, hotel_id: str,
    ) -> list[dict[str, Any]]:
        """Get the list of facilities/amenities for a hotel."""
        cache_key = TTLCache.make_key("booking_facilities", hotel_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Facilities come from the detail endpoint
        detail = await self.get_hotel_details(hotel_id)
        facilities = detail.get("facilities", [])

        self._cache.set(cache_key, facilities)
        return facilities
