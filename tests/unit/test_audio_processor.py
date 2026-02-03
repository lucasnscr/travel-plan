"""Unit tests for the audio processor module."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.multimodal.audio_processor import (
    AudioProcessingError,
    AudioRequirements,
    _build_extraction_prompt,
    _build_extraction_system_prompt,
    _compute_dates,
    _empty_state,
    _mock_extract,
    _mock_transcribe,
    _parse_extraction_response,
    _validate_audio_file,
    extract_requirements_from_transcript,
    populate_state_from_audio,
    transcribe_audio,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio_file(tmp_path: Any, ext: str = ".mp3", size_kb: int = 10) -> str:
    """Create a mock audio file at tmp_path with given extension and size."""
    f = tmp_path / f"audio{ext}"
    f.write_bytes(b"\x00" * size_kb * 1024)
    return str(f)


def _make_transcript() -> str:
    return (
        "Quero viajar para Paris em julho com minha esposa. "
        "Nosso orcamento e de cinco mil euros. Gostamos de museus, "
        "gastronomia e passeios ao ar livre. Preferimos um ritmo moderado, "
        "sem correria. A viagem seria de sete dias."
    )


def _make_requirements(**overrides: Any) -> AudioRequirements:
    base: AudioRequirements = {
        "destination": "Paris",
        "duration_days": 7,
        "start_month": "july",
        "budget": {"total": 5000.0, "currency": "EUR"},
        "interests": ["museum", "gastronomy", "outdoors"],
        "pace": "moderate",
        "group_size": 2,
        "special_requests": [],
        "conflicts_detected": [],
        "raw_transcript": _make_transcript(),
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


# ===================================================================
# TestValidateAudioFile
# ===================================================================


class TestValidateAudioFile:
    def test_valid_mp3(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")
        _validate_audio_file(path)  # Should not raise

    def test_valid_wav(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".wav")
        _validate_audio_file(path)  # Should not raise

    def test_valid_m4a(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".m4a")
        _validate_audio_file(path)  # Should not raise

    def test_unsupported_format(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".txt")
        with pytest.raises(AudioProcessingError, match="Unsupported audio format"):
            _validate_audio_file(path)

    def test_file_not_found(self) -> None:
        with pytest.raises(AudioProcessingError, match="File not found"):
            _validate_audio_file("/nonexistent/audio.mp3")

    def test_file_too_large(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3", size_kb=26 * 1024)
        with pytest.raises(AudioProcessingError, match="File too large"):
            _validate_audio_file(path)

    def test_empty_extension(self, tmp_path: Any) -> None:
        f = tmp_path / "audiofile"
        f.write_bytes(b"\x00" * 1024)
        with pytest.raises(AudioProcessingError, match="No file extension"):
            _validate_audio_file(str(f))


# ===================================================================
# TestMockTranscribe
# ===================================================================


class TestMockTranscribe:
    def test_returns_nonempty_string(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")
        result = _mock_transcribe(path)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_deterministic_per_filename(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")
        result1 = _mock_transcribe(path)
        result2 = _mock_transcribe(path)
        assert result1 == result2

    def test_different_filenames_may_differ(self, tmp_path: Any) -> None:
        p1 = tmp_path / "file1.mp3"
        p2 = tmp_path / "file2.mp3"
        p1.write_bytes(b"\x00")
        p2.write_bytes(b"\x00")
        # Different filenames should produce the same or different — just no crash
        _mock_transcribe(str(p1))
        _mock_transcribe(str(p2))


# ===================================================================
# TestTranscribeAudio
# ===================================================================


class TestTranscribeAudio:
    @pytest.mark.asyncio
    async def test_with_whisper_api_success(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Hello, I want to travel."}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value="sk-test-key",
        ), patch(
            "travel_orchestrator.multimodal.audio_processor.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await transcribe_audio(path)

        assert result == "Hello, I want to travel."

    @pytest.mark.asyncio
    async def test_api_failure_falls_back_to_mock(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value="sk-test-key",
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._call_whisper_api",
            side_effect=Exception("API error"),
        ):
            result = await transcribe_audio(path)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_no_api_key_falls_back_to_mock(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ):
            result = await transcribe_audio(path)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_returns_string(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ):
            result = await transcribe_audio(path)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_invalid_file_raises(self) -> None:
        with pytest.raises(AudioProcessingError):
            await transcribe_audio("/nonexistent/audio.mp3")


# ===================================================================
# TestCallWhisperApi
# ===================================================================


class TestCallWhisperApi:
    @pytest.mark.asyncio
    async def test_successful_response(self, tmp_path: Any) -> None:
        from travel_orchestrator.multimodal.audio_processor import _call_whisper_api

        path = _make_audio_file(tmp_path, ".mp3")

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Transcribed text"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "travel_orchestrator.multimodal.audio_processor.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await _call_whisper_api(path, "sk-test")

        assert result == "Transcribed text"

    @pytest.mark.asyncio
    async def test_http_error_raises(self, tmp_path: Any) -> None:
        import httpx

        from travel_orchestrator.multimodal.audio_processor import _call_whisper_api

        path = _make_audio_file(tmp_path, ".mp3")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(),
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "travel_orchestrator.multimodal.audio_processor.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(httpx.HTTPStatusError):
            await _call_whisper_api(path, "sk-test")

    @pytest.mark.asyncio
    async def test_timeout_raises(self, tmp_path: Any) -> None:
        import httpx

        from travel_orchestrator.multimodal.audio_processor import _call_whisper_api

        path = _make_audio_file(tmp_path, ".mp3")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch(
            "travel_orchestrator.multimodal.audio_processor.httpx.AsyncClient",
            return_value=mock_client,
        ), pytest.raises(httpx.TimeoutException):
            await _call_whisper_api(path, "sk-test")


# ===================================================================
# TestBuildExtractionPrompt
# ===================================================================


class TestBuildExtractionPrompt:
    def test_contains_transcript(self) -> None:
        transcript = "I want to go to Paris"
        prompt = _build_extraction_prompt(transcript)
        assert "I want to go to Paris" in prompt

    def test_contains_json_schema(self) -> None:
        prompt = _build_extraction_prompt("test transcript")
        assert "destination" in prompt
        assert "duration_days" in prompt
        assert "budget" in prompt
        assert "interests" in prompt


class TestBuildExtractionSystemPrompt:
    def test_returns_nonempty_string(self) -> None:
        result = _build_extraction_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mentions_extraction(self) -> None:
        result = _build_extraction_system_prompt()
        assert "extraction" in result.lower()


# ===================================================================
# TestParseExtractionResponse
# ===================================================================


class TestParseExtractionResponse:
    def test_valid_json(self) -> None:
        import json

        data = {
            "destination": "Paris",
            "duration_days": 7,
            "start_month": "july",
            "budget": {"total": 5000.0, "currency": "EUR"},
            "interests": ["museum", "food"],
            "pace": "moderate",
            "group_size": 2,
            "special_requests": [],
            "conflicts_detected": [],
        }
        result = _parse_extraction_response(json.dumps(data))
        assert result["destination"] == "Paris"
        assert result["duration_days"] == 7

    def test_strips_markdown_fences(self) -> None:
        import json

        data = {"destination": "Tokyo", "duration_days": 10}
        raw = f"```json\n{json.dumps(data)}\n```"
        result = _parse_extraction_response(raw)
        assert result["destination"] == "Tokyo"

    def test_malformed_json_uses_mock(self) -> None:
        result = _parse_extraction_response("not valid json at all {{{")
        assert isinstance(result, dict)
        assert "destination" in result

    def test_missing_optional_fields_get_defaults(self) -> None:
        import json

        data = {"destination": "London"}
        result = _parse_extraction_response(json.dumps(data))
        assert result["destination"] == "London"
        assert result["duration_days"] == 7
        assert result["pace"] == "moderate"
        assert result["group_size"] == 2

    def test_all_required_fields_present(self) -> None:
        import json

        data = {"destination": "Berlin", "duration_days": 5}
        result = _parse_extraction_response(json.dumps(data))

        required_keys = {
            "destination", "duration_days", "start_month", "budget",
            "interests", "pace", "group_size", "special_requests",
            "conflicts_detected", "raw_transcript",
        }
        assert required_keys.issubset(set(result.keys()))


# ===================================================================
# TestExtractRequirements
# ===================================================================


class TestExtractRequirements:
    @pytest.mark.asyncio
    async def test_with_claude_success(self) -> None:
        import json

        mock_data = {
            "destination": "Paris",
            "duration_days": 7,
            "start_month": "july",
            "budget": {"total": 5000.0, "currency": "EUR"},
            "interests": ["museum"],
            "pace": "moderate",
            "group_size": 2,
            "special_requests": [],
            "conflicts_detected": [],
        }

        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_data)
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await extract_requirements_from_transcript("test transcript")

        assert result["destination"] == "Paris"
        assert result["raw_transcript"] == "test transcript"

    @pytest.mark.asyncio
    async def test_claude_failure_falls_back_to_mock(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await extract_requirements_from_transcript(_make_transcript())

        assert isinstance(result, dict)
        assert "destination" in result

    @pytest.mark.asyncio
    async def test_no_client_falls_back_to_mock(self) -> None:
        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            result = await extract_requirements_from_transcript(_make_transcript())

        assert isinstance(result, dict)
        assert "destination" in result

    @pytest.mark.asyncio
    async def test_returns_audio_requirements_dict(self) -> None:
        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            result = await extract_requirements_from_transcript("Test")

        required_keys = {
            "destination", "duration_days", "start_month", "budget",
            "interests", "pace", "group_size", "special_requests",
            "conflicts_detected", "raw_transcript",
        }
        assert required_keys.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_extracts_destination(self) -> None:
        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            result = await extract_requirements_from_transcript(
                "Quero viajar para Paris em julho",
            )

        assert result["destination"] == "Paris"


# ===================================================================
# TestMockExtract
# ===================================================================


class TestMockExtract:
    def test_finds_destination_keywords(self) -> None:
        result = _mock_extract("Quero ir para Tokyo em marco")
        assert result["destination"] == "Tokyo"

    def test_finds_budget_numbers(self) -> None:
        result = _mock_extract("Tenho 5 mil euros para a viagem")
        assert result["budget"]["total"] == 5000.0
        assert result["budget"]["currency"] == "EUR"

    def test_returns_valid_audio_requirements(self) -> None:
        result = _mock_extract("Any random text")
        required_keys = {
            "destination", "duration_days", "start_month", "budget",
            "interests", "pace", "group_size", "special_requests",
            "conflicts_detected", "raw_transcript",
        }
        assert required_keys.issubset(set(result.keys()))

    def test_finds_duration(self) -> None:
        result = _mock_extract("A viagem seria de 10 dias")
        assert result["duration_days"] == 10

    def test_finds_group_size_solo(self) -> None:
        result = _mock_extract("Vou viajar sozinho para Roma")
        assert result["group_size"] == 1

    def test_finds_interests(self) -> None:
        result = _mock_extract("Gosto de museus e gastronomia")
        assert "museum" in result["interests"]
        assert "gastronomy" in result["interests"]

    def test_finds_pace(self) -> None:
        result = _mock_extract("Prefiro ritmo tranquilo")
        assert result["pace"] == "relaxed"

    def test_finds_month_portuguese(self) -> None:
        result = _mock_extract("Quero viajar em setembro")
        assert result["start_month"] == "september"


# ===================================================================
# TestComputeDates
# ===================================================================


class TestComputeDates:
    def test_specific_month(self) -> None:
        result = _compute_dates("july", 7)
        assert "start_date" in result
        assert "end_date" in result
        assert "-07-01" in result["start_date"]

    def test_no_month_defaults_30_days(self) -> None:
        import datetime

        result = _compute_dates(None, 7)
        expected_start = datetime.date.today() + datetime.timedelta(days=30)
        assert result["start_date"] == expected_start.isoformat()

    def test_duration_applied(self) -> None:
        import datetime

        result = _compute_dates("july", 10)
        start = datetime.date.fromisoformat(result["start_date"])
        end = datetime.date.fromisoformat(result["end_date"])
        assert (end - start).days == 10

    def test_past_month_rolls_to_next_year(self) -> None:
        import datetime

        today = datetime.date.today()
        # Use a month that's definitely in the past
        if today.month >= 3:
            past_month = "january"
            result = _compute_dates(past_month, 7)
            start = datetime.date.fromisoformat(result["start_date"])
            assert start.year >= today.year
        else:
            # Early in the year — use december which would be next year
            result = _compute_dates("december", 7)
            start = datetime.date.fromisoformat(result["start_date"])
            assert start.year >= today.year


# ===================================================================
# TestPopulateStateFromAudio
# ===================================================================


class TestPopulateStateFromAudio:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocks(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            state = await populate_state_from_audio(path)

        assert isinstance(state, dict)
        assert "plan_id" in state
        assert "destination" in state

    @pytest.mark.asyncio
    async def test_populates_destination(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            state = await populate_state_from_audio(path)

        # Destination comes from mock transcript → mock extract
        assert isinstance(state["destination"], str)

    @pytest.mark.asyncio
    async def test_populates_budget(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            state = await populate_state_from_audio(path)

        assert "total" in state["budget"]
        assert "currency" in state["budget"]

    @pytest.mark.asyncio
    async def test_populates_dates(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            state = await populate_state_from_audio(path)

        assert "start_date" in state["dates"]
        assert "end_date" in state["dates"]
        assert len(state["dates"]["start_date"]) == 10  # ISO format

    @pytest.mark.asyncio
    async def test_populates_traveler_profile(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            state = await populate_state_from_audio(path)

        profile = state["traveler_profile"]
        assert "interests" in profile
        assert "pace" in profile
        assert "group_size" in profile

    @pytest.mark.asyncio
    async def test_generates_plan_id(self, tmp_path: Any) -> None:
        path = _make_audio_file(tmp_path, ".mp3")

        with patch(
            "travel_orchestrator.multimodal.audio_processor._get_openai_api_key",
            return_value=None,
        ), patch(
            "travel_orchestrator.multimodal.audio_processor._get_anthropic_client",
            return_value=None,
        ):
            state = await populate_state_from_audio(path)

        assert len(state["plan_id"]) == 8
        assert state["plan_id"].isalnum()


# ===================================================================
# TestEmptyState
# ===================================================================


class TestEmptyState:
    def test_has_all_travel_planner_core_keys(self) -> None:
        state = _empty_state()
        expected_keys = {
            "plan_id", "destination", "dates", "budget", "traveler_profile",
            "selected_flight_id", "selected_hotel_id", "selected_activity_ids",
            "current_cost", "revision_count", "approval_status", "risk_flags",
            "alternative_plans", "destination_analysis", "hotel_options",
            "activity_options", "optimized_itinerary",
        }
        assert expected_keys.issubset(set(state.keys()))

    def test_default_values_correct(self) -> None:
        state = _empty_state()
        assert state["plan_id"] == ""
        assert state["destination"] == ""
        assert state["current_cost"] == 0.0
        assert state["revision_count"] == 0
        assert state["approval_status"] == "pending"
        assert state["risk_flags"] == []
        assert state["selected_flight_id"] is None
        assert state["selected_hotel_id"] is None
        assert state["optimized_itinerary"] is None


# ===================================================================
# TestAudioProcessingError
# ===================================================================


class TestAudioProcessingError:
    def test_is_exception_subclass(self) -> None:
        assert issubclass(AudioProcessingError, Exception)

    def test_message_preserved(self) -> None:
        err = AudioProcessingError("test error message")
        assert str(err) == "test error message"
