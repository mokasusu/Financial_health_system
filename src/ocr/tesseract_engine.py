"""Tesseract OCR Engine wrapper for Vietnamese financial documents."""
import io
import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional, Union
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

# Default standard installation path on Windows x64
DEFAULT_WINDOWS_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class TesseractEngineError(Exception):
    """Base exception for Tesseract engine errors."""
    pass


class TesseractNotFoundError(TesseractEngineError):
    """Raised when Tesseract executable is not found or cannot be executed."""
    pass


class TesseractLanguageError(TesseractEngineError):
    """Raised when a requested OCR language pack is not available."""
    pass


class TesseractExecutionError(TesseractEngineError):
    """Raised when Tesseract fails during image OCR execution."""
    pass


class TesseractEngine:
    """Wrapper around pytesseract with robust Windows path resolution and Vietnamese support."""

    def __init__(self, tesseract_cmd: Optional[str] = None):
        """Initialize TesseractEngine with resolution from environment or standard paths.

        Resolution order:
        1. Explicit parameter `tesseract_cmd`
        2. Environment variable `TESSERACT_CMD`
        3. Standard Windows location (`C:\\Program Files\\Tesseract-OCR\\tesseract.exe`)
        4. System PATH (`shutil.which('tesseract')`)
        """
        self.cmd_path = self._resolve_executable_path(tesseract_cmd)
        pytesseract.pytesseract.tesseract_cmd = str(self.cmd_path)
        logger.debug("Tesseract command path configured to: %s", self.cmd_path)

    @staticmethod
    def _resolve_executable_path(custom_path: Optional[str] = None) -> Path:
        """Resolve the Tesseract binary path safely across platforms."""
        if custom_path and Path(custom_path).is_file():
            return Path(custom_path)

        env_cmd = os.getenv("TESSERACT_CMD")
        if env_cmd and Path(env_cmd).is_file():
            return Path(env_cmd)

        if os.name == "nt" and Path(DEFAULT_WINDOWS_TESSERACT_PATH).is_file():
            return Path(DEFAULT_WINDOWS_TESSERACT_PATH)

        which_path = shutil.which("tesseract")
        if which_path:
            return Path(which_path)

        # Fallback to configured or default string for error traceability
        return Path(custom_path or env_cmd or DEFAULT_WINDOWS_TESSERACT_PATH)

    def is_available(self) -> bool:
        """Check if Tesseract binary is present and executable."""
        try:
            _ = pytesseract.get_tesseract_version()
            return True
        except (pytesseract.TesseractNotFoundError, Exception) as exc:
            logger.debug("Tesseract availability check failed: %s", exc)
            return False

    def get_version(self) -> str:
        """Retrieve Tesseract engine version string."""
        if not self.is_available():
            raise TesseractNotFoundError(
                f"Tesseract executable not found at '{self.cmd_path}'. "
                "Please install Tesseract or configure TESSERACT_CMD."
            )
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception as exc:
            raise TesseractExecutionError(f"Failed to query Tesseract version: {exc}") from exc

    def get_available_languages(self) -> List[str]:
        """List language models installed in Tesseract tessdata."""
        if not self.is_available():
            raise TesseractNotFoundError(f"Tesseract executable not found at '{self.cmd_path}'")
        try:
            langs = pytesseract.get_languages()
            return sorted(langs)
        except Exception as exc:
            logger.warning("Could not list Tesseract languages: %s", exc)
            return []

    def validate_languages(self, lang: str) -> None:
        """Validate whether the requested language tokens are installed.

        Format can be 'vie', 'eng', or combined 'vie+eng'.
        """
        available = self.get_available_languages()
        if not available:
            return  # Could not verify, continue with execution

        requested_langs = [l.strip() for l in lang.split("+") if l.strip()]
        missing = [l for l in requested_langs if l not in available]

        if len(missing) == len(requested_langs):
            raise TesseractLanguageError(
                f"None of the requested OCR languages '{lang}' are installed. "
                f"Available languages: {', '.join(available)}"
            )
        elif missing:
            logger.warning(
                "Some requested languages %s are missing from Tesseract. Available: %s",
                missing,
                available,
            )

    def ocr_image(
        self,
        image_input: Union[Image.Image, Path, str, bytes],
        lang: str = "vie+eng",
        config: str = "--psm 6",
    ) -> str:
        """Run OCR on an image input and return extracted raw text.

        Args:
            image_input: PIL Image, file path, or raw image bytes.
            lang: Language string (defaults to 'vie+eng').
            config: Additional Tesseract CLI parameters (defaults to '--psm 6' for block of text).

        Returns:
            Extracted text content.

        Raises:
            TesseractNotFoundError: If Tesseract executable is missing.
            TesseractLanguageError: If language packs are missing.
            TesseractExecutionError: If OCR processing fails.
        """
        if not self.is_available():
            raise TesseractNotFoundError(
                f"Tesseract is not available at '{self.cmd_path}'. "
                "Ensure Tesseract is installed and path is configured."
            )

        self.validate_languages(lang)

        pil_image: Optional[Image.Image] = None
        should_close_image = False

        try:
            if isinstance(image_input, Image.Image):
                pil_image = image_input
            elif isinstance(image_input, (str, Path)):
                img_path = Path(image_input)
                if not img_path.is_file():
                    raise FileNotFoundError(f"Image file does not exist: {img_path}")
                pil_image = Image.open(img_path)
                should_close_image = True
            elif isinstance(image_input, (bytes, bytearray)):
                pil_image = Image.open(io.BytesIO(image_input))
                should_close_image = True
            else:
                raise TypeError(f"Unsupported image input type: {type(image_input)}")

            logger.info("Executing Tesseract OCR on image (%dx%d) with lang='%s'", pil_image.width, pil_image.height, lang)
            text = pytesseract.image_to_string(pil_image, lang=lang, config=config)
            return text or ""

        except (TesseractNotFoundError, TesseractLanguageError, FileNotFoundError, TypeError):
            raise
        except pytesseract.TesseractError as exc:
            raise TesseractExecutionError(f"Tesseract processing error: {exc}") from exc
        except Exception as exc:
            raise TesseractExecutionError(f"Unexpected error during OCR: {exc}") from exc
        finally:
            if should_close_image and pil_image is not None:
                try:
                    pil_image.close()
                except Exception:
                    pass
