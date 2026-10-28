"""Gói hạ tầng nhận dạng ký tự quang học (Infrastructure OCR Package).

Cung cấp động cơ nhận dạng PaddleOCREngine hỗ trợ PP-Structure và khử nhiễu layout,
cùng bộ tiền xử lý hình ảnh OpenCV ImagePreprocessor.
"""
from src.infrastructure.ocr.paddle_engine import (
    PaddleOCREngine,
    PaddleOCREngineError,
    get_shared_paddle_engine,
    reset_shared_paddle_engine,
)
from src.infrastructure.ocr.preprocessor import ImagePreprocessor

__all__ = [
    "PaddleOCREngine",
    "PaddleOCREngineError",
    "get_shared_paddle_engine",
    "reset_shared_paddle_engine",
    "ImagePreprocessor",
]
