"""Inspiration-image analysis pipeline.

Uses Anthropic Claude vision to extract travel vibes from an uploaded
image, falling back to a deterministic mock when no API key is available.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from travel_orchestrator.state.models import TravelVibe
from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUPPORTED_IMAGE_FORMATS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp"}
)
_MAX_IMAGE_SIZE_MB = 20

_VISION_MODEL = "claude-sonnet-4-20250514"
_VISION_MAX_TOKENS = 1024

# Media type mapping for Anthropic API
_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ImageAnalysisError(Exception):
    """Raised when image file validation or processing fails."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyze_inspiration_image(image_path: str) -> TravelVibe:
    """Analyze an inspiration image and extract travel vibes.

    Uses Anthropic Claude vision when an API key is available,
    otherwise falls back to a deterministic mock analysis.

    Raises:
        ImageAnalysisError: If the file is invalid (not found,
            unsupported format, too large).
    """
    _validate_image_file(image_path)

    client = _get_anthropic_client()
    if client is not None:
        try:
            ext = os.path.splitext(image_path)[1].lower()
            media_type = _MEDIA_TYPES.get(ext, "image/jpeg")

            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            response = await client.messages.create(
                model=_VISION_MODEL,
                max_tokens=_VISION_MAX_TOKENS,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": _build_vision_prompt(),
                        },
                    ],
                }],
            )
            raw = response.content[0].text
            result = _parse_vision_response(raw)
            logger.info("image_analyzed_via_vision", path=image_path)
            return result
        except Exception as exc:
            logger.warning("vision_api_failed_using_mock", error=str(exc))

    logger.warning("using_mock_image_analysis", path=image_path)
    return _mock_analyze(image_path)


# ---------------------------------------------------------------------------
# Private helpers — API client
# ---------------------------------------------------------------------------


def _get_anthropic_client() -> Any | None:
    """Create an ``AsyncAnthropic`` client, or ``None`` if unavailable."""
    try:
        from anthropic import AsyncAnthropic

        from travel_orchestrator.config.settings import get_settings

        settings = get_settings()
        api_key = settings.anthropic_api_key
        if not api_key:
            logger.warning("no_anthropic_api_key")
            return None
        return AsyncAnthropic(api_key=api_key)
    except Exception as exc:
        logger.warning("anthropic_client_unavailable", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Private helpers — Prompts
# ---------------------------------------------------------------------------


def _build_vision_prompt() -> str:
    """Return the prompt for extracting travel vibes from an image."""
    schema = {
        "destination_suggestions": ["list of 2-3 destination names"],
        "vibe_tags": ["list of 3-5 mood/aesthetic tags"],
        "budget_tier_guess": "one of: budget, mid, luxury",
        "season_preference": "e.g. summer, winter, spring, autumn, any",
        "activity_bias": ["list of 2-4 activity types"],
    }
    return (
        "Analyze this travel inspiration image. Extract the travel vibes, "
        "destination hints, and preferences it suggests.\n\n"
        f"Respond with this exact JSON schema:\n{json.dumps(schema, indent=2)}\n\n"
        "RULES:\n"
        "- destination_suggestions: real city/region names that match the image\n"
        "- vibe_tags: mood words like 'romantic', 'adventurous', 'cultural'\n"
        "- budget_tier_guess: infer from the setting (luxury resort vs hostel)\n"
        "- activity_bias: types like 'beach', 'museum', 'hiking', 'food'\n"
        "- JSON only, no commentary."
    )


# ---------------------------------------------------------------------------
# Private helpers — Response parsing
# ---------------------------------------------------------------------------


def _parse_vision_response(raw: str) -> TravelVibe:
    """Parse LLM JSON response into a TravelVibe dict."""
    text = raw.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("vision_json_parse_failed_using_mock")
        return _mock_analyze("")

    return {
        "destination_suggestions": [
            str(d) for d in data.get("destination_suggestions", ["Unknown"])
        ],
        "vibe_tags": [str(t) for t in data.get("vibe_tags", ["travel"])],
        "budget_tier_guess": str(data.get("budget_tier_guess", "mid")),
        "season_preference": str(data.get("season_preference", "any")),
        "activity_bias": [str(a) for a in data.get("activity_bias", ["sightseeing"])],
    }


# ---------------------------------------------------------------------------
# Private helpers — Mock fallback
# ---------------------------------------------------------------------------

_MOCK_VIBES: list[TravelVibe] = [
    {
        "destination_suggestions": ["Paris", "Rome"],
        "vibe_tags": ["romantic", "cultural", "historic"],
        "budget_tier_guess": "mid",
        "season_preference": "spring",
        "activity_bias": ["museum", "gastronomy", "walking_tour"],
    },
    {
        "destination_suggestions": ["Bali", "Phuket"],
        "vibe_tags": ["tropical", "relaxing", "adventurous"],
        "budget_tier_guess": "mid",
        "season_preference": "summer",
        "activity_bias": ["beach", "nature", "diving"],
    },
    {
        "destination_suggestions": ["Tokyo", "Kyoto"],
        "vibe_tags": ["modern", "traditional", "vibrant"],
        "budget_tier_guess": "mid",
        "season_preference": "autumn",
        "activity_bias": ["food", "temple", "shopping"],
    },
]


def _mock_analyze(image_path: str) -> TravelVibe:
    """Return a deterministic mock TravelVibe based on filename hash."""
    name = os.path.basename(image_path) if image_path else "default"
    h = hashlib.md5(name.encode()).hexdigest()
    idx = int(h, 16) % len(_MOCK_VIBES)
    return dict(_MOCK_VIBES[idx])  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Private helpers — Validation
# ---------------------------------------------------------------------------


def _validate_image_file(image_path: str) -> None:
    """Validate that the image file exists, has a supported format,
    and is within the size limit.

    Raises:
        ImageAnalysisError: On any validation failure.
    """
    if not os.path.isfile(image_path):
        raise ImageAnalysisError(f"File not found: {image_path}")

    ext = os.path.splitext(image_path)[1].lower()
    if not ext:
        raise ImageAnalysisError(f"No file extension: {image_path}")
    if ext not in _SUPPORTED_IMAGE_FORMATS:
        raise ImageAnalysisError(
            f"Unsupported image format '{ext}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_IMAGE_FORMATS))}"
        )

    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > _MAX_IMAGE_SIZE_MB:
        raise ImageAnalysisError(
            f"File too large ({size_mb:.1f} MB). Maximum: {_MAX_IMAGE_SIZE_MB} MB"
        )
