"""Đường ống bóc tách tài liệu PDF và hình ảnh hỗ trợ văn bản gốc, PaddleOCR và điều hướng lai (Hybrid Routing).

Module này triển khai lớp PDFExtractor theo kiến trúc 3 tuyến xử lý thông minh:
- Tuyến A (Route A - Native Text): Bóc tách lớp văn bản vector số hóa qua PyMuPDF với tốc độ mili-giây.
- Tuyến B (Route B - Scanned OCR): Kết xuất raster hình ảnh độ phân giải cao và gọi đường ống PaddleOCR.
- Tuyến C (Route C - Mixed Hybrid): Nhận diện các trang tài liệu hỗn hợp (chứa cả văn bản số hóa lẫn
  các biểu bảng dạng ảnh quét), thực hiện OCR vùng cục bộ, khử trùng lặp chuỗi và hợp nhất bảo toàn tọa độ.
"""
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

from src.infrastructure.ocr.preprocessor import ImagePreprocessor
from src.domain.models.ocr import (
    DocumentExtractionResult,
    ExtractionMethod,
    ExtractionStatus,
    LayoutRegion,
    PageExtractionResult,
)
from src.infrastructure.ocr.paddle_engine import PaddleOCREngine

logger = logging.getLogger(__name__)

# Các phần mở rộng tệp ảnh độc lập được hỗ trợ nhận diện OCR trực tiếp
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# Mẫu số tài chính Tiếng Việt: số nguyên phân cách bằng dấu chấm hoặc số thực (ví dụ: 150.000.000, 1.234, 50000)
FINANCIAL_NUMBER_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b|\b\d{4,}\b")


