"""Gói hạ tầng bóc tách tài liệu PDF (Infrastructure PDF Package).

Cung cấp bộ bóc tách PDFExtractor hỗ trợ kiến trúc 3 tuyến xử lý:
văn bản gốc (PyMuPDF), tài liệu scan (PaddleOCR), và tài liệu lai kết hợp (Hybrid Routing).
"""
from src.infrastructure.pdf.extractor import (
    FINANCIAL_NUMBER_PATTERN,
    IMAGE_EXTENSIONS,
    PDFExtractor,
)

__all__ = [
    "FINANCIAL_NUMBER_PATTERN",
    "IMAGE_EXTENSIONS",
    "PDFExtractor",
]
