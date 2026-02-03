"""Competitor travel-offer PDF parser.

Extracts structured travel data from a competitor PDF brochure using
Anthropic Claude, falling back to a deterministic mock when no API
key is available.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from typing_extensions import TypedDict

from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PDF_SIZE_MB = 50

_EXTRACTION_MODEL = "claude-sonnet-4-20250514"
_EXTRACTION_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class PDFParsingError(Exception):
    """Raised when PDF file validation or parsing fails."""


# ---------------------------------------------------------------------------
# Local TypedDict
# ---------------------------------------------------------------------------


class CompetitorOffer(TypedDict):
    """Structured data extracted from a competitor travel offer PDF."""

    destination: str
    price: float
    currency: str
    duration_days: int
    highlights: list[str]
    hotel_name: str
    raw_text: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def parse_competitor_offer_pdf(pdf_path: str) -> CompetitorOffer:
    """Parse a competitor travel offer PDF and extract structured data.

    Uses Anthropic Claude when an API key is available, otherwise
    falls back to a deterministic mock extraction.

    Raises:
        PDFParsingError: If the file is invalid (not found,
            wrong format, too large).
    """
    _validate_pdf_file(pdf_path)

    client = _get_anthropic_client()
    if client is not None:
        try:
            with open(pdf_path, "rb") as f:
                pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

            response = await client.messages.create(
                model=_EXTRACTION_MODEL,
                max_tokens=_EXTRACTION_MAX_TOKENS,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": _build_extraction_prompt(),
                        },
                    ],
                }],
            )
            raw = response.content[0].text
            result = _parse_extraction_response(raw)
            logger.info("pdf_parsed_via_llm", path=pdf_path)
            return result
        except Exception as exc:
            logger.warning("pdf_llm_parsing_failed_using_mock", error=str(exc))

    logger.warning("using_mock_pdf_parsing", path=pdf_path)
    return _mock_parse(pdf_path)


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


def _build_extraction_prompt() -> str:
    """Return the prompt for extracting competitor offer data."""
    schema = {
        "destination": "string — city or region name",
        "price": "float — total package price",
        "currency": "string — USD, EUR, BRL, etc.",
        "duration_days": "integer — number of days",
        "highlights": ["string — list of included features/excursions"],
        "hotel_name": "string — name of included hotel",
    }
    return (
        "Extract the travel offer details from this PDF document.\n\n"
        f"Respond with this exact JSON schema:\n{json.dumps(schema, indent=2)}\n\n"
        "RULES:\n"
        "- Extract the main destination, total price, duration, hotel, "
        "and key highlights/excursions.\n"
        "- If multiple packages exist, extract the first/main one.\n"
        "- price must be a number, not a string.\n"
        "- highlights should list included tours, meals, transfers, etc.\n"
        "- JSON only, no commentary."
    )


# ---------------------------------------------------------------------------
# Private helpers — Response parsing
# ---------------------------------------------------------------------------


def _parse_extraction_response(raw: str) -> CompetitorOffer:
    """Parse LLM JSON response into a CompetitorOffer dict."""
    text = raw.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("pdf_json_parse_failed_using_mock")
        return _mock_parse("")

    return {
        "destination": str(data.get("destination", "")),
        "price": float(data.get("price", 0.0)),
        "currency": str(data.get("currency", "USD")),
        "duration_days": int(data.get("duration_days", 7)),
        "highlights": [str(h) for h in data.get("highlights", [])],
        "hotel_name": str(data.get("hotel_name", "")),
        "raw_text": raw,
    }


# ---------------------------------------------------------------------------
# Private helpers — Mock fallback
# ---------------------------------------------------------------------------

_MOCK_OFFERS: list[CompetitorOffer] = [
    {
        "destination": "Lisboa",
        "price": 4500.0,
        "currency": "BRL",
        "duration_days": 7,
        "highlights": [
            "Passeio em Sintra",
            "Tour de Tuk-Tuk por Alfama",
            "Degustacao de vinhos no Douro",
            "Jantar de fado",
        ],
        "hotel_name": "Hotel Avenida Palace",
        "raw_text": "(mock extraction)",
    },
    {
        "destination": "Paris",
        "price": 3200.0,
        "currency": "EUR",
        "duration_days": 5,
        "highlights": [
            "Ingresso Louvre sem fila",
            "Cruzeiro no Sena",
            "Tour Versailles",
            "Jantar na Torre Eiffel",
        ],
        "hotel_name": "Hotel Le Marais",
        "raw_text": "(mock extraction)",
    },
    {
        "destination": "Tokyo",
        "price": 6800.0,
        "currency": "USD",
        "duration_days": 10,
        "highlights": [
            "Excursao Monte Fuji",
            "Aula de culinaria japonesa",
            "Dia em Kyoto",
            "Experiencia ryokan",
        ],
        "hotel_name": "Shinjuku Granbell Hotel",
        "raw_text": "(mock extraction)",
    },
]


def _mock_parse(pdf_path: str) -> CompetitorOffer:
    """Return a deterministic mock CompetitorOffer based on filename hash."""
    name = os.path.basename(pdf_path) if pdf_path else "default"
    h = hashlib.md5(name.encode()).hexdigest()
    idx = int(h, 16) % len(_MOCK_OFFERS)
    return dict(_MOCK_OFFERS[idx])  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Private helpers — Validation
# ---------------------------------------------------------------------------


def _validate_pdf_file(pdf_path: str) -> None:
    """Validate that the PDF file exists, has .pdf extension,
    and is within the size limit.

    Raises:
        PDFParsingError: On any validation failure.
    """
    if not os.path.isfile(pdf_path):
        raise PDFParsingError(f"File not found: {pdf_path}")

    ext = os.path.splitext(pdf_path)[1].lower()
    if ext != ".pdf":
        raise PDFParsingError(
            f"Expected .pdf file, got '{ext}': {pdf_path}"
        )

    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    if size_mb > _MAX_PDF_SIZE_MB:
        raise PDFParsingError(
            f"File too large ({size_mb:.1f} MB). Maximum: {_MAX_PDF_SIZE_MB} MB"
        )
