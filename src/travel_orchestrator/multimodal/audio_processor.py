"""Audio-to-structured-requirements pipeline.

Transcribes audio via OpenAI Whisper API (with mock fallback when no API key
is configured), then uses Anthropic Claude to extract structured travel
requirements from the transcript and populate a ``TravelPlannerCore`` state.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import uuid
from typing import Any

import httpx
from typing_extensions import TypedDict

from travel_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_WHISPER_MODEL = "whisper-1"

_SUPPORTED_AUDIO_FORMATS: frozenset[str] = frozenset(
    {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
)
_MAX_FILE_SIZE_MB = 25

_EXTRACTION_MODEL = "claude-sonnet-4-20250514"
_EXTRACTION_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class AudioProcessingError(Exception):
    """Raised when audio file validation or processing fails."""


# ---------------------------------------------------------------------------
# Local TypedDict
# ---------------------------------------------------------------------------


class AudioRequirements(TypedDict):
    """Structured travel requirements extracted from an audio transcript."""

    destination: str
    duration_days: int
    start_month: str | None
    budget: dict[str, float | str]  # total (float), currency (str)
    interests: list[str]
    pace: str
    group_size: int
    special_requests: list[str]
    conflicts_detected: list[str]
    raw_transcript: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def transcribe_audio(audio_path: str) -> str:
    """Transcribe an audio file to text.

    Uses OpenAI Whisper API when an API key is available, otherwise
    falls back to a deterministic mock transcription.

    Raises:
        AudioProcessingError: If the file is invalid (not found,
            unsupported format, too large).
    """
    _validate_audio_file(audio_path)

    api_key = _get_openai_api_key()
    if api_key:
        try:
            transcript = await _call_whisper_api(audio_path, api_key)
            logger.info("audio_transcribed_via_whisper", path=audio_path)
            return transcript
        except Exception as exc:
            logger.warning("whisper_api_failed_using_mock", error=str(exc))

    logger.warning("using_mock_transcription", path=audio_path)
    return _mock_transcribe(audio_path)


async def extract_requirements_from_transcript(
    transcript: str,
) -> AudioRequirements:
    """Extract structured travel requirements from a transcript.

    Uses Anthropic Claude when a client is available, otherwise
    falls back to keyword-based mock extraction.
    """
    client = _get_anthropic_client()
    if client is not None:
        try:
            system_prompt = _build_extraction_system_prompt()
            user_prompt = _build_extraction_prompt(transcript)

            response = await client.messages.create(
                model=_EXTRACTION_MODEL,
                max_tokens=_EXTRACTION_MAX_TOKENS,
                temperature=0.1,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text
            result = _parse_extraction_response(raw)
            result["raw_transcript"] = transcript
            logger.info("requirements_extracted_via_llm")
            return result
        except Exception as exc:
            logger.warning("llm_extraction_failed_using_mock", error=str(exc))

    logger.warning("using_mock_extraction")
    return _mock_extract(transcript)


async def populate_state_from_audio(audio_path: str) -> dict[str, Any]:
    """Full pipeline: transcribe audio → extract requirements → build state.

    Returns a ``TravelPlannerCore``-compatible dict populated from the
    audio content.
    """
    transcript = await transcribe_audio(audio_path)
    requirements = await extract_requirements_from_transcript(transcript)

    state = _empty_state()
    state["plan_id"] = uuid.uuid4().hex[:8]
    state["destination"] = requirements["destination"]

    dates = _compute_dates(
        requirements["start_month"], requirements["duration_days"],
    )
    state["dates"] = dates

    state["budget"] = requirements["budget"]
    state["traveler_profile"] = {
        "interests": requirements["interests"],
        "pace": requirements["pace"],
        "group_size": requirements["group_size"],
    }

    logger.info(
        "state_populated_from_audio",
        destination=state["destination"],
        duration=requirements["duration_days"],
        plan_id=state["plan_id"],
    )
    return state


# ---------------------------------------------------------------------------
# Private helpers — API clients
# ---------------------------------------------------------------------------


def _get_openai_api_key() -> str | None:
    """Read OpenAI API key from settings, returning None on any failure."""
    try:
        from travel_orchestrator.config.settings import get_settings

        settings = get_settings()
        key = settings.openai_api_key
        return key if key else None
    except Exception:
        return None


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
# Private helpers — Whisper API
# ---------------------------------------------------------------------------


async def _call_whisper_api(audio_path: str, api_key: str) -> str:
    """Call OpenAI Whisper API via httpx to transcribe audio."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(audio_path, "rb") as f:
            response = await client.post(
                _WHISPER_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (os.path.basename(audio_path), f)},
                data={"model": _WHISPER_MODEL},
            )
        response.raise_for_status()
        data = response.json()
        return data.get("text", "")


