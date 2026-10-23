"""Unit tests for Tesseract OCR engine wrapper."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image, ImageDraw

from src.ocr.tesseract_engine import (
    DEFAULT_WINDOWS_TESSERACT_PATH,
    TesseractEngine,
    TesseractExecutionError,
    TesseractLanguageError,
    TesseractNotFoundError,
)


class TestTesseractEngineInit:
    """Test path resolution and initialization."""

    def test_custom_cmd_path(self, tmp_path: Path):
        fake_binary = tmp_path / "tesseract.exe"
        fake_binary.write_text("dummy", encoding="utf-8")
        engine = TesseractEngine(tesseract_cmd=str(fake_binary))
        assert engine.cmd_path == fake_binary

    def test_env_cmd_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        fake_binary = tmp_path / "custom_tess.exe"
        fake_binary.write_text("dummy", encoding="utf-8")
        monkeypatch.setenv("TESSERACT_CMD", str(fake_binary))
        engine = TesseractEngine()
        assert engine.cmd_path == fake_binary

    def test_fallback_windows_path(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("TESSERACT_CMD", raising=False)
        engine = TesseractEngine(tesseract_cmd=None)
        assert engine.cmd_path is not None


class TestTesseractEngineMocked:
    """Test behavior using mocked pytesseract calls."""

    @patch("src.ocr.tesseract_engine.pytesseract.get_tesseract_version")
    def test_is_available_true(self, mock_ver: MagicMock):
        mock_ver.return_value = "5.5.0"
        engine = TesseractEngine()
        assert engine.is_available() is True

    @patch("src.ocr.tesseract_engine.pytesseract.get_tesseract_version")
    def test_is_available_false(self, mock_ver: MagicMock):
        mock_ver.side_effect = Exception("Not found")
        engine = TesseractEngine()
        assert engine.is_available() is False

    @patch("src.ocr.tesseract_engine.pytesseract.get_tesseract_version")
    def test_get_version_not_found(self, mock_ver: MagicMock):
        mock_ver.side_effect = Exception("Not found")
        engine = TesseractEngine()
        with pytest.raises(TesseractNotFoundError):
            engine.get_version()

    @patch("src.ocr.tesseract_engine.pytesseract.get_languages")
    @patch("src.ocr.tesseract_engine.pytesseract.get_tesseract_version")
    def test_validate_languages_missing(self, mock_ver: MagicMock, mock_langs: MagicMock):
        mock_ver.return_value = "5.5.0"
        mock_langs.return_value = ["eng", "osd"]
        engine = TesseractEngine()
        with pytest.raises(TesseractLanguageError):
            engine.validate_languages("vie")

    @patch("src.ocr.tesseract_engine.pytesseract.image_to_string")
    @patch("src.ocr.tesseract_engine.pytesseract.get_languages")
    @patch("src.ocr.tesseract_engine.pytesseract.get_tesseract_version")
    def test_ocr_image_success(
        self, mock_ver: MagicMock, mock_langs: MagicMock, mock_img_to_str: MagicMock
    ):
        mock_ver.return_value = "5.5.0"
        mock_langs.return_value = ["vie", "eng"]
        mock_img_to_str.return_value = "Báo cáo tài chính năm 2020\n"

        engine = TesseractEngine()
        img = Image.new("RGB", (50, 50), color="white")
        result = engine.ocr_image(img, lang="vie")
        assert "Báo cáo tài chính" in result

    def test_ocr_image_file_not_found(self):
        engine = TesseractEngine()
        with patch.object(engine, "is_available", return_value=True):
            with patch.object(engine, "validate_languages"):
                with pytest.raises(FileNotFoundError):
                    engine.ocr_image(Path("non_existent_image_12345.png"))

    def test_ocr_image_invalid_type(self):
        engine = TesseractEngine()
        with patch.object(engine, "is_available", return_value=True):
            with patch.object(engine, "validate_languages"):
                with pytest.raises(TypeError):
                    engine.ocr_image(12345)  # type: ignore


class TestTesseractEngineRealSmoke:
    """Smoke test running against real Tesseract installation if present."""

    def test_real_tesseract_smoke(self):
        engine = TesseractEngine()
        if not engine.is_available():
            pytest.skip("Real Tesseract engine not available on this machine.")

        version = engine.get_version()
        assert version is not None
        assert len(version) > 0

        # Create a small synthetic image with simple text
        img = Image.new("RGB", (200, 60), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 20), "FINANCE 2026", fill="black")

        langs = engine.get_available_languages()
        ocr_lang = "eng" if "eng" in langs else (langs[0] if langs else "eng")

        result = engine.ocr_image(img, lang=ocr_lang)
        assert isinstance(result, str)
