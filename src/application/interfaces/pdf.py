"""Giao diện trừu tượng (Protocol) cho bộ trích xuất tài liệu BCTC đa định dạng.

Hỗ trợ tiếp nhận tệp dữ liệu trực tiếp trong bộ nhớ RAM (`io.BytesIO` hoặc `bytes`)
tuân thủ tuyệt đối nguyên tắc bảo mật quyền riêng tư không lưu trữ file (Zero File Retention).
"""
import io
from pathlib import Path
from typing import Optional, Protocol, Union

from src.domain.models.ocr import DocumentExtractionResult


class IDocumentExtractor(Protocol):
    """Giao thức chuẩn cho các bộ trích xuất tài liệu (PDF văn bản số, PDF scan dạng ảnh, file ảnh)."""

    def extract(
        self,
        file_input: Union[str, Path, bytes, io.BytesIO],
        source_name: Optional[str] = None,
        max_pages: Optional[int] = None,
        **kwargs,
    ) -> DocumentExtractionResult:
        """Trích xuất tài liệu đa trang thành kết quả DocumentExtractionResult có cấu trúc.

        Args:
            file_input (Union[str, Path, bytes, io.BytesIO]): Nguồn tài liệu BCTC
                (luồng stream RAM io.BytesIO, chuỗi byte, hoặc đường dẫn tệp).
            source_name (Optional[str]): Tên tệp hoặc định danh hiển thị của tài liệu.
            max_pages (Optional[int]): Giới hạn số lượng trang tối đa cần xử lý (None nếu xử lý hết).
            **kwargs: Các cờ tham số phụ trợ bổ sung.

        Returns:
            DocumentExtractionResult: Kết quả bóc tách tổng hợp chứa toàn bộ dữ liệu các trang,
                bảng biểu và các cảnh báo kiểm toán.
        """
        ...