# ---------------------------------------------------------------------------
# Private helpers — Mock fallbacks
# ---------------------------------------------------------------------------


_MOCK_TRANSCRIPTS: list[str] = [
    (
        "Quero viajar para Paris em julho com minha esposa. "
        "Nosso orcamento e de cinco mil euros. Gostamos de museus, "
        "gastronomia e passeios ao ar livre. Preferimos um ritmo moderado, "
        "sem correria. A viagem seria de sete dias."
    ),
    (
        "Estou planejando uma viagem para Tokyo em marco. "
        "Somos um grupo de quatro amigos. Temos um orcamento de "
        "oito mil dolares. Queremos visitar templos, experimentar "
        "a culinaria local e fazer compras. Dez dias seria ideal."
    ),
    (
        "Gostaria de ir para Roma em setembro, sozinho. "
        "Tenho tres mil euros para gastar. Adoro historia, "
        "arquitetura e comida italiana. Cinco dias sao suficientes. "
        "Prefiro um ritmo mais tranquilo."
    ),
]


def _mock_transcribe(audio_path: str) -> str:
    """Return a deterministic mock transcript based on filename hash."""
    h = hashlib.md5(os.path.basename(audio_path).encode()).hexdigest()
    idx = int(h, 16) % len(_MOCK_TRANSCRIPTS)
    return _MOCK_TRANSCRIPTS[idx]


# Destination keywords for mock extraction (PT + EN)
_DESTINATION_KEYWORDS: dict[str, str] = {
    "paris": "Paris",
    "tokyo": "Tokyo",
    "roma": "Rome",
    "rome": "Rome",
    "london": "London",
    "londres": "London",
    "nova york": "New York",
    "new york": "New York",
    "barcelona": "Barcelona",
    "lisboa": "Lisbon",
    "lisbon": "Lisbon",
    "berlin": "Berlin",
    "berlim": "Berlin",
    "amsterdam": "Amsterdam",
    "madrid": "Madrid",
}

_MONTH_MAP: dict[str, str] = {
    "janeiro": "january",
    "fevereiro": "february",
    "marco": "march",
    "março": "march",
    "abril": "april",
    "maio": "may",
    "junho": "june",
    "julho": "july",
    "agosto": "august",
    "setembro": "september",
    "outubro": "october",
    "novembro": "november",
    "dezembro": "december",
}

_INTEREST_KEYWORDS: dict[str, str] = {
    "museu": "museum",
    "museus": "museum",
    "museum": "museum",
    "gastronomia": "gastronomy",
    "culinaria": "gastronomy",
    "comida": "gastronomy",
    "food": "gastronomy",
    "historia": "history",
    "history": "history",
    "arquitetura": "architecture",
    "architecture": "architecture",
    "praia": "beach",
    "beach": "beach",
    "compras": "shopping",
    "shopping": "shopping",
    "natureza": "nature",
    "nature": "nature",
    "ar livre": "outdoors",
    "outdoor": "outdoors",
    "templo": "temples",
    "templos": "temples",
    "temple": "temples",
}

_PACE_KEYWORDS: dict[str, str] = {
    "tranquilo": "relaxed",
    "relaxed": "relaxed",
    "calmo": "relaxed",
    "moderado": "moderate",
    "moderate": "moderate",
    "intenso": "fast",
    "rapido": "fast",
    "fast": "fast",
    "correria": "moderate",  # "sem correria" implies moderate
}


