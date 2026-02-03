"""Unit tests for the image analyzer module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.multimodal.image_analyzer import (
    ImageAnalysisError,
    _build_vision_prompt,
    _mock_analyze,
    _parse_vision_response,
    _validate_image_file,
    analyze_inspiration_image,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_image_file(tmp_path: Any, ext: str = ".jpg", size_kb: int = 10) -> str:
    """Create a mock image file at tmp_path with given extension and size."""
    f = tmp_path / f"photo{ext}"
    f.write_bytes(b"\x00" * size_kb * 1024)
    return str(f)


# ===================================================================
# TestValidateImageFile
# ===================================================================


class TestValidateImageFile:
    def test_valid_jpg(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg")
        _validate_image_file(path)  # Should not raise

    def test_valid_png(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".png")
        _validate_image_file(path)  # Should not raise

    def test_unsupported_format(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".bmp")
        with pytest.raises(ImageAnalysisError, match="Unsupported image format"):
            _validate_image_file(path)

    def test_file_not_found(self) -> None:
        with pytest.raises(ImageAnalysisError, match="File not found"):
            _validate_image_file("/nonexistent/photo.jpg")

    def test_file_too_large(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg", size_kb=21 * 1024)
        with pytest.raises(ImageAnalysisError, match="File too large"):
            _validate_image_file(path)

    def test_empty_extension(self, tmp_path: Any) -> None:
        f = tmp_path / "photofile"
        f.write_bytes(b"\x00" * 1024)
        with pytest.raises(ImageAnalysisError, match="No file extension"):
            _validate_image_file(str(f))


# ===================================================================
# TestMockAnalyze
# ===================================================================


class TestMockAnalyze:
    def test_returns_travel_vibe(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg")
        result = _mock_analyze(path)
        assert isinstance(result, dict)
        assert "destination_suggestions" in result
        assert "vibe_tags" in result
        assert "budget_tier_guess" in result
        assert "season_preference" in result
        assert "activity_bias" in result

    def test_deterministic(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg")
        result1 = _mock_analyze(path)
        result2 = _mock_analyze(path)
        assert result1 == result2

    def test_has_all_required_fields(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".png")
        result = _mock_analyze(path)
        assert isinstance(result["destination_suggestions"], list)
        assert len(result["destination_suggestions"]) >= 1
        assert isinstance(result["vibe_tags"], list)
        assert result["budget_tier_guess"] in ("budget", "mid", "luxury")
        assert isinstance(result["season_preference"], str)
        assert isinstance(result["activity_bias"], list)


# ===================================================================
# TestParseVisionResponse
# ===================================================================


class TestParseVisionResponse:
    def test_valid_json(self) -> None:
        data = {
            "destination_suggestions": ["Paris", "Rome"],
            "vibe_tags": ["romantic", "cultural"],
            "budget_tier_guess": "mid",
            "season_preference": "spring",
            "activity_bias": ["museum", "food"],
        }
        result = _parse_vision_response(json.dumps(data))
        assert result["destination_suggestions"] == ["Paris", "Rome"]
        assert result["budget_tier_guess"] == "mid"

    def test_strips_markdown_fences(self) -> None:
        data = {"destination_suggestions": ["Tokyo"], "vibe_tags": ["modern"]}
        raw = f"```json\n{json.dumps(data)}\n```"
        result = _parse_vision_response(raw)
        assert result["destination_suggestions"] == ["Tokyo"]

    def test_malformed_json_uses_mock(self) -> None:
        result = _parse_vision_response("not valid json {{{")
        assert isinstance(result, dict)
        assert "destination_suggestions" in result


# ===================================================================
# TestBuildVisionPrompt
# ===================================================================


class TestBuildVisionPrompt:
    def test_returns_nonempty_string(self) -> None:
        prompt = _build_vision_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_schema_fields(self) -> None:
        prompt = _build_vision_prompt()
        assert "destination_suggestions" in prompt
        assert "vibe_tags" in prompt
        assert "budget_tier_guess" in prompt


# ===================================================================
# TestAnalyzeInspirationImage
# ===================================================================


class TestAnalyzeInspirationImage:
    @pytest.mark.asyncio
    async def test_mock_fallback_when_no_api_key(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg")

        with patch(
            "travel_orchestrator.multimodal.image_analyzer._get_anthropic_client",
            return_value=None,
        ):
            result = await analyze_inspiration_image(path)

        assert isinstance(result, dict)
        assert "destination_suggestions" in result

    @pytest.mark.asyncio
    async def test_api_failure_falls_back_to_mock(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg")

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

        with patch(
            "travel_orchestrator.multimodal.image_analyzer._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await analyze_inspiration_image(path)

        assert isinstance(result, dict)
        assert "destination_suggestions" in result

    @pytest.mark.asyncio
    async def test_success_with_mock_client(self, tmp_path: Any) -> None:
        path = _make_image_file(tmp_path, ".jpg")

        mock_data = {
            "destination_suggestions": ["Barcelona", "Madrid"],
            "vibe_tags": ["sunny", "vibrant"],
            "budget_tier_guess": "mid",
            "season_preference": "summer",
            "activity_bias": ["beach", "food"],
        }
        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_data)
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "travel_orchestrator.multimodal.image_analyzer._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await analyze_inspiration_image(path)

        assert result["destination_suggestions"] == ["Barcelona", "Madrid"]

    @pytest.mark.asyncio
    async def test_invalid_file_raises(self) -> None:
        with pytest.raises(ImageAnalysisError):
            await analyze_inspiration_image("/nonexistent/photo.jpg")
