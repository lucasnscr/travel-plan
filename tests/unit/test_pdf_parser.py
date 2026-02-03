"""Unit tests for the PDF parser module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from travel_orchestrator.multimodal.pdf_parser import (
    PDFParsingError,
    _build_extraction_prompt,
    _mock_parse,
    _parse_extraction_response,
    _validate_pdf_file,
    parse_competitor_offer_pdf,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pdf_file(tmp_path: Any, size_kb: int = 10) -> str:
    """Create a mock PDF file at tmp_path."""
    f = tmp_path / "offer.pdf"
    f.write_bytes(b"%PDF-1.4\n" + b"\x00" * size_kb * 1024)
    return str(f)


# ===================================================================
# TestValidatePdfFile
# ===================================================================


class TestValidatePdfFile:
    def test_valid_pdf(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)
        _validate_pdf_file(path)  # Should not raise

    def test_wrong_extension(self, tmp_path: Any) -> None:
        f = tmp_path / "offer.docx"
        f.write_bytes(b"\x00" * 1024)
        with pytest.raises(PDFParsingError, match="Expected .pdf"):
            _validate_pdf_file(str(f))

    def test_file_not_found(self) -> None:
        with pytest.raises(PDFParsingError, match="File not found"):
            _validate_pdf_file("/nonexistent/offer.pdf")

    def test_file_too_large(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path, size_kb=51 * 1024)
        with pytest.raises(PDFParsingError, match="File too large"):
            _validate_pdf_file(path)


# ===================================================================
# TestMockParse
# ===================================================================


class TestMockParse:
    def test_returns_competitor_offer(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)
        result = _mock_parse(path)
        assert isinstance(result, dict)
        assert "destination" in result
        assert "price" in result
        assert "currency" in result
        assert "duration_days" in result
        assert "highlights" in result
        assert "hotel_name" in result
        assert "raw_text" in result

    def test_deterministic(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)
        result1 = _mock_parse(path)
        result2 = _mock_parse(path)
        assert result1 == result2

    def test_has_valid_types(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)
        result = _mock_parse(path)
        assert isinstance(result["destination"], str)
        assert isinstance(result["price"], float)
        assert isinstance(result["currency"], str)
        assert isinstance(result["duration_days"], int)
        assert isinstance(result["highlights"], list)
        assert isinstance(result["hotel_name"], str)


# ===================================================================
# TestParseExtractionResponse
# ===================================================================


class TestParseExtractionResponse:
    def test_valid_json(self) -> None:
        data = {
            "destination": "Paris",
            "price": 3200.0,
            "currency": "EUR",
            "duration_days": 5,
            "highlights": ["Louvre", "Eiffel"],
            "hotel_name": "Hotel Le Marais",
        }
        result = _parse_extraction_response(json.dumps(data))
        assert result["destination"] == "Paris"
        assert result["price"] == 3200.0

    def test_strips_markdown_fences(self) -> None:
        data = {"destination": "Tokyo", "price": 5000.0}
        raw = f"```json\n{json.dumps(data)}\n```"
        result = _parse_extraction_response(raw)
        assert result["destination"] == "Tokyo"

    def test_malformed_json_uses_mock(self) -> None:
        result = _parse_extraction_response("not valid json")
        assert isinstance(result, dict)
        assert "destination" in result

    def test_missing_fields_get_defaults(self) -> None:
        data = {"destination": "London"}
        result = _parse_extraction_response(json.dumps(data))
        assert result["destination"] == "London"
        assert result["price"] == 0.0
        assert result["currency"] == "USD"
        assert result["duration_days"] == 7


# ===================================================================
# TestBuildExtractionPrompt
# ===================================================================


class TestBuildExtractionPrompt:
    def test_returns_nonempty_string(self) -> None:
        prompt = _build_extraction_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_schema_fields(self) -> None:
        prompt = _build_extraction_prompt()
        assert "destination" in prompt
        assert "price" in prompt
        assert "highlights" in prompt


# ===================================================================
# TestParseCompetitorOfferPdf
# ===================================================================


class TestParseCompetitorOfferPdf:
    @pytest.mark.asyncio
    async def test_mock_fallback_when_no_api_key(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)

        with patch(
            "travel_orchestrator.multimodal.pdf_parser._get_anthropic_client",
            return_value=None,
        ):
            result = await parse_competitor_offer_pdf(path)

        assert isinstance(result, dict)
        assert "destination" in result

    @pytest.mark.asyncio
    async def test_api_failure_falls_back_to_mock(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

        with patch(
            "travel_orchestrator.multimodal.pdf_parser._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await parse_competitor_offer_pdf(path)

        assert isinstance(result, dict)
        assert "destination" in result

    @pytest.mark.asyncio
    async def test_success_with_mock_client(self, tmp_path: Any) -> None:
        path = _make_pdf_file(tmp_path)

        mock_data = {
            "destination": "Lisboa",
            "price": 4500.0,
            "currency": "BRL",
            "duration_days": 7,
            "highlights": ["Sintra", "Fado"],
            "hotel_name": "Hotel Avenida",
        }
        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_data)
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "travel_orchestrator.multimodal.pdf_parser._get_anthropic_client",
            return_value=mock_client,
        ):
            result = await parse_competitor_offer_pdf(path)

        assert result["destination"] == "Lisboa"
        assert result["price"] == 4500.0

    @pytest.mark.asyncio
    async def test_invalid_file_raises(self) -> None:
        with pytest.raises(PDFParsingError):
            await parse_competitor_offer_pdf("/nonexistent/offer.pdf")