def _mock_extract(transcript: str) -> AudioRequirements:
    """Simple keyword-based extraction fallback."""
    lower = transcript.lower()

    # Destination
    destination = ""
    for kw, name in _DESTINATION_KEYWORDS.items():
        if kw in lower:
            destination = name
            break

    # Duration — look for number + "dias"/"days"
    duration_days = 7
    duration_match = re.search(r"(\d+)\s*(?:dias|days|day)", lower)
    if duration_match:
        duration_days = int(duration_match.group(1))

    # Month
    start_month: str | None = None
    for pt_month, en_month in _MONTH_MAP.items():
        if pt_month in lower:
            start_month = en_month
            break
    if not start_month:
        # Try English month names
        for en_month in [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]:
            if en_month in lower:
                start_month = en_month
                break

    # Budget — look for number + currency keyword
    budget_total = 5000.0
    currency = "USD"
    budget_match = re.search(
        r"(\d[\d.,]*)\s*(?:mil\s+)?(euros?|dolares?|dollars?|reais|usd|eur|brl)",
        lower,
    )
    if budget_match:
        raw_num = budget_match.group(1).replace(",", "").replace(".", "")
        budget_total = float(raw_num)
        curr_word = budget_match.group(2)
        if "euro" in curr_word or curr_word == "eur":
            currency = "EUR"
        elif "dolar" in curr_word or "dollar" in curr_word or curr_word == "usd":
            currency = "USD"
        elif "rea" in curr_word or curr_word == "brl":
            currency = "BRL"

    # Handle "mil" (thousand) multiplier
    if re.search(r"(\d+)\s*mil", lower):
        mil_match = re.search(r"(\d+)\s*mil", lower)
        if mil_match:
            budget_total = float(mil_match.group(1)) * 1000

    # Interests
    interests: list[str] = []
    for kw, interest in _INTEREST_KEYWORDS.items():
        if kw in lower and interest not in interests:
            interests.append(interest)

    # Pace
    pace = "moderate"
    for kw, p in _PACE_KEYWORDS.items():
        if kw in lower:
            pace = p
            break

    # Group size — look for number + "amigos"/"pessoas"/"people"
    group_size = 2
    group_match = re.search(
        r"(\d+)\s*(?:amigos?|pessoas?|people|friends?)", lower,
    )
    if group_match:
        group_size = int(group_match.group(1))
    elif "sozinho" in lower or "alone" in lower or "solo" in lower:
        group_size = 1
    elif "casal" in lower or "esposa" in lower or "marido" in lower or "couple" in lower:
        group_size = 2

    return {
        "destination": destination,
        "duration_days": duration_days,
        "start_month": start_month,
        "budget": {"total": budget_total, "currency": currency},
        "interests": interests,
        "pace": pace,
        "group_size": group_size,
        "special_requests": [],
        "conflicts_detected": [],
        "raw_transcript": transcript,
    }


# ---------------------------------------------------------------------------
# Private helpers — Extraction prompts
# ---------------------------------------------------------------------------


def _build_extraction_system_prompt() -> str:
    """Return the system prompt for the extraction specialist."""
    return (
        "You are a travel requirement extraction specialist. Your job is to "
        "analyze a transcript of a person describing their travel plans and "
        "extract structured requirements. You MUST respond with valid JSON "
        "only, no markdown fences, no commentary outside the JSON."
    )


def _build_extraction_prompt(transcript: str) -> str:
    """Build the user prompt with transcript and expected JSON schema."""
    schema = {
        "destination": "string — city or region name",
        "duration_days": "integer — number of travel days",
        "start_month": "string or null — e.g. 'july', 'march'",
        "budget": {
            "total": "float — total budget amount",
            "currency": "string — 'USD', 'EUR', 'BRL', etc.",
        },
        "interests": ["string — list of interests/activities"],
        "pace": "string — 'relaxed', 'moderate', or 'fast'",
        "group_size": "integer — number of travelers",
        "special_requests": ["string — any special requirements"],
        "conflicts_detected": ["string — contradictions in the request"],
    }

    return (
        "Extract structured travel requirements from the following transcript.\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"RESPOND with this exact JSON schema:\n{json.dumps(schema, indent=2)}\n\n"
        "RULES:\n"
        "- If the transcript is in a non-English language, still output field "
        "values in English (except destination names which keep original form).\n"
        "- If a field is not mentioned, use sensible defaults: "
        "duration_days=7, pace='moderate', group_size=2, currency='USD'.\n"
        "- budget.total should be a number, not a string.\n"
        "- interests should be a list of lowercase English words.\n"
        "- If contradictions are detected (e.g. 'budget trip' but '5-star hotel'), "
        "list them in conflicts_detected.\n"
        "- JSON only, no commentary."
    )


