"""Giao diện trừu tượng (Protocol) cho các động cơ nhận dạng ký tự quang học (OCR Engine).

Cho phép hệ thống linh hoạt chuyển đổi giữa các động cơ OCR khác nhau
(PaddleOCR GPU, PaddleOCR CPU, EasyOCR, Tesseract...) mà không làm thay đổi
bất kỳ logic nghiệp vụ nào trong tầng Application hay Domain.
"""
from pathlib import Path
from typing import Any, List, Optional, Protocol, Tuple, Union
import numpy as np
from PIL import Image

from src.domain.models.ocr import LayoutRegion


class IOCREngine(Protocol):
    """Giao thức định nghĩa các phương thức chuẩn cho một động cơ OCR."""

    def is_available(self) -> bool:
        """Kiểm tra môi trường runtime và trọng số mô hình OCR đã sẵn sàng hay chưa.

        Returns:
            bool: True nếu mô hình OCR đã được tải và sẵn sàng suy luận.
        """
        ...

    def ocr_image(
        self, image_input: Union[Path, str, np.ndarray, Image.Image]
    ) -> Tuple[List[str], List[float]]:
        """Thực hiện nhận dạng ký tự quang học cơ bản trên ảnh đầu vào.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh đầu vào dạng đường dẫn,
                mảng NumPy (OpenCV) hoặc đối tượng PIL Image.

        Returns:
            Tuple[List[str], List[float]]: (Danh sách các dòng văn bản nhận dạng được,
                Danh sách điểm tin cậy tương ứng từ 0.0 đến 1.0).
        """
        ...

    def ocr_image_detailed(
        self, image_input: Union[Path, str, np.ndarray, Image.Image]
    ) -> Tuple[List[str], List[float], List[Tuple[float, float, float, float]]]:
        """Thực hiện OCR chi tiết trả về văn bản, độ tin cậy và tọa độ khung bao.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh trang BCTC.

        Returns:
            Tuple[List[str], List[float], List[Tuple[float, float, float, float]]]:
                (Danh sách chuỗi ký tự, Danh sách độ tin cậy, Danh sách tọa độ bounding boxes x1, y1, x2, y2).
        """
        ...

    def analyze_layout(
        self, image_input: Union[Path, str, np.ndarray, Image.Image]
    ) -> List[LayoutRegion]:
        """Phân tích cấu trúc bố cục hình học (Layout Analysis) phát hiện bảng, tiêu đề, văn bản.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh trang BCTC.

        Returns:
            List[LayoutRegion]: Danh sách các vùng layout được phân loại.
        """
        ...

    def ocr_with_layout(
        self, image_input: Union[Path, str, np.ndarray, Image.Image]
    ) -> Tuple[List[str], List[float], List[LayoutRegion]]:
        """Kết hợp phân tích bố cục và nhận dạng ký tự có cấu trúc trên trang.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh trang BCTC.

        Returns:
            Tuple[List[str], List[float], List[LayoutRegion]]:
                (Danh sách dòng văn bản, Danh sách độ tin cậy, Danh sách vùng layout phát hiện).
        """
        ...

    def release_memory(self) -> None:
        """Giải phóng bộ nhớ VRAM của GPU và bộ đệm RAM sau khi kết thúc phiên phân tích."""
        ...
