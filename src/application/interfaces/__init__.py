"""Gói giao diện trừu tượng (Abstract Protocol Interfaces) của Tầng Application.

Triển khai nguyên lý Đảo ngược phụ thuộc (DIP) nhằm cô lập hoàn toàn tầng ứng dụng
khỏi các chi tiết công nghệ cụ thể trong tầng Infrastructure:
- IOCREngine: Giao thức cho động cơ nhận dạng ký tự quang học.
- IAIClient: Giao thức cho khách hàng giao tiếp mô hình AI / LLM.
- IDocumentExtractor: Giao thức cho bộ bóc tách tài liệu số hóa đa định dạng.
"""
from src.application.interfaces.ocr import IOCREngine
from src.application.interfaces.ai import IAIClient
from src.application.interfaces.pdf import IDocumentExtractor

__all__ = [
    "IOCREngine",
    "IAIClient",
    "IDocumentExtractor",
]