# ---------------------------------------------------------------------------
# Private helpers — Response parsing
# ---------------------------------------------------------------------------


def _parse_extraction_response(raw: str) -> AudioRequirements:
    """Parse LLM JSON response into AudioRequirements."""
    text = raw.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("json_parse_failed_using_mock_extraction")
        return _mock_extract(raw)

    # Validate and fill defaults
    destination = str(data.get("destination", ""))
    duration_days = int(data.get("duration_days", 7))

    start_month_raw = data.get("start_month")
    start_month: str | None = str(start_month_raw).lower() if start_month_raw else None

    budget_data = data.get("budget", {})
    budget_total = float(budget_data.get("total", 5000.0))
    budget_currency = str(budget_data.get("currency", "USD"))

    interests = [str(i) for i in data.get("interests", [])]
    pace = str(data.get("pace", "moderate"))
    group_size = int(data.get("group_size", 2))
    special_requests = [str(r) for r in data.get("special_requests", [])]
    conflicts = [str(c) for c in data.get("conflicts_detected", [])]

    return {
        "destination": destination,
        "duration_days": duration_days,
        "start_month": start_month,
        "budget": {"total": budget_total, "currency": budget_currency},
        "interests": interests,
        "pace": pace,
        "group_size": group_size,
        "special_requests": special_requests,
        "conflicts_detected": conflicts,
        "raw_transcript": "",
    }


# ---------------------------------------------------------------------------
# Private helpers — Date computation
# ---------------------------------------------------------------------------


def _compute_dates(
    start_month: str | None, duration_days: int,
) -> dict[str, str]:
    """Compute start_date and end_date from month name + duration.

    If no month is specified, defaults to 30 days from today.
    If the month has already passed this year, rolls to next year.
    """
    today = datetime.date.today()

    if start_month:
        month_names = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]
        month_lower = start_month.lower()
        if month_lower in month_names:
            month_num = month_names.index(month_lower) + 1
            year = today.year
            # If month has already passed this year, use next year
            if month_num < today.month or (
                month_num == today.month and today.day > 15
            ):
                year += 1
            start_date = datetime.date(year, month_num, 1)
        else:
            start_date = today + datetime.timedelta(days=30)
    else:
        start_date = today + datetime.timedelta(days=30)

    end_date = start_date + datetime.timedelta(days=duration_days)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


# ---------------------------------------------------------------------------
# Private helpers — Validation
# ---------------------------------------------------------------------------


def _validate_audio_file(audio_path: str) -> None:
    """Validate that the audio file exists, has a supported format, and is
    within the size limit.

    Raises:
        AudioProcessingError: On any validation failure.
    """
    if not os.path.isfile(audio_path):
        raise AudioProcessingError(f"File not found: {audio_path}")

    ext = os.path.splitext(audio_path)[1].lower()
    if not ext:
        raise AudioProcessingError(f"No file extension: {audio_path}")
    if ext not in _SUPPORTED_AUDIO_FORMATS:
        raise AudioProcessingError(
            f"Unsupported audio format '{ext}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_AUDIO_FORMATS))}"
        )

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb > _MAX_FILE_SIZE_MB:
        raise AudioProcessingError(
            f"File too large ({size_mb:.1f} MB). Maximum: {_MAX_FILE_SIZE_MB} MB"
        )


# ---------------------------------------------------------------------------
# Private helpers — State builder
# ---------------------------------------------------------------------------


def _empty_state() -> dict[str, Any]:
    """Return a fresh TravelPlannerCore-compatible dict with defaults."""
    return {
        "plan_id": "",
        "destination": "",
        "dates": {"start_date": "", "end_date": ""},
        "budget": {"total": 0.0, "currency": "USD", "flexibility": 0.1},
        "traveler_profile": {"interests": [], "pace": "moderate", "group_size": 2},
        "selected_flight_id": None,
        "selected_hotel_id": None,
        "selected_activity_ids": [],
        "current_cost": 0.0,
        "revision_count": 0,
        "approval_status": "pending",
        "risk_flags": [],
        "alternative_plans": {},
        "destination_analysis": None,
        "hotel_options": [],
        "activity_options": [],
        "optimized_itinerary": None,
    }