class PDFExtractor:
    """Bộ bóc tách văn bản và tài liệu PDF cấp sản xuất với kiến trúc phân luồng 3 tuyến.

    Kiến trúc điều hướng xử lý:
    - Tuyến A (Native): PDF dạng văn bản số hóa trích xuất trực tiếp qua PyMuPDF.
    - Tuyến B (Scanned): PDF scan hình ảnh kết xuất raster và nhận diện qua PaddleOCR.
    - Tuyến C (Mixed): PDF hỗn hợp kết hợp văn bản gốc và OCR vùng ảnh quét kèm khử trùng lặp.

    Attributes:
        preprocessor (ImagePreprocessor): Bộ tiền xử lý hình ảnh OpenCV.
        paddle_engine (PaddleOCREngine): Động cơ PaddleOCR.
        min_native_text_chars (int): Ngưỡng ký tự tối thiểu để phân loại là trang văn bản gốc.
        ocr_dpi (int): Độ phân giải DPI khi kết xuất raster trang PDF.
        default_lang (str): Mã ngôn ngữ OCR ('vi').
        extract_tables (bool): Tùy chọn trích xuất bảng bằng pdfplumber.
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
    ) -> None:
        """Khởi tạo bộ bóc tách tài liệu PDFExtractor.

        Args:
            paddle_engine (Optional[PaddleOCREngine]): Phiên bản PaddleOCREngine. Nếu None sẽ dùng singleton chung.
            preprocessor (Optional[ImagePreprocessor]): Phiên bản tiền xử lý ảnh OpenCV.
            min_native_text_chars (int): Số ký tự văn bản gốc tối thiểu để trang không bị coi là scan (mặc định 50).
            ocr_dpi (int): DPI khi chuyển đổi trang PDF sang ảnh raster (mặc định 200 DPI cân bằng tốc độ/độ chính xác).
            default_lang (str): Mã ngôn ngữ OCR (mặc định 'vi').
            extract_tables (bool): Cho phép bóc tách cấu trúc bảng bằng pdfplumber.
            enable_enhance (bool): Bật tiền xử lý CLAHE LAB và unsharp masking.
        """
        self.preprocessor: ImagePreprocessor = preprocessor or ImagePreprocessor(
            enable_denoise=False,
            enable_deskew=True,
            enable_binarize=False,
            enable_enhance=enable_enhance,
        )
        if paddle_engine is not None:
            self.paddle_engine: PaddleOCREngine = paddle_engine
        else:
            from src.infrastructure.ocr.paddle_engine import get_shared_paddle_engine

            self.paddle_engine = get_shared_paddle_engine(lang=default_lang)

        self.min_native_text_chars: int = max(0, min_native_text_chars)
        self.ocr_dpi: int = max(72, ocr_dpi)
        self.default_lang: str = default_lang
        self.extract_tables: bool = extract_tables

    def extract(
        self,
        file_input: Union[Path, str, bytes],
        source_name: Optional[str] = None,
    ) -> DocumentExtractionResult:
        """Trích xuất toàn diện văn bản và siêu dữ liệu từ tệp PDF hoặc ảnh độc lập.

        Args:
            file_input (Union[Path, str, bytes]): Đường dẫn tệp hoặc luồng byte trong bộ nhớ (Zero File Retention).
            source_name (Optional[str]): Tên định danh nguồn tài liệu (tùy chọn).

        Returns:
            DocumentExtractionResult: Kết quả bóc tách tổng thể gồm danh sách từng trang và siêu dữ liệu.

        Raises:
            FileNotFoundError: Khi đường dẫn tệp không tồn tại trên hệ thống.
            ValueError: Khi định dạng đầu vào không hợp lệ hoặc không thể giải mã.
            TypeError: Khi kiểu dữ liệu đầu vào không được hỗ trợ.
        """
        start_time: float = time.perf_counter()

        # Kiểm tra và xử lý đường dẫn tệp
        resolved_path: Optional[Path] = None
        if isinstance(file_input, (str, Path)):
            resolved_path = Path(file_input)
            if not resolved_path.is_file():
                raise FileNotFoundError(f"Document file does not exist: {resolved_path}")
            doc_name = source_name or resolved_path.name
            file_ext = resolved_path.suffix.lower()

            # Nhận diện tuyến xử lý trực tiếp cho tệp ảnh độc lập
            if file_ext in IMAGE_EXTENSIONS:
                return self._extract_standalone_image(
                    resolved_path, source_name=doc_name, start_time=start_time
                )
        elif isinstance(file_input, (bytes, bytearray)):
            doc_name = source_name or "in_memory_document.pdf"
        else:
            raise TypeError(f"Unsupported file_input type: {type(file_input)}")

        # Xử lý tài liệu PDF
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
        """Xử lý tuần tự tất cả các trang của tài liệu PyMuPDF đang mở.

        Args:
            doc (pymupdf.Document): Đối tượng tài liệu PDF.
            source_name (str): Tên nguồn tài liệu.
            file_input (Union[Path, str, bytes]): Đầu vào gốc (phục vụ pdfplumber).
            start_time (float): Thời điểm bắt đầu xử lý đo hiệu năng.

        Returns:
            DocumentExtractionResult: Kết quả bóc tách hợp nhất toàn bộ tài liệu.
        """
        total_pages: int = len(doc)
        metadata: Dict[str, Any] = self._extract_clean_metadata(doc)
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

        has_ocr_pages: bool = False
        has_native_pages: bool = False
        has_tables: bool = False

        # Tùy chọn trích xuất bảng thô bằng pdfplumber (cho trang văn bản số hóa)
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

                # Gán bảng cấu trúc nếu trang này có kết quả từ pdfplumber
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

        # Suy luận trạng thái cấp tài liệu
        if not overall_success or any(p.status == ExtractionStatus.FAILED for p in pages_result):
            doc_status = (
                ExtractionStatus.FAILED
                if all(p.status == ExtractionStatus.FAILED for p in pages_result)
                else ExtractionStatus.PARTIAL
            )
        elif all(p.status == ExtractionStatus.EMPTY for p in pages_result):
            doc_status = ExtractionStatus.EMPTY
        elif any(p.status == ExtractionStatus.PARTIAL for p in pages_result) or any(
            p.needs_review for p in pages_result
        ):
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
        """Kết xuất raster một trang PDF hoặc một khung hình chữ nhật thành mảng numpy BGR.

        Args:
            page (pymupdf.Page): Trang tài liệu PyMuPDF.
            clip (Optional[pymupdf.Rect]): Khung cắt hình chữ nhật tùy chọn.

        Returns:
            np.ndarray: Mảng ảnh BGR chuẩn mực sẵn sàng cho OpenCV/PaddleOCR.
        """
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
        """Phân loại trang tài liệu vào một trong ba tuyến xử lý: 'native', 'scanned', hoặc 'mixed'.

        Args:
            page (pymupdf.Page): Trang tài liệu.
            native_text (str): Toàn bộ văn bản số hóa trích xuất được.
            text_blocks (List[Any]): Các khối văn bản dạng vector.
            image_rects (List[pymupdf.Rect]): Danh sách khung ảnh nhúng trong trang.

        Returns:
            Tuple[str, str]: (Tên tuyến xử lý: 'native' | 'scanned' | 'mixed', Lý do chẩn đoán).
        """
        char_count = len(native_text)
        printable_count = sum(1 for c in native_text if c.isprintable() or c in "\n\r\t")
        quality_ratio = printable_count / max(1, char_count)

        page_area = max(1.0, page.rect.width * page.rect.height)
        total_img_area = sum(r.width * r.height for r in image_rects)
        img_area_ratio = min(1.0, total_img_area / page_area)

        # Tuyến B (Scanned): Không đủ ký tự văn bản hoặc mã hóa phông chữ bị lỗi mờ
        if char_count < self.min_native_text_chars or quality_ratio < 0.60:
            reason = (
                f"Scanned page: native text below threshold ({char_count} < {self.min_native_text_chars}) "
                f"or low quality ratio ({quality_ratio:.2f}); routed to PaddleOCR."
            )
            return "scanned", reason

        # Tuyến C (Mixed): Phát hiện nội dung hỗn hợp
        # Ngay cả khi số ký tự vượt ngưỡng, ảnh nhúng có thể là biểu bảng tài chính scan quan trọng
        financial_numbers = FINANCIAL_NUMBER_PATTERN.findall(native_text)
        num_financial_numbers = len(financial_numbers)

        has_significant_images = (img_area_ratio >= 0.10) or any(
            (r.height >= 70 and r.width >= 120) for r in image_rects
        )

        if has_significant_images:
            # Kiểm tra 1: Văn bản số hóa thiếu các con số tài chính
            lacks_numbers = (num_financial_numbers < 3)

            # Kiểm tra 2: Vùng ảnh chiếm diện tích lớn nhưng không có khối chữ số hóa nào đè lên
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

        # Tuyến A (Native): Văn bản gốc đầy đủ, chất lượng cao, bao phủ trọn vẹn trang
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
        """Bóc tách văn bản của một trang tài liệu theo kiến trúc điều hướng 3 tuyến.

        Args:
            page (pymupdf.Page): Trang tài liệu.
            page_number (int): Số thứ tự trang.
            source_name (str): Tên nguồn tài liệu.

        Returns:
            PageExtractionResult: Kết quả bóc tách chi tiết của trang.
        """
        native_text = page.get_text("text").strip()

        # Bóc tách các khối chữ số hóa (block_type == 0 là văn bản)
        raw_blocks = page.get_text("blocks")
        text_blocks = [b for b in raw_blocks if len(b) >= 7 and b[6] == 0 and b[4].strip()]

        # Thu thập tọa độ các hình ảnh nhúng trong trang
        image_rects: List[pymupdf.Rect] = []
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                rects = page.get_image_rects(xref)
                image_rects.extend(rects)
        except Exception as img_err:
            logger.debug("Page %d image inspection notice: %s", page_number, img_err)

        # Phân loại luồng xử lý trang
        route, reason = self._classify_page_routing(
            page=page,
            native_text=native_text,
            text_blocks=text_blocks,
            image_rects=image_rects,
        )

        # Tuyến A: PDF văn bản gốc hoàn toàn
        if route == "native":
            return self._extract_route_native(
                page=page,
                page_number=page_number,
                source_name=source_name,
                native_text=native_text,
                text_blocks=text_blocks,
                reason=reason,
            )

        # Trang trống không có chữ cũng không có ảnh
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

        # Tuyến B: Trang PDF scan hoàn toàn
        if route == "scanned":
            return self._extract_route_scanned(
                page=page,
                page_number=page_number,
                source_name=source_name,
                native_text=native_text,
                reason=reason,
            )

        # Tuyến C: Nội dung lai hỗn hợp văn bản và bảng scan
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
        """Tuyến A: Bóc tách văn bản và vùng bố cục trực tiếp từ lớp vector số hóa không cần OCR.

        Args:
            page (pymupdf.Page): Trang tài liệu.
            page_number (int): Số thứ tự trang.
            source_name (str): Tên nguồn tài liệu.
            native_text (str): Chuỗi văn bản số hóa.
            text_blocks (List[Any]): Danh sách khối văn bản PyMuPDF.
            reason (str): Lý do định tuyến.

        Returns:
            PageExtractionResult: Kết quả bóc tách với phương pháp NATIVE_TEXT và độ tin cậy 1.0.
        """
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
        """Tuyến B: Kết xuất raster trang scan và gọi đường ống nhận diện PaddleOCR.

        Args:
            page (pymupdf.Page): Trang tài liệu.
            page_number (int): Số thứ tự trang.
            source_name (str): Tên nguồn tài liệu.
            native_text (str): Văn bản gốc sót lại nếu có.
            reason (str): Lý do điều hướng.

        Returns:
            PageExtractionResult: Kết quả bóc tách với phương pháp PADDLE_OCR.
        """
        warnings: List[str] = []
        if native_text:
            warnings.append(
                f"Page had only {len(native_text)} native chars (below threshold {self.min_native_text_chars})."
            )

        # Xử lý an toàn khi động cơ OCR chưa được cài đặt hoặc không khả dụng
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
        """Tuyến C: Bóc tách tài liệu lai với OCR cấp vùng và thuật toán hợp nhất khử trùng lặp.

        Args:
            page (pymupdf.Page): Trang tài liệu.
            page_number (int): Số thứ tự trang.
            source_name (str): Tên nguồn tài liệu.
            native_text (str): Văn bản số hóa đã có.
            text_blocks (List[Any]): Khối chữ số hóa.
            image_rects (List[pymupdf.Rect]): Vùng hình ảnh nhúng.
            reason (str): Lý do điều hướng.

        Returns:
            PageExtractionResult: Kết quả bóc tách HYBRID kết hợp cả hai nguồn văn bản.
        """
        warnings: List[str] = [reason]

        # 1. Thu thập các vùng văn bản số hóa
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

        # Nếu không có động cơ OCR, trả về văn bản gốc kèm cảnh báo
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
            ocr_text_pieces: List[Tuple[float, str]] = []  # Cặp (y0, text)
            ocr_regions: List[LayoutRegion] = []
            ocr_confidences: List[float] = []

            # Xác định xem nên OCR từng vùng ảnh riêng lẻ hay toàn trang
            large_image_rects = [
                r for r in image_rects if r.height >= 50 and r.width >= 100
            ]

            if large_image_rects and len(large_image_rects) <= 4:
                # Bóc tách cấp vùng trên các khung ảnh cụ thể
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
                            # Ánh xạ lại tọa độ hộp bao về không gian tọa độ trang PDF
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
                # OCR toàn trang khi ảnh quét trải rộng toàn bộ tài liệu
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

            # Khử trùng lặp và hợp nhất văn bản số hóa + nội dung OCR
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
        """Loại bỏ ký tự không phải chữ số và chuyển chữ thường phục vụ so khớp trùng lặp.

        Args:
            text (str): Dòng văn bản thô.

        Returns:
            str: Chuỗi ký tự chỉ gồm chữ và số viết thường liền nhau.
        """
        return re.sub(r"[^\w\d]", "", text).lower()

    def _deduplicate_and_merge(
        self,
        native_text: str,
        native_regions: List[LayoutRegion],
        ocr_text_pieces: List[Tuple[float, str]],
        ocr_regions: List[LayoutRegion],
    ) -> Tuple[str, List[LayoutRegion]]:
        """Hợp nhất văn bản gốc và văn bản OCR có nhận thức không gian và khử trùng lặp chuỗi.

        Ngăn chặn hiện tượng lặp lại cùng một dòng văn bản trong khi vẫn bảo tồn trọn vẹn
        các chỉ số tài chính và bảng biểu từ phần scan.

        Args:
            native_text (str): Văn bản gốc số hóa.
            native_regions (List[LayoutRegion]): Vùng bố cục gốc.
            ocr_text_pieces (List[Tuple[float, str]]): Các đoạn văn bản OCR kèm tọa độ y0.
            ocr_regions (List[LayoutRegion]): Vùng bố cục OCR.

        Returns:
            Tuple[str, List[LayoutRegion]]: (Văn bản hợp nhất hoàn chỉnh, Danh sách vùng bố cục hợp nhất).
        """
        # Thu thập tập hợp các dòng văn bản gốc đã chuẩn hóa
        native_lines = [l.strip() for l in native_text.splitlines() if l.strip()]
        native_normalized_set: Set[str] = {
            self._normalize_line_for_dedup(l)
            for l in native_lines
            if len(self._normalize_line_for_dedup(l)) >= 3
        }

        # Lọc ra các dòng OCR mới chưa có trong văn bản gốc
        novel_ocr_lines: List[str] = []
        for _, text_block in ocr_text_pieces:
            for line in text_block.splitlines():
                line = line.strip()
                if not line:
                    continue

                norm_line = self._normalize_line_for_dedup(line)
                if not norm_line:
                    continue

                # Kiểm tra dòng đã tồn tại chính xác trong văn bản gốc chưa
                if norm_line in native_normalized_set:
                    continue

                # Kiểm tra dòng có phải là bản sao gần đúng của dòng gốc không
                is_duplicate = False
                for nat_norm in native_normalized_set:
                    if len(norm_line) >= 8 and (norm_line in nat_norm or nat_norm in norm_line):
                        is_duplicate = True
                        break

                # Luôn bảo lưu số liệu tài chính ngay cả khi văn bản mô tả xung quanh tương đồng
                if is_duplicate:
                    fin_nums = FINANCIAL_NUMBER_PATTERN.findall(line)
                    if fin_nums and not any(all(fn in nat_l for fn in fin_nums) for nat_l in native_lines):
                        is_duplicate = False

                if not is_duplicate:
                    novel_ocr_lines.append(line)

        # Hợp nhất văn bản bảo tồn cấu trúc tự nhiên: Văn bản gốc + Dòng bảng biểu OCR mới
        if novel_ocr_lines:
            merged_text = native_text + "\n\n" + "\n".join(novel_ocr_lines)
        else:
            merged_text = native_text

        # Hợp nhất các vùng bố cục
        merged_regions = list(native_regions)
        for r in ocr_regions:
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
        """Bóc tách văn bản trực tiếp từ tệp hình ảnh độc lập (.png, .jpg, v.v.).

        Args:
            image_input (Union[Path, str, bytes]): Đường dẫn hoặc dữ liệu byte của ảnh.
            source_name (str): Tên tệp ảnh nguồn.
            start_time (float): Thời điểm bắt đầu xử lý.

        Returns:
            DocumentExtractionResult: Kết quả bóc tách 1 trang cho ảnh độc lập.
        """
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

            # Chuyển đổi đầu vào sang mảng numpy BGR chuẩn hóa
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
        """Trích xuất bảng biểu thô bằng thư viện pdfplumber cho các trang PDF vector.

        Args:
            file_input (Union[Path, str, bytes]): Đầu vào tệp hoặc luồng byte.

        Returns:
            Dict[int, List[List[List[Optional[str]]]]]: Ánh xạ số trang -> danh sách các bảng ma trận ô.
        """
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
        """Bóc tách và chuẩn hóa siêu dữ liệu tài liệu từ danh mục PDF Catalog.

        Args:
            doc (pymupdf.Document): Đối tượng tài liệu PDF.

        Returns:
            Dict[str, Any]: Từ điển siêu dữ liệu sạch (tiêu đề, tác giả, ngày tạo, v.v.).
        """
        raw_meta = doc.metadata or {}
        clean_meta = {}
        for k, v in raw_meta.items():
            if v and isinstance(v, str):
                clean_meta[k] = v.strip()
            elif v is not None:
                clean_meta[k] = v
        return clean_meta
