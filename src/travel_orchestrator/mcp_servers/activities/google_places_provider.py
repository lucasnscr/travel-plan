"""Google Places API (New) provider for activity/place discovery.

Provides real place search, details, photos, directions, and geocoding
using the Google Places API (New) and Maps Platform APIs.
Falls back gracefully when no API key is configured.

References:
- Places (New): https://places.googleapis.com/v1/places
- Directions: https://maps.googleapis.com/maps/api/directions/json
- Geocoding: https://maps.googleapis.com/maps/api/geocode/json
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from travel_orchestrator.mcp_servers.activities.models import (
    DirectionRoute,
    DirectionStep,
    GeocodeResult,
    GeoLocation,
    Place,
    PlaceDetail,
    PlaceOpeningHours,
    PlacePhoto,
    PlaceReview,
    Viewport,
)
from travel_orchestrator.mcp_servers.hotels.retry import RetryableError, with_retry
from travel_orchestrator.mcp_servers.weather.cache import TTLCache
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLACES_BASE = "https://places.googleapis.com/v1"
_MAPS_BASE = "https://maps.googleapis.com/maps/api"
_DEFAULT_TIMEOUT = 15.0
_CACHE_TTL_SEARCH = 3600  # 1 hour for search results
_CACHE_TTL_DETAILS = 86400  # 24 hours for place details
_CACHE_TTL_PHOTOS = 604800  # 7 days for photos
_MAX_RPS = 10  # Google allows higher QPS


def _get_google_maps_key() -> str | None:
    """Return the Google Maps API key from environment, or None."""
    return os.environ.get("GOOGLE_MAPS_API_KEY")


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple asyncio-based rate limiter using a semaphore."""

    def __init__(self, max_rps: int = _MAX_RPS) -> None:
        self._semaphore = asyncio.Semaphore(max_rps)
        self._max_rps = max_rps

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        asyncio.get_event_loop().call_later(1.0, self._semaphore.release)


# ---------------------------------------------------------------------------
# Field masks
# ---------------------------------------------------------------------------

_SEARCH_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.location,places.rating,places.userRatingCount,"
    "places.priceLevel,places.types,places.photos,"
    "places.currentOpeningHours,places.websiteUri,"
    "places.internationalPhoneNumber,places.editorialSummary,"
    "places.primaryType"
)

