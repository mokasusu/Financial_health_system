"""Tầng hạ tầng (Infrastructure Layer).

Cung cấp các triển khai kỹ thuật cụ thể kết nối phần cứng, thư viện đồ họa và API bên ngoài:
- Trích xuất tài liệu PDF & hình ảnh: PDFExtractor (PyMuPDF + PaddleOCR).
- Tiền xử lý ảnh quang học: ImagePreprocessor (OpenCV).
- Động cơ nhận dạng OCR: PaddleOCREngine (PaddleOCR + PP-Structure).
- Máy khách trí tuệ nhân tạo: OpenRouterClient (OpenRouter AI Gateway).
- Nhà máy tiêm phụ thuộc: ServiceFactory (Dependency Injection Factory).
"""
from src.infrastructure.ai.client import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
    RateLimitError,
    ResponseValidationError,
    ServerError,
    redact_secret,
)
from src.infrastructure.factories import ServiceFactory
from src.infrastructure.ocr.paddle_engine import (
    PaddleOCREngine,
    PaddleOCREngineError,
    get_shared_paddle_engine,
    reset_shared_paddle_engine,
)
from src.infrastructure.ocr.preprocessor import ImagePreprocessor
from src.infrastructure.pdf.extractor import PDFExtractor

__all__ = [
    "ServiceFactory",
    "ImagePreprocessor",
    "PaddleOCREngine",
    "PaddleOCREngineError",
    "get_shared_paddle_engine",
    "reset_shared_paddle_engine",
    "PDFExtractor",
    "OpenRouterClient",
    "OpenRouterConfig",
    "OpenRouterError",
    "AuthenticationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "ConfigurationError",
    "ResponseValidationError",
    "redact_secret",
]
