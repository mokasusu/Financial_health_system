"""PDF and Document extraction pipeline supporting native text and Tesseract OCR fallback."""
import io
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from PIL import Image
import pymupdf

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

from src.ocr.models import DocumentExtractionResult, ExtractionMethod, PageExtractionResult
from src.ocr.tesseract_engine import TesseractEngine, TesseractEngineError

logger = logging.getLogger(__name__)

# Supported standalone image extensions for direct OCR
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}


class PDFExtractor:
    """Hybrid PDF and document text extractor.

    Features:
    - High-speed native text extraction via PyMuPDF.
    - Automatic scan/image page detection using configurable character threshold.
    - Page-by-page OCR fallback via Tesseract (vie + eng) without re-processing entire document.
    - Raw table extraction via pdfplumber when requested.
    - Direct single-image OCR support using the same pipeline.
    - Strict preservation of page order and extraction provenance.
    """

    def __init__(
        self,
        tesseract_engine: Optional[TesseractEngine] = None,
        min_native_text_chars: int = 50,
        ocr_dpi: int = 200,
        default_lang: str = "vie+eng",
        extract_tables: bool = False,
    ):
        """Initialize PDFExtractor.

        Args:
            tesseract_engine: TesseractEngine instance. If None, instantiates default engine.
            min_native_text_chars: Minimum characters required to qualify a page as native text.
                                   Pages with fewer characters are considered scan/empty.
            ocr_dpi: Rendering DPI when rasterizing PDF pages for OCR.
            default_lang: OCR language code (default 'vie+eng').
            extract_tables: Whether to attempt raw table extraction with pdfplumber.
        """
        self.tesseract_engine = tesseract_engine or TesseractEngine()
        self.min_native_text_chars = max(0, min_native_text_chars)
        self.ocr_dpi = max(72, ocr_dpi)
        self.default_lang = default_lang
        self.extract_tables = extract_tables

    def extract(
        self,
        file_input: Union[Path, str, bytes],
        source_name: Optional[str] = None,
    ) -> DocumentExtractionResult:
        """Extract text and metadata from a PDF file or standalone image.

        Args:
            file_input: File path (Path/str) or in-memory bytes of the document.
            source_name: Optional custom identifier for the document source.

        Returns:
            DocumentExtractionResult with page-level results and document metadata.

        Raises:
            FileNotFoundError: If the input path does not exist.
            ValueError: If input format is invalid or unsupported.
        """
        start_time = time.perf_counter()

        # Handle file path validation
        resolved_path: Optional[Path] = None
        if isinstance(file_input, (str, Path)):
            resolved_path = Path(file_input)
            if not resolved_path.is_file():
                raise FileNotFoundError(f"Document file does not exist: {resolved_path}")
            doc_name = source_name or resolved_path.name
            file_ext = resolved_path.suffix.lower()

            # Direct route for standalone image files
            if file_ext in IMAGE_EXTENSIONS:
                return self._extract_standalone_image(
                    resolved_path, source_name=doc_name, start_time=start_time
                )
        elif isinstance(file_input, (bytes, bytearray)):
            doc_name = source_name or "in_memory_document.pdf"
        else:
            raise TypeError(f"Unsupported file_input type: {type(file_input)}")

        # Process PDF document
        doc: Optional[pymupdf.Document] = None
        try:
            if resolved_path:
                doc = pymupdf.open(resolved_path)
            else:
                doc = pymupdf.open(stream=file_input, filetype="pdf")

            return self._process_pdf_document(
                doc=doc,
                source_name=doc_name,
                file_input=file_input,
                start_time=start_time,
            )
        except pymupdf.FileDataError as exc:
            logger.error("Corrupted or invalid PDF file '%s': %s", doc_name, exc)
            return DocumentExtractionResult(
                source_name=doc_name,
                total_pages=0,
                success=False,
                errors=[f"Corrupted or invalid PDF file: {exc}"],
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )
        except Exception as exc:
            logger.error("Failed to process document '%s': %s", doc_name, exc)
            return DocumentExtractionResult(
                source_name=doc_name,
                total_pages=0,
                success=False,
                errors=[f"Document processing failure: {exc}"],
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    def _process_pdf_document(
        self,
        doc: pymupdf.Document,
        source_name: str,
        file_input: Union[Path, str, bytes],
        start_time: float,
    ) -> DocumentExtractionResult:
        """Process all pages of an opened PyMuPDF Document."""
        total_pages = len(doc)
        metadata = self._extract_clean_metadata(doc)
        pages_result: List[PageExtractionResult] = []
        doc_errors: List[str] = []

        has_ocr_pages = False
        has_native_pages = False
        has_tables = False

        # Optional raw table extraction with pdfplumber
        plumber_tables_by_page: Dict[int, List[Any]] = {}
        if self.extract_tables and HAS_PDFPLUMBER:
            plumber_tables_by_page = self._extract_tables_with_pdfplumber(file_input)

        logger.info("Processing PDF '%s' with %d pages...", source_name, total_pages)

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]

            try:
                page_result = self._extract_single_page(
                    page=page,
                    page_number=page_num,
                    source_name=source_name,
                )

                # Attach raw tables if available for this page
                if page_num in plumber_tables_by_page:
                    page_result.tables = plumber_tables_by_page[page_num]
                    if page_result.tables:
                        has_tables = True

                if page_result.extraction_method == ExtractionMethod.OCR.value:
                    has_ocr_pages = True
                elif page_result.extraction_method == ExtractionMethod.NATIVE_TEXT.value:
                    has_native_pages = True

                pages_result.append(page_result)

            except Exception as page_exc:
                logger.error("Error extracting page %d of '%s': %s", page_num, source_name, page_exc)
                doc_errors.append(f"Page {page_num} extraction failed: {page_exc}")
                pages_result.append(
                    PageExtractionResult(
                        source_name=source_name,
                        page_number=page_num,
                        text="",
                        extraction_method=ExtractionMethod.FAILED.value,
                        success=False,
                        warnings=[f"Extraction exception: {page_exc}"],
                    )
                )

        duration = round(time.perf_counter() - start_time, 3)
        overall_success = (len(doc_errors) == 0) and (total_pages > 0)

        return DocumentExtractionResult(
            source_name=source_name,
            total_pages=total_pages,
            pages=pages_result,
            metadata=metadata,
            success=overall_success,
            has_ocr_pages=has_ocr_pages,
            has_native_pages=has_native_pages,
            has_tables=has_tables,
            processing_time_seconds=duration,
            errors=doc_errors,
        )

    def _extract_single_page(
        self,
        page: pymupdf.Page,
        page_number: int,
        source_name: str,
    ) -> PageExtractionResult:
        """Extract text from a single page using native text or OCR fallback."""
        native_text = page.get_text("text").strip()

        # Case 1: Page has sufficient native text
        if len(native_text) >= self.min_native_text_chars:
            return PageExtractionResult(
                source_name=source_name,
                page_number=page_number,
                text=native_text,
                extraction_method=ExtractionMethod.NATIVE_TEXT.value,
                success=True,
                char_count=len(native_text),
            )

        # Case 2: Insufficient or empty native text -> Attempt OCR on rendered page
        logger.debug(
            "Page %d of '%s' has %d native chars (threshold=%d). Falling back to OCR.",
            page_number,
            source_name,
            len(native_text),
            self.min_native_text_chars,
        )

        warnings: List[str] = []
        if native_text:
            warnings.append(
                f"Page had only {len(native_text)} native chars (below threshold {self.min_native_text_chars})"
            )

        if not self.tesseract_engine.is_available():
            # OCR is unavailable
            if native_text:
                warnings.append("OCR engine unavailable; kept partial native text.")
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text=native_text,
                    extraction_method=ExtractionMethod.NATIVE_TEXT.value,
                    success=True,
                    warnings=warnings,
                )
            else:
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text="",
                    extraction_method=ExtractionMethod.EMPTY.value,
                    success=True,
                    warnings=warnings + ["Page has no text and OCR engine is unavailable."],
                )

        # Render page to PIL image in-memory
        try:
            pix = page.get_pixmap(dpi=self.ocr_dpi)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            ocr_text = self.tesseract_engine.ocr_image(
                image_input=page_image,
                lang=self.default_lang,
            ).strip()

            if ocr_text:
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text=ocr_text,
                    extraction_method=ExtractionMethod.OCR.value,
                    success=True,
                    warnings=warnings,
                    char_count=len(ocr_text),
                )
            else:
                # Both native and OCR yielded no text
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text="",
                    extraction_method=ExtractionMethod.EMPTY.value,
                    success=True,
                    warnings=warnings + ["Page visually empty or OCR found no text."],
                )

        except TesseractEngineError as ocr_err:
            logger.warning("OCR failed on page %d: %s", page_number, ocr_err)
            return PageExtractionResult(
                source_name=source_name,
                page_number=page_number,
                text=native_text,  # Preserve whatever native text existed
                extraction_method=(
                    ExtractionMethod.NATIVE_TEXT.value if native_text else ExtractionMethod.FAILED.value
                ),
                success=bool(native_text),
                warnings=warnings + [f"OCR execution failed: {ocr_err}"],
            )

    def _extract_standalone_image(
        self,
        image_path: Path,
        source_name: str,
        start_time: float,
    ) -> DocumentExtractionResult:
        """Direct OCR extraction for a standalone image file."""
        logger.info("Processing standalone image '%s' via Tesseract OCR...", source_name)
        try:
            if not self.tesseract_engine.is_available():
                return DocumentExtractionResult(
                    source_name=source_name,
                    total_pages=1,
                    pages=[
                        PageExtractionResult(
                            source_name=source_name,
                            page_number=1,
                            text="",
                            extraction_method=ExtractionMethod.FAILED.value,
                            success=False,
                            warnings=["Tesseract OCR engine is not available."],
                        )
                    ],
                    success=False,
                    errors=["Tesseract OCR is not installed or configured."],
                    processing_time_seconds=round(time.perf_counter() - start_time, 3),
                )

            ocr_text = self.tesseract_engine.ocr_image(image_path, lang=self.default_lang).strip()
            method = ExtractionMethod.OCR.value if ocr_text else ExtractionMethod.EMPTY.value

            page_res = PageExtractionResult(
                source_name=source_name,
                page_number=1,
                text=ocr_text,
                extraction_method=method,
                success=True,
                char_count=len(ocr_text),
            )

            return DocumentExtractionResult(
                source_name=source_name,
                total_pages=1,
                pages=[page_res],
                success=True,
                has_ocr_pages=bool(ocr_text),
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )
        except Exception as exc:
            logger.error("Failed to OCR standalone image '%s': %s", source_name, exc)
            return DocumentExtractionResult(
                source_name=source_name,
                total_pages=1,
                success=False,
                errors=[f"Image OCR failure: {exc}"],
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )

    def _extract_tables_with_pdfplumber(
        self,
        file_input: Union[Path, str, bytes],
    ) -> Dict[int, List[List[List[Optional[str]]]]]:
        """Extract raw tables using pdfplumber without assuming full structural perfection."""
        tables_map: Dict[int, List[Any]] = {}
        if not HAS_PDFPLUMBER:
            return tables_map

        try:
            if isinstance(file_input, (str, Path)):
                with pdfplumber.open(str(file_input)) as pdf:
                    for idx, page in enumerate(pdf.pages):
                        extracted = page.extract_tables()
                        if extracted:
                            tables_map[idx + 1] = extracted
            elif isinstance(file_input, (bytes, bytearray)):
                with pdfplumber.open(io.BytesIO(file_input)) as pdf:
                    for idx, page in enumerate(pdf.pages):
                        extracted = page.extract_tables()
                        if extracted:
                            tables_map[idx + 1] = extracted
        except Exception as exc:
            logger.warning("pdfplumber table extraction encountered an issue: %s", exc)

        return tables_map

    @staticmethod
    def _extract_clean_metadata(doc: pymupdf.Document) -> Dict[str, Any]:
        """Extract and sanitize document metadata from PDF catalog."""
        raw_meta = doc.metadata or {}
        clean_meta = {}
        for k, v in raw_meta.items():
            if v and isinstance(v, str):
                clean_meta[k] = v.strip()
            elif v is not None:
                clean_meta[k] = v
        return clean_meta