_DETAIL_FIELDS = (
    "id,displayName,formattedAddress,location,rating,"
    "userRatingCount,priceLevel,types,photos,"
    "currentOpeningHours,regularOpeningHours,"
    "websiteUri,internationalPhoneNumber,"
    "editorialSummary,reviews,viewport,"
    "googleMapsUri,businessStatus,primaryType"
)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GooglePlacesProvider:
    """Async client for Google Places API (New) and Maps Platform."""

    def __init__(
        self,
        *,
        places_base_url: str = _PLACES_BASE,
        maps_base_url: str = _MAPS_BASE,
        timeout: float = _DEFAULT_TIMEOUT,
        cache: TTLCache | None = None,
        api_key: str | None = None,
    ) -> None:
        self._places_base = places_base_url
        self._maps_base = maps_base_url
        self._timeout = timeout
        self._cache = cache or TTLCache(default_ttl_seconds=_CACHE_TTL_SEARCH)
        self._api_key = api_key or _get_google_maps_key()
        self._rate_limiter = _RateLimiter(_MAX_RPS)

    @property
    def is_configured(self) -> bool:
        """True if a Google Maps API key is available."""
        return bool(self._api_key)

    def _headers(self, field_mask: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key or "",
        }
        if field_mask:
            headers["X-Goog-FieldMask"] = field_mask
        return headers

    async def _post(
        self,
        url: str,
        body: dict[str, Any],
        *,
        field_mask: str | None = None,
    ) -> dict[str, Any]:
        """Make a rate-limited, retried POST request."""
        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY not configured")

        await self._rate_limiter.acquire()

        async def _do_request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url,
                    headers=self._headers(field_mask),
                    json=body,
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

        return await with_retry(_do_request, operation="google_places_post")

    async def _get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Make a rate-limited, retried GET request."""
        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY not configured")

        await self._rate_limiter.acquire()

        async def _do_request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    raise RetryableError(
                        "Rate limited", status_code=429, retry_after=2.0,
                    )
                if resp.status_code >= 500:
                    raise RetryableError(
                        f"Server error {resp.status_code}",
                        status_code=resp.status_code,
                    )
                resp.raise_for_status()
                return resp.json()

        return await with_retry(_do_request, operation="google_maps_get")

    # ------------------------------------------------------------------
    # Text Search (activities, restaurants)
    # ------------------------------------------------------------------

    async def text_search(
        self,
        query: str,
        *,
        language: str = "pt-BR",
        max_results: int = 20,
        location_bias: dict[str, Any] | None = None,
    ) -> list[Place]:
        """Search places by text query using Places API (New).

        POST https://places.googleapis.com/v1/places:searchText
        """
        cache_key = TTLCache.make_key(
            "gp_text", query.lower(), language, max_results,
            str(location_bias),
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body: dict[str, Any] = {
            "textQuery": query,
            "languageCode": language,
            "maxResultCount": min(max_results, 20),
        }
        if location_bias:
            body["locationBias"] = location_bias

        data = await self._post(
            f"{self._places_base}/places:searchText",
            body,
            field_mask=_SEARCH_FIELDS,
        )

        results = [
            self._normalise_place(p) for p in data.get("places", [])
        ]

        self._cache.set(cache_key, results, ttl=_CACHE_TTL_SEARCH)
        logger.info("google_text_search_done", query=query, count=len(results))
        return results

    # ------------------------------------------------------------------
    # Nearby Search
    # ------------------------------------------------------------------

    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        *,
        place_type: str = "tourist_attraction",
        language: str = "pt-BR",
        max_results: int = 20,
    ) -> list[Place]:
        """Search places near a coordinate.

        POST https://places.googleapis.com/v1/places:searchNearby
        """
        cache_key = TTLCache.make_key(
            "gp_nearby", round(latitude, 4), round(longitude, 4),
            radius_meters, place_type, language,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body: dict[str, Any] = {
            "includedTypes": [place_type],
            "maxResultCount": min(max_results, 20),
            "languageCode": language,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": float(radius_meters),
                },
            },
        }

        data = await self._post(
            f"{self._places_base}/places:searchNearby",
            body,
            field_mask=_SEARCH_FIELDS,
        )

        results = [
            self._normalise_place(p) for p in data.get("places", [])
        ]

        self._cache.set(cache_key, results, ttl=_CACHE_TTL_SEARCH)
        logger.info(
            "google_nearby_search_done",
            lat=latitude, lng=longitude, count=len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Place Details
    # ------------------------------------------------------------------

    async def get_place_details(
        self,
        place_id: str,
        *,
        language: str = "pt-BR",
    ) -> PlaceDetail:
        """Get full details for a place by ID.

        GET https://places.googleapis.com/v1/places/{place_id}
        """
        cache_key = TTLCache.make_key("gp_detail", place_id, language)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY not configured")

        await self._rate_limiter.acquire()

        async def _do_request() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._places_base}/places/{place_id}",
                    headers=self._headers(_DETAIL_FIELDS),
                    params={"languageCode": language},
                )
                if resp.status_code == 429:
                    raise RetryableError(
                        "Rate limited", status_code=429, retry_after=2.0,
                    )
                if resp.status_code >= 500:
                    raise RetryableError(
                        f"Server error {resp.status_code}",
                        status_code=resp.status_code,
                    )
                resp.raise_for_status()
                return resp.json()

        data = await with_retry(_do_request, operation="google_place_detail")
        result = self._normalise_place_detail(data)

        self._cache.set(cache_key, result, ttl=_CACHE_TTL_DETAILS)
        return result

    # ------------------------------------------------------------------
    # Place Photos
    # ------------------------------------------------------------------

    async def get_place_photos(
        self,
        place_id: str,
        *,
        max_photos: int = 5,
    ) -> list[PlacePhoto]:
        """Get photo URLs for a place.

        Uses the photo resource name from Place data.
        Photo URL: https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx=800&key={key}
        """
        cache_key = TTLCache.make_key("gp_photos", place_id, max_photos)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # First get the place details to get photo references
        detail = await self.get_place_details(place_id)

        photos: list[PlacePhoto] = []
        for photo in detail.photos[:max_photos]:
            if photo.photo_reference:
                url = (
                    f"{self._places_base}/{photo.photo_reference}"
                    f"/media?maxWidthPx=800&key={self._api_key}"
                )
                photos.append(PlacePhoto(
                    photo_reference=photo.photo_reference,
                    url=url,
                    width=photo.width,
                    height=photo.height,
                    attributions=photo.attributions,
                ))

        self._cache.set(cache_key, photos, ttl=_CACHE_TTL_PHOTOS)
        return photos

    # ------------------------------------------------------------------
    # Directions
    # ------------------------------------------------------------------

    async def get_directions(
        self,
        origin: str,
        destination: str,
        *,
        mode: str = "walking",
        language: str = "pt-BR",
    ) -> DirectionRoute:
        """Get directions between two points.

        GET https://maps.googleapis.com/maps/api/directions/json
        """
        cache_key = TTLCache.make_key(
            "gp_dir", origin.lower(), destination.lower(), mode, language,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._get(
            f"{self._maps_base}/directions/json",
            {
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "language": language,
                "key": self._api_key,
            },
        )

        route = self._normalise_direction(data)

        self._cache.set(cache_key, route, ttl=_CACHE_TTL_SEARCH)
        return route

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    async def geocode(
        self,
        address: str,
        *,
        language: str = "pt-BR",
    ) -> list[GeocodeResult]:
        """Forward geocode: address → coordinates.

        GET https://maps.googleapis.com/maps/api/geocode/json
        """
        cache_key = TTLCache.make_key("gp_geo", address.lower(), language)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._get(
            f"{self._maps_base}/geocode/json",
            {
                "address": address,
                "language": language,
                "key": self._api_key,
            },
        )

        results = [
            self._normalise_geocode(r)
            for r in data.get("results", [])
        ]

        self._cache.set(cache_key, results, ttl=_CACHE_TTL_DETAILS)
        return results

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
        *,
        language: str = "pt-BR",
    ) -> list[GeocodeResult]:
        """Reverse geocode: coordinates → address.

        GET https://maps.googleapis.com/maps/api/geocode/json
        """
        cache_key = TTLCache.make_key(
            "gp_revgeo", round(latitude, 5), round(longitude, 5), language,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._get(
            f"{self._maps_base}/geocode/json",
            {
                "latlng": f"{latitude},{longitude}",
                "language": language,
                "key": self._api_key,
            },
        )

        results = [
            self._normalise_geocode(r)
            for r in data.get("results", [])
        ]

        self._cache.set(cache_key, results, ttl=_CACHE_TTL_DETAILS)
        return results

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    def _normalise_place(self, raw: dict[str, Any]) -> Place:
        """Convert a Google Places API (New) result to our Place model."""
        loc = raw.get("location", {})
        display_name = raw.get("displayName", {})
        editorial = raw.get("editorialSummary", {})

        photos: list[PlacePhoto] = []
        for p in (raw.get("photos") or [])[:5]:
            photos.append(PlacePhoto(
                photo_reference=p.get("name", ""),
                width=p.get("widthPx", 0),
                height=p.get("heightPx", 0),
                attributions=[
                    a.get("displayName", {}).get("text", "")
                    for a in (p.get("authorAttributions") or [])
                ],
            ))

        hours_raw = raw.get("currentOpeningHours") or {}
        opening_hours = None
        if hours_raw:
            opening_hours = PlaceOpeningHours(
                open_now=hours_raw.get("openNow"),
                weekday_text=hours_raw.get("weekdayDescriptions", []),
            )

        primary_type = raw.get("primaryType", "")
        category = self._type_to_category(primary_type, raw.get("types", []))

        return Place(
            place_id=raw.get("id", ""),
            name=display_name.get("text", ""),
            category=category,
            address=raw.get("formattedAddress", ""),
            location=GeoLocation(
                lat=loc.get("latitude", 0.0),
                lng=loc.get("longitude", 0.0),
            ),
            rating=float(raw.get("rating", 0.0)),
            user_ratings_total=raw.get("userRatingCount", 0),
            price_level=self._parse_price_level(raw.get("priceLevel")),
            types=raw.get("types", []),
            photos=photos,
            opening_hours=opening_hours,
            website=raw.get("websiteUri"),
            phone=raw.get("internationalPhoneNumber"),
            description=editorial.get("text", ""),
            data_source="google_places",
        )

    def _normalise_place_detail(self, raw: dict[str, Any]) -> PlaceDetail:
        """Convert a full Google Places detail response."""
        place = self._normalise_place(raw)

        reviews: list[PlaceReview] = []
        for r in (raw.get("reviews") or [])[:10]:
            author = r.get("authorAttribution", {})
            original_text = r.get("originalText", {})
            reviews.append(PlaceReview(
                author=author.get("displayName", ""),
                rating=float(r.get("rating", 0)),
                text=original_text.get("text", ""),
                time=r.get("publishTime", ""),
                language=original_text.get("languageCode", ""),
            ))

        viewport = None
        vp_raw = raw.get("viewport")
        if vp_raw:
            low = vp_raw.get("low", {})
            high = vp_raw.get("high", {})
            viewport = Viewport(
                low=GeoLocation(
                    lat=low.get("latitude", 0.0),
                    lng=low.get("longitude", 0.0),
                ),
                high=GeoLocation(
                    lat=high.get("latitude", 0.0),
                    lng=high.get("longitude", 0.0),
                ),
            )

        return PlaceDetail(
            place_id=place.place_id,
            name=place.name,
            category=place.category,
            address=place.address,
            location=place.location,
            rating=place.rating,
            user_ratings_total=place.user_ratings_total,
            price_level=place.price_level,
            types=place.types,
            photos=place.photos,
            opening_hours=place.opening_hours,
            website=place.website,
            phone=place.phone,
            description=place.description,
            data_source="google_places",
            reviews=reviews,
            viewport=viewport,
            url=raw.get("googleMapsUri", ""),
            business_status=raw.get("businessStatus", "OPERATIONAL"),
            editorial_summary=(
                raw.get("editorialSummary", {}).get("text", "")
            ),
        )

    def _normalise_direction(self, raw: dict[str, Any]) -> DirectionRoute:
        """Convert a Google Directions API response."""
        routes = raw.get("routes", [])
        if not routes:
            return DirectionRoute(data_source="google_places")

        route = routes[0]
        legs = route.get("legs", [])
        if not legs:
            return DirectionRoute(data_source="google_places")

        leg = legs[0]
        steps: list[DirectionStep] = []
        for s in leg.get("steps", []):
            steps.append(DirectionStep(
                instruction=s.get("html_instructions", ""),
                distance_meters=s.get("distance", {}).get("value", 0),
                duration_seconds=s.get("duration", {}).get("value", 0),
                travel_mode=s.get("travel_mode", "WALKING"),
            ))

        return DirectionRoute(
            summary=route.get("summary", ""),
            distance_meters=leg.get("distance", {}).get("value", 0),
            duration_seconds=leg.get("duration", {}).get("value", 0),
            start_address=leg.get("start_address", ""),
            end_address=leg.get("end_address", ""),
            steps=steps,
            polyline=route.get("overview_polyline", {}).get("points", ""),
            data_source="google_places",
        )

    def _normalise_geocode(self, raw: dict[str, Any]) -> GeocodeResult:
        """Convert a Google Geocoding API result."""
        geo = raw.get("geometry", {}).get("location", {})
        return GeocodeResult(
            place_id=raw.get("place_id", ""),
            formatted_address=raw.get("formatted_address", ""),
            location=GeoLocation(
                lat=geo.get("lat", 0.0),
                lng=geo.get("lng", 0.0),
            ),
            types=raw.get("types", []),
            data_source="google_places",
        )

    @staticmethod
    def _type_to_category(
        primary_type: str, types: list[str],
    ) -> str:
        """Map Google place types to our activity categories."""
        type_map: dict[str, str] = {
            "museum": "museum",
            "art_gallery": "museum",
            "church": "museum",
            "hindu_temple": "museum",
            "mosque": "museum",
            "synagogue": "museum",
            "restaurant": "restaurant",
            "cafe": "restaurant",
            "bakery": "restaurant",
            "bar": "restaurant",
            "meal_delivery": "restaurant",
            "meal_takeaway": "restaurant",
            "park": "nature",
            "campground": "nature",
            "national_park": "nature",
            "natural_feature": "nature",
            "tourist_attraction": "tour",
            "point_of_interest": "tour",
            "amusement_park": "tour",
            "aquarium": "tour",
            "zoo": "tour",
            "shopping_mall": "shopping",
            "clothing_store": "shopping",
            "department_store": "shopping",
            "night_club": "nightlife",
            "casino": "nightlife",
        }

        # Check primary type first
        if primary_type in type_map:
            return type_map[primary_type]

        # Then check all types
        for t in types:
            if t in type_map:
                return type_map[t]

        return "tour"

    @staticmethod
    def _parse_price_level(value: Any) -> int | None:
        """Parse Google's PRICE_LEVEL enum to integer."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        level_map = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4,
        }
        return level_map.get(str(value))
