"""Data models and schemas for OCR and PDF extraction results."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    """Method used to extract text from a specific page or document."""
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    EMPTY = "empty"
    FAILED = "failed"


class PageExtractionResult(BaseModel):
    """Extraction result for a single document page."""
    source_name: str = Field(description="Name or identifier of source document")
    page_number: int = Field(ge=1, description="Page number, 1-indexed")
    text: str = Field(default="", description="Extracted text content")
    extraction_method: str = Field(
        default=ExtractionMethod.EMPTY.value,
        description="Method used for extraction (native_text, ocr, empty, failed)"
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings encountered during extraction")
    success: bool = Field(default=True, description="Whether page extraction was successful")
    char_count: int = Field(default=0, description="Number of characters extracted")
    tables: list[list[list[Optional[str]]]] = Field(
        default_factory=list,
        description="Raw tables extracted from page if table extraction was requested"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.char_count and self.text:
            self.char_count = len(self.text)


class DocumentExtractionResult(BaseModel):
    """Aggregated extraction result for an entire document."""
    source_name: str = Field(description="Name or file path of source document")
    total_pages: int = Field(ge=0, default=0, description="Total number of pages")
    pages: list[PageExtractionResult] = Field(
        default_factory=list,
        description="List of extracted pages preserving original page order"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata from PDF header")
    success: bool = Field(default=True, description="Overall document extraction status")
    has_ocr_pages: bool = Field(default=False, description="Whether any page required OCR")
    has_native_pages: bool = Field(default=False, description="Whether any page had native text")
    has_tables: bool = Field(default=False, description="Whether any table was extracted")
    processing_time_seconds: float = Field(default=0.0, description="Processing duration in seconds")
    errors: list[str] = Field(default_factory=list, description="List of document-level errors")

    @property
    def full_text(self) -> str:
        """Concatenate all page texts separated by page dividers."""
        return "\n\n".join(
            f"===== PAGE {p.page_number} =====\n{p.text}" for p in self.pages if p.text.strip()
        )
