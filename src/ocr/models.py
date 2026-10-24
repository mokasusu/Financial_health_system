"""Data models and schemas for OCR and PDF extraction results."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    """Method used to extract text from a specific page or document."""
    NATIVE_TEXT = "native_text"
    PADDLE_OCR = "paddle_ocr"
    HYBRID = "hybrid"
    OCR = "ocr"  # Maintained for backward compatibility with legacy payloads and older tests
    EMPTY = "empty"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    """Semantic status of page or document extraction.

    - COMPLETE: All requested content (text/tables) extracted successfully with high confidence.
    - PARTIAL: Content extracted but with warnings, low OCR confidence, or some failed pages/regions.
    - EMPTY: Document/page rendered or processed without errors, but contained no discernible text/tables.
    - FAILED: Document/page encountered an unrecoverable exception or error during processing.
    """
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"
    FAILED = "failed"


class LayoutRegion(BaseModel):
    """Một vùng layout được PP-Structure hoặc engine layout phát hiện trên trang.

    Preserves layout-level bounding box, content, and provenance without mixing financial ratio
    or downstream business calculation logic.
    """
    region_type: str = Field(description="Loại vùng: text, title, table, figure, header, footer, v.v.")
    bbox: tuple[int, int, int, int] = Field(description="(x1, y1, x2, y2) bounding box coordinates")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ tin cậy của vùng (0.0 - 1.0)")
    text: str = Field(default="", description="Text OCR (cho vùng text/title)")
    html: str = Field(default="", description="HTML representation (cho vùng table)")
    included: bool = Field(default=True, description="False nếu bị lọc bỏ (header, footer, figure, logo)")
    source_method: Optional[str] = Field(default=None, description="Phương pháp/engine phát hiện (pp_structure, fallback_crop, v.v.)")
    needs_review: bool = Field(default=False, description="Cờ đánh dấu vùng cần người dùng xem xét/kiểm tra lại")
    review_reason: Optional[str] = Field(default=None, description="Lý do đánh dấu cần kiểm tra (ví dụ: điểm tin cậy thấp, header chứa số liệu)")


class PageExtractionResult(BaseModel):
    """Extraction result for a single document page."""
    source_name: str = Field(description="Name or identifier of source document")
    page_number: int = Field(ge=1, description="Page number, 1-indexed")
    text: str = Field(default="", description="Extracted text content")
    extraction_method: str = Field(
        default=ExtractionMethod.EMPTY.value,
        description="Method used for extraction (native_text, paddle_ocr, ocr, empty, failed)"
    )
    status: ExtractionStatus = Field(
        default=ExtractionStatus.COMPLETE,
        description="Semantic extraction status: complete, partial, empty, failed"
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings encountered during extraction")
    success: bool = Field(default=True, description="Whether page extraction was successful (preserved for caller compatibility)")
    char_count: int = Field(default=0, description="Number of characters extracted")
    tables: list[list[list[Optional[str]]]] = Field(
        default_factory=list,
        description="Raw tables extracted from page if table extraction was requested"
    )
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ tin cậy OCR trung bình của trang (0.0 - 1.0)")
    layout_regions: list[LayoutRegion] = Field(default_factory=list, description="Danh sách các vùng layout phát hiện trên trang")
    routing_reason: Optional[str] = Field(default=None, description="Lý do định tuyến trang (native text threshold, scan fallback, v.v.)")
    needs_review: bool = Field(default=False, description="Cờ đánh dấu trang cần người dùng rà soát")
    error_details: Optional[str] = Field(default=None, description="Chi tiết lỗi nếu trích xuất trang thất bại")

    def model_post_init(self, __context: Any) -> None:
        # Populate char_count from text if not explicitly set
        if "char_count" not in self.model_fields_set and self.text:
            self.char_count = len(self.text)
        elif not self.char_count and self.text:
            self.char_count = len(self.text)

        # Infer status if not explicitly passed by caller
        if "status" not in self.model_fields_set:
            if not self.success or self.extraction_method == ExtractionMethod.FAILED.value:
                self.status = ExtractionStatus.FAILED
            elif self.extraction_method == ExtractionMethod.EMPTY.value or not self.text.strip():
                self.status = ExtractionStatus.EMPTY
            elif self.warnings or self.needs_review or (0.0 < self.ocr_confidence < 0.60):
                self.status = ExtractionStatus.PARTIAL
            else:
                self.status = ExtractionStatus.COMPLETE

        # Sync success with status if success was not explicitly customized
        if "success" not in self.model_fields_set:
            self.success = (self.status != ExtractionStatus.FAILED)

        # Default needs_review to True if status is PARTIAL and needs_review wasn't set
        if "needs_review" not in self.model_fields_set and self.status == ExtractionStatus.PARTIAL:
            self.needs_review = True


class DocumentExtractionResult(BaseModel):
    """Aggregated extraction result for an entire document."""
    source_name: str = Field(description="Name or file path of source document")
    total_pages: int = Field(ge=0, default=0, description="Total number of pages")
    pages: list[PageExtractionResult] = Field(
        default_factory=list,
        description="List of extracted pages preserving original page order"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata from PDF header")
    success: bool = Field(default=True, description="Overall document extraction status (preserved for caller compatibility)")
    status: ExtractionStatus = Field(
        default=ExtractionStatus.COMPLETE,
        description="Overall semantic status across all pages: complete, partial, empty, failed"
    )
    needs_review: bool = Field(default=False, description="Whether any page in document was flagged for review")
    has_ocr_pages: bool = Field(default=False, description="Whether any page required OCR")
    has_native_pages: bool = Field(default=False, description="Whether any page had native text")
    has_tables: bool = Field(default=False, description="Whether any table was extracted")
    processing_time_seconds: float = Field(default=0.0, description="Processing duration in seconds")
    errors: list[str] = Field(default_factory=list, description="List of document-level errors")

    def model_post_init(self, __context: Any) -> None:
        if "status" not in self.model_fields_set:
            if not self.success or (self.errors and len(self.errors) > 0 and self.total_pages == 0):
                self.status = ExtractionStatus.FAILED
            elif self.total_pages == 0 or (self.pages and all(p.status == ExtractionStatus.EMPTY for p in self.pages)):
                self.status = ExtractionStatus.EMPTY
            elif any(p.status in (ExtractionStatus.PARTIAL, ExtractionStatus.FAILED) for p in self.pages) or self.errors:
                self.status = ExtractionStatus.PARTIAL
            else:
                self.status = ExtractionStatus.COMPLETE

        if "success" not in self.model_fields_set:
            self.success = (self.status != ExtractionStatus.FAILED)

        if "needs_review" not in self.model_fields_set:
            self.needs_review = any(p.needs_review for p in self.pages) or (self.status == ExtractionStatus.PARTIAL)

    @property
    def full_text(self) -> str:
        """Concatenate all page texts separated by page dividers."""
        return "\n\n".join(
            f"===== PAGE {p.page_number} =====\n{p.text}" for p in self.pages if p.text.strip()
        )
