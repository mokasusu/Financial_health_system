"""PDF and document extraction pipeline supporting native text, PaddleOCR, and hybrid routing."""
import io
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import cv2
import numpy as np
from PIL import Image
import pymupdf

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

from src.ocr.image_preprocessor import ImagePreprocessor
from src.ocr.models import (
    DocumentExtractionResult,
    ExtractionMethod,
    ExtractionStatus,
    LayoutRegion,
    PageExtractionResult,
)
from src.ocr.paddle_engine import PaddleOCREngine

logger = logging.getLogger(__name__)

# Supported standalone image extensions for direct OCR
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# Financial numeric pattern: Vietnamese period-separated integers or floating numbers (e.g. 150.000.000, 1.234, 50000)
FINANCIAL_NUMBER_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b|\b\d{4,}\b")


class PDFExtractor:
    """Production PDF and document text extractor.

    Architecture & Routing:
    - Route A: Native-text PDF via PyMuPDF vector extraction and block layout analysis.
    - Route B: Scanned PDF via PyMuPDF raster rendering and PaddleOCR pipeline.
    - Route C: Mixed-content PDF combining native text and region-level PaddleOCR
               with spatial deduplication and provenance preservation.

    PaddleOCR is the sole OCR engine. Tesseract has been completely removed from the production pipeline.
    """

    def __init__(
        self,
        paddle_engine: Optional[PaddleOCREngine] = None,
        preprocessor: Optional[ImagePreprocessor] = None,
        min_native_text_chars: int = 50,
        ocr_dpi: int = 200,
        default_lang: str = "vi",
        extract_tables: bool = False,
        enable_enhance: bool = True,
    ):
        """Initialize PDFExtractor.

        Args:
            paddle_engine: PaddleOCREngine instance. If None, uses shared singleton engine.
            preprocessor: ImagePreprocessor instance for scan preprocessing.
            min_native_text_chars: Minimum characters required to qualify a page as native text.
                                   Pages with fewer characters are considered scan/empty.
            ocr_dpi: Rendering DPI when rasterizing PDF pages for OCR (default 200 DPI for optimal speed/accuracy).
            default_lang: OCR language code (default 'vi').
            extract_tables: Whether to attempt raw table extraction with pdfplumber.
            enable_enhance: Whether to enable LAB CLAHE + unsharp masking preprocessing.
        """
        self.preprocessor = preprocessor or ImagePreprocessor(
            enable_denoise=False,
            enable_deskew=True,
            enable_binarize=False,
            enable_enhance=enable_enhance,
        )
        if paddle_engine is not None:
            self.paddle_engine = paddle_engine
        else:
            from src.ocr.paddle_engine import get_shared_paddle_engine

            self.paddle_engine = get_shared_paddle_engine(lang=default_lang)

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
                status=ExtractionStatus.FAILED,
                errors=[f"Corrupted or invalid PDF file: {exc}"],
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )
        except Exception as exc:
            logger.error("Failed to process document '%s': %s", doc_name, exc)
            return DocumentExtractionResult(
                source_name=doc_name,
                total_pages=0,
                success=False,
                status=ExtractionStatus.FAILED,
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

        if total_pages == 0:
            return DocumentExtractionResult(
                source_name=source_name,
                total_pages=0,
                pages=[],
                metadata=metadata,
                success=True,
                status=ExtractionStatus.EMPTY,
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )

        has_ocr_pages = False
        has_native_pages = False
        has_tables = False

        # Optional raw table extraction with pdfplumber (for native text pages)
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

                if page_result.extraction_method in (
                    ExtractionMethod.PADDLE_OCR.value,
                    ExtractionMethod.HYBRID.value,
                    ExtractionMethod.OCR.value,
                ):
                    has_ocr_pages = True
                if page_result.extraction_method in (
                    ExtractionMethod.NATIVE_TEXT.value,
                    ExtractionMethod.HYBRID.value,
                ):
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
                        status=ExtractionStatus.FAILED,
                        success=False,
                        error_details=str(page_exc),
                        warnings=[f"Extraction exception: {page_exc}"],
                    )
                )

        duration = round(time.perf_counter() - start_time, 3)
        overall_success = (len(doc_errors) == 0) and (total_pages > 0)

        # Derive document-level status
        if not overall_success or any(p.status == ExtractionStatus.FAILED for p in pages_result):
            doc_status = ExtractionStatus.FAILED if all(p.status == ExtractionStatus.FAILED for p in pages_result) else ExtractionStatus.PARTIAL
        elif all(p.status == ExtractionStatus.EMPTY for p in pages_result):
            doc_status = ExtractionStatus.EMPTY
        elif any(p.status == ExtractionStatus.PARTIAL for p in pages_result) or any(p.needs_review for p in pages_result):
            doc_status = ExtractionStatus.PARTIAL
        else:
            doc_status = ExtractionStatus.COMPLETE

        return DocumentExtractionResult(
            source_name=source_name,
            total_pages=total_pages,
            pages=pages_result,
            metadata=metadata,
            success=overall_success,
            status=doc_status,
            needs_review=any(p.needs_review for p in pages_result) or (doc_status == ExtractionStatus.PARTIAL),
            has_ocr_pages=has_ocr_pages,
            has_native_pages=has_native_pages,
            has_tables=has_tables,
            processing_time_seconds=duration,
            errors=doc_errors,
        )

    def _render_page_to_bgr(
        self,
        page: pymupdf.Page,
        clip: Optional[pymupdf.Rect] = None,
    ) -> np.ndarray:
        """Render page or clip rectangle to standardized BGR numpy array."""
        pix = page.get_pixmap(dpi=self.ocr_dpi, clip=clip)
        try:
            samples = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
            if pix.n == 4:
                return cv2.cvtColor(samples, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                return cv2.cvtColor(samples, cv2.COLOR_RGB2BGR)
            elif pix.n == 1:
                return cv2.cvtColor(samples, cv2.COLOR_GRAY2BGR)
            else:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        finally:
            del pix

    def _classify_page_routing(
        self,
        page: pymupdf.Page,
        native_text: str,
        text_blocks: List[Any],
        image_rects: List[pymupdf.Rect],
    ) -> Tuple[str, str]:
        """Classify page into one of three routes: 'native', 'scanned', or 'mixed'.

        Returns:
            Tuple of (route_name, diagnostic_reason)
        """
        char_count = len(native_text)
        printable_count = sum(1 for c in native_text if c.isprintable() or c in "\n\r\t")
        quality_ratio = printable_count / max(1, char_count)

        page_area = max(1.0, page.rect.width * page.rect.height)
        total_img_area = sum(r.width * r.height for r in image_rects)
        img_area_ratio = min(1.0, total_img_area / page_area)

        # Route B: Insufficient native text or garbled font encoding -> Route to PaddleOCR
        if char_count < self.min_native_text_chars or quality_ratio < 0.60:
            reason = (
                f"Scanned page: native text below threshold ({char_count} < {self.min_native_text_chars}) "
                f"or low quality ratio ({quality_ratio:.2f}); routed to PaddleOCR."
            )
            return "scanned", reason

        # Route C: Mixed content detection
        # Even if native text exceeds min_native_text_chars (e.g. headers, metadata, titles),
        # an embedded raster table or scanned region may contain critical financial content.
        financial_numbers = FINANCIAL_NUMBER_PATTERN.findall(native_text)
        num_financial_numbers = len(financial_numbers)

        has_significant_images = (img_area_ratio >= 0.10) or any(
            (r.height >= 70 and r.width >= 120) for r in image_rects
        )

        if has_significant_images:
            # Check 1: Native text lacks financial numbers despite having characters
            lacks_numbers = (num_financial_numbers < 3)

            # Check 2: Spatial coverage - an image occupies page area with no native text blocks overlapping it
            has_uncovered_image = False
            for ir in image_rects:
                if ir.height >= 70 and ir.width >= 120:
                    overlapping_blocks = [
                        b for b in text_blocks if pymupdf.Rect(b[:4]).intersects(ir)
                    ]
                    overlapping_chars = sum(len(b[4]) for b in overlapping_blocks)
                    if overlapping_chars < 30:
                        has_uncovered_image = True
                        break

            if lacks_numbers or has_uncovered_image:
                reason = (
                    f"Mixed content detected: native text present ({char_count} chars, {num_financial_numbers} numbers), "
                    f"but embedded image region ({img_area_ratio:.1%} page area) contains missing table/scanned content."
                )
                return "mixed", reason

        # Route A: Native text is complete, high quality, and covers the document page
        reason = (
            f"Native text extraction: sufficient content ({char_count} chars, {num_financial_numbers} numeric values) "
            f"with quality ratio {quality_ratio:.2f} and no missing scanned regions."
        )
        return "native", reason

    def _extract_single_page(
        self,
        page: pymupdf.Page,
        page_number: int,
        source_name: str,
    ) -> PageExtractionResult:
        """Extract text from a single page using 3-route architecture."""
        native_text = page.get_text("text").strip()

        # Extract native text blocks (block_type == 0 is text)
        raw_blocks = page.get_text("blocks")
        text_blocks = [b for b in raw_blocks if len(b) >= 7 and b[6] == 0 and b[4].strip()]

        # Collect embedded image rectangles
        image_rects: List[pymupdf.Rect] = []
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                rects = page.get_image_rects(xref)
                image_rects.extend(rects)
        except Exception as img_err:
            logger.debug("Page %d image inspection notice: %s", page_number, img_err)

        # Classify routing
        route, reason = self._classify_page_routing(
            page=page,
            native_text=native_text,
            text_blocks=text_blocks,
            image_rects=image_rects,
        )

        # Route A: Complete native text PDF
        if route == "native":
            return self._extract_route_native(
                page=page,
                page_number=page_number,
                source_name=source_name,
                native_text=native_text,
                text_blocks=text_blocks,
                reason=reason,
            )

        # Empty page with neither text nor raster content
        if route == "empty":
            return PageExtractionResult(
                source_name=source_name,
                page_number=page_number,
                text="",
                extraction_method=ExtractionMethod.EMPTY.value,
                status=ExtractionStatus.EMPTY,
                success=True,
                char_count=0,
                ocr_confidence=0.0,
                routing_reason=reason,
                warnings=["Page contains neither native text nor raster image."],
            )

        # Route B: Purely scanned PDF page
        if route == "scanned":
            return self._extract_route_scanned(
                page=page,
                page_number=page_number,
                source_name=source_name,
                native_text=native_text,
                reason=reason,
            )

        # Route C: Mixed text and scanned content
        return self._extract_route_mixed(
            page=page,
            page_number=page_number,
            source_name=source_name,
            native_text=native_text,
            text_blocks=text_blocks,
            image_rects=image_rects,
            reason=reason,
        )

    def _extract_route_native(
        self,
        page: pymupdf.Page,
        page_number: int,
        source_name: str,
        native_text: str,
        text_blocks: List[Any],
        reason: str,
    ) -> PageExtractionResult:
        """Route A: Extract text and layout regions from native PDF layer without OCR."""
        layout_regions: List[LayoutRegion] = []

        for b in text_blocks:
            x0, y0, x1, y1, b_text, b_no, _ = b[:7]
            clean_b = b_text.strip()
            if clean_b:
                layout_regions.append(
                    LayoutRegion(
                        region_type="text",
                        bbox=(int(x0), int(y0), int(x1), int(y1)),
                        confidence=1.0,
                        text=clean_b,
                        included=True,
                        source_method="pymupdf_native",
                        needs_review=False,
                    )
                )

        return PageExtractionResult(
            source_name=source_name,
            page_number=page_number,
            text=native_text,
            extraction_method=ExtractionMethod.NATIVE_TEXT.value,
            status=ExtractionStatus.COMPLETE,
            success=True,
            char_count=len(native_text),
            ocr_confidence=1.0,
            layout_regions=layout_regions,
            routing_reason=reason,
            needs_review=False,
        )

    def _extract_route_scanned(
        self,
        page: pymupdf.Page,
        page_number: int,
        source_name: str,
        native_text: str,
        reason: str,
    ) -> PageExtractionResult:
        """Route B: Render scanned page and execute PaddleOCR pipeline."""
        warnings: List[str] = []
        if native_text:
            warnings.append(
                f"Page had only {len(native_text)} native chars (below threshold {self.min_native_text_chars})."
            )

        # Graceful handling when PaddleOCR engine is unavailable
        if self.paddle_engine is None or not self.paddle_engine.is_available():
            if native_text:
                warnings.append("OCR engine unavailable; kept partial native text.")
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text=native_text,
                    extraction_method=ExtractionMethod.NATIVE_TEXT.value,
                    status=ExtractionStatus.PARTIAL,
                    success=True,
                    warnings=warnings,
                    routing_reason="OCR engine unavailable; fallback to partial native text.",
                    needs_review=True,
                )
            else:
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text="",
                    extraction_method=ExtractionMethod.EMPTY.value,
                    status=ExtractionStatus.EMPTY,
                    success=True,
                    warnings=warnings + ["Page has no text and OCR engine unavailable."],
                    routing_reason="OCR engine unavailable on empty/scanned page.",
                )

        try:
            page_bgr = self._render_page_to_bgr(page)
            preprocessed = self.preprocessor.preprocess(page_bgr)
            del page_bgr

            ocr_text, ocr_conf, layout_regions = self.paddle_engine.ocr_with_layout(preprocessed)

            if ocr_text:
                status = ExtractionStatus.COMPLETE if ocr_conf >= 0.60 else ExtractionStatus.PARTIAL
                needs_review = (ocr_conf < 0.60)
                if needs_review:
                    warnings.append(f"Low OCR confidence ({ocr_conf:.2f} < 0.60); marked for manual review.")

                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text=ocr_text,
                    extraction_method=ExtractionMethod.PADDLE_OCR.value,
                    status=status,
                    ocr_confidence=ocr_conf,
                    layout_regions=layout_regions,
                    success=True,
                    warnings=warnings,
                    char_count=len(ocr_text),
                    routing_reason=reason,
                    needs_review=needs_review,
                )
            else:
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text="",
                    extraction_method=ExtractionMethod.EMPTY.value,
                    status=ExtractionStatus.EMPTY,
                    ocr_confidence=0.0,
                    layout_regions=layout_regions,
                    success=True,
                    warnings=warnings + ["Page visually empty or OCR found no text."],
                    routing_reason=reason,
                )

        except Exception as ocr_err:
            logger.warning("OCR failed on page %d: %s", page_number, ocr_err)
            if native_text:
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text=native_text,
                    extraction_method=ExtractionMethod.NATIVE_TEXT.value,
                    status=ExtractionStatus.PARTIAL,
                    success=True,
                    warnings=warnings + [f"OCR execution failed: {ocr_err}; preserved native text."],
                    routing_reason="OCR crashed; retained native text.",
                    needs_review=True,
                    error_details=str(ocr_err),
                )
            else:
                return PageExtractionResult(
                    source_name=source_name,
                    page_number=page_number,
                    text="",
                    extraction_method=ExtractionMethod.FAILED.value,
                    status=ExtractionStatus.FAILED,
                    success=False,
                    warnings=warnings + [f"OCR execution failed: {ocr_err}"],
                    routing_reason="OCR execution failure on scanned page.",
                    error_details=str(ocr_err),
                )

    def _extract_route_mixed(
        self,
        page: pymupdf.Page,
        page_number: int,
        source_name: str,
        native_text: str,
        text_blocks: List[Any],
        image_rects: List[pymupdf.Rect],
        reason: str,
    ) -> PageExtractionResult:
        """Route C: Mixed text & scanned content with region-level OCR and deduplicating merge."""
        warnings: List[str] = [reason]

        # 1. Collect native text layout regions
        native_regions: List[LayoutRegion] = []
        for b in text_blocks:
            x0, y0, x1, y1, b_text, _, _ = b[:7]
            clean_b = b_text.strip()
            if clean_b:
                native_regions.append(
                    LayoutRegion(
                        region_type="text",
                        bbox=(int(x0), int(y0), int(x1), int(y1)),
                        confidence=1.0,
                        text=clean_b,
                        included=True,
                        source_method="pymupdf_native",
                    )
                )

        # If OCR engine is unavailable, gracefully return native text with warning
        if self.paddle_engine is None or not self.paddle_engine.is_available():
            warnings.append("PaddleOCR engine unavailable for mixed content; returned native text only.")
            return PageExtractionResult(
                source_name=source_name,
                page_number=page_number,
                text=native_text,
                extraction_method=ExtractionMethod.NATIVE_TEXT.value,
                status=ExtractionStatus.PARTIAL,
                success=True,
                warnings=warnings,
                routing_reason="OCR unavailable; fallback to native text.",
                needs_review=True,
                layout_regions=native_regions,
            )

        try:
            ocr_text_pieces: List[Tuple[float, str]] = []  # (y0, text)
            ocr_regions: List[LayoutRegion] = []
            ocr_confidences: List[float] = []

            # Determine whether to OCR specific image regions or render full page
            large_image_rects = [
                r for r in image_rects if r.height >= 50 and r.width >= 100
            ]

            if large_image_rects and len(large_image_rects) <= 4:
                # Region-level extraction on specific image clips
                scale = 72.0 / self.ocr_dpi
                for ir in large_image_rects:
                    clip_bgr = self._render_page_to_bgr(page, clip=ir)
                    preprocessed_clip = self.preprocessor.preprocess(clip_bgr)
                    del clip_bgr

                    c_text, c_conf, c_regs = self.paddle_engine.ocr_with_layout(preprocessed_clip)
                    if c_text.strip():
                        ocr_text_pieces.append((ir.y0, c_text))
                        ocr_confidences.append(c_conf)

                        for r in c_regs:
                            # Remap bounding box to page coordinate space
                            page_bbox = (
                                int(ir.x0 + r.bbox[0] * scale),
                                int(ir.y0 + r.bbox[1] * scale),
                                int(ir.x0 + r.bbox[2] * scale),
                                int(ir.y0 + r.bbox[3] * scale),
                            )
                            r.bbox = page_bbox
                            r.source_method = "paddle_ocr_region"
                            ocr_regions.append(r)
            else:
                # Page-level OCR when image rects span the full page or are complex
                page_bgr = self._render_page_to_bgr(page)
                preprocessed = self.preprocessor.preprocess(page_bgr)
                del page_bgr

                p_text, p_conf, p_regs = self.paddle_engine.ocr_with_layout(preprocessed)
                if p_text.strip():
                    scale = 72.0 / self.ocr_dpi
                    for r in p_regs:
                        r.source_method = "paddle_ocr_page"
                        ocr_regions.append(r)
                    ocr_text_pieces.append((page.rect.y0, p_text))
                    ocr_confidences.append(p_conf)

            # Deduplicate and merge native text + OCR content
            merged_text, merged_regions = self._deduplicate_and_merge(
                native_text=native_text,
                native_regions=native_regions,
                ocr_text_pieces=ocr_text_pieces,
                ocr_regions=ocr_regions,
            )

            avg_conf = (
                sum(ocr_confidences) / len(ocr_confidences)
                if ocr_confidences
                else 1.0
            )
            status = ExtractionStatus.COMPLETE if avg_conf >= 0.60 else ExtractionStatus.PARTIAL
            needs_review = (avg_conf < 0.60)
            if needs_review:
                warnings.append(f"Low OCR confidence ({avg_conf:.2f} < 0.60) in scanned region.")

            return PageExtractionResult(
                source_name=source_name,
                page_number=page_number,
                text=merged_text,
                extraction_method=ExtractionMethod.HYBRID.value,
                status=status,
                ocr_confidence=round(avg_conf, 3),
                layout_regions=merged_regions,
                success=True,
                warnings=warnings,
                char_count=len(merged_text),
                routing_reason=reason,
                needs_review=needs_review,
            )

        except Exception as ocr_err:
            logger.warning("OCR failed on mixed page %d: %s", page_number, ocr_err)
            return PageExtractionResult(
                source_name=source_name,
                page_number=page_number,
                text=native_text,
                extraction_method=ExtractionMethod.NATIVE_TEXT.value,
                status=ExtractionStatus.PARTIAL,
                success=True,
                warnings=warnings + [f"OCR execution failed on mixed page: {ocr_err}; preserved native text."],
                routing_reason="OCR execution failure on mixed page; retained native text.",
                needs_review=True,
                error_details=str(ocr_err),
                layout_regions=native_regions,
            )

    @staticmethod
    def _normalize_line_for_dedup(text: str) -> str:
        """Strip non-alphanumeric characters and lowercase for duplicate text detection."""
        return re.sub(r"[^\w\d]", "", text).lower()

    def _deduplicate_and_merge(
        self,
        native_text: str,
        native_regions: List[LayoutRegion],
        ocr_text_pieces: List[Tuple[float, str]],
        ocr_regions: List[LayoutRegion],
    ) -> Tuple[str, List[LayoutRegion]]:
        """Merge native text and OCR text with coordinate awareness and string deduplication.

        Prevents duplicate text while retaining numeric and tabular values from scanned regions.
        """
        # Collect normalized native lines
        native_lines = [l.strip() for l in native_text.splitlines() if l.strip()]
        native_normalized_set: Set[str] = {
            self._normalize_line_for_dedup(l)
            for l in native_lines
            if len(self._normalize_line_for_dedup(l)) >= 3
        }

        # Filter novel OCR lines
        novel_ocr_lines: List[str] = []
        for _, text_block in ocr_text_pieces:
            for line in text_block.splitlines():
                line = line.strip()
                if not line:
                    continue

                norm_line = self._normalize_line_for_dedup(line)
                if not norm_line:
                    continue

                # Check if exact normalized line already exists in native text
                if norm_line in native_normalized_set:
                    continue

                # Check if line is a close duplicate of an existing native line
                is_duplicate = False
                for nat_norm in native_normalized_set:
                    if len(norm_line) >= 8 and (norm_line in nat_norm or nat_norm in norm_line):
                        is_duplicate = True
                        break

                # Preserve financial numbers even if surrounding text is similar
                if is_duplicate:
                    fin_nums = FINANCIAL_NUMBER_PATTERN.findall(line)
                    if fin_nums and not any(all(fn in nat_l for fn in fin_nums) for nat_l in native_lines):
                        is_duplicate = False

                if not is_duplicate:
                    novel_ocr_lines.append(line)

        # Merge text preserving natural document structure:
        # Native text + OCR scanned table content
        if novel_ocr_lines:
            merged_text = native_text + "\n\n" + "\n".join(novel_ocr_lines)
        else:
            merged_text = native_text

        # Merge layout regions
        merged_regions = list(native_regions)
        for r in ocr_regions:
            # Check overlap with native regions
            r_norm = self._normalize_line_for_dedup(r.text)
            if r_norm not in native_normalized_set:
                merged_regions.append(r)

        return merged_text, merged_regions

    def _extract_standalone_image(
        self,
        image_input: Union[Path, str, bytes],
        source_name: str,
        start_time: float,
    ) -> DocumentExtractionResult:
        """Direct OCR extraction for a standalone image file."""
        logger.info("Processing standalone image '%s' via PaddleOCR pipeline...", source_name)
        try:
            if self.paddle_engine is None or not self.paddle_engine.is_available():
                return DocumentExtractionResult(
                    source_name=source_name,
                    total_pages=1,
                    pages=[
                        PageExtractionResult(
                            source_name=source_name,
                            page_number=1,
                            text="",
                            extraction_method=ExtractionMethod.FAILED.value,
                            status=ExtractionStatus.FAILED,
                            success=False,
                            warnings=["OCR engine is not available."],
                            error_details="PaddleOCR engine is unavailable or not configured.",
                        )
                    ],
                    success=False,
                    status=ExtractionStatus.FAILED,
                    errors=["OCR engine is not installed or configured."],
                    processing_time_seconds=round(time.perf_counter() - start_time, 3),
                )

            # Convert input to standardized BGR numpy array
            if isinstance(image_input, (bytes, bytearray)):
                nparr = np.frombuffer(image_input, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError("Could not decode image from provided bytes.")
            else:
                img = self.preprocessor.to_numpy(image_input)

            preprocessed = self.preprocessor.preprocess(img)
            ocr_text, ocr_conf, layout_regions = self.paddle_engine.ocr_with_layout(preprocessed)

            if ocr_text:
                status = ExtractionStatus.COMPLETE if ocr_conf >= 0.60 else ExtractionStatus.PARTIAL
                method = ExtractionMethod.PADDLE_OCR.value
            else:
                status = ExtractionStatus.EMPTY
                method = ExtractionMethod.EMPTY.value

            page_res = PageExtractionResult(
                source_name=source_name,
                page_number=1,
                text=ocr_text,
                extraction_method=method,
                status=status,
                ocr_confidence=ocr_conf,
                layout_regions=layout_regions,
                success=True,
                char_count=len(ocr_text),
                needs_review=(ocr_conf < 0.60 and bool(ocr_text)),
                routing_reason="Standalone image input processed via PaddleOCR pipeline.",
            )

            return DocumentExtractionResult(
                source_name=source_name,
                total_pages=1,
                pages=[page_res],
                success=True,
                status=status,
                has_ocr_pages=bool(ocr_text),
                processing_time_seconds=round(time.perf_counter() - start_time, 3),
            )
        except Exception as exc:
            logger.error("Failed to OCR standalone image '%s': %s", source_name, exc)
            return DocumentExtractionResult(
                source_name=source_name,
                total_pages=1,
                pages=[
                    PageExtractionResult(
                        source_name=source_name,
                        page_number=1,
                        text="",
                        extraction_method=ExtractionMethod.FAILED.value,
                        status=ExtractionStatus.FAILED,
                        success=False,
                        warnings=[f"Image OCR failure: {exc}"],
                        error_details=str(exc),
                    )
                ],
                success=False,
                status=ExtractionStatus.FAILED,
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
                        valid_tables = [t for t in extracted if t and len(t) >= 2]
                        if valid_tables:
                            tables_map[idx + 1] = valid_tables
            elif isinstance(file_input, (bytes, bytearray)):
                with pdfplumber.open(io.BytesIO(file_input)) as pdf:
                    for idx, page in enumerate(pdf.pages):
                        extracted = page.extract_tables()
                        valid_tables = [t for t in extracted if t and len(t) >= 2]
                        if valid_tables:
                            tables_map[idx + 1] = valid_tables
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
