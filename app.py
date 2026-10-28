"""Điểm nhập cảnh chính của hệ thống Financial Health System (Application Entry Point).

Tệp khởi động tinh gọn (thin bootstrap) ủy quyền thực thi cho bộ điều khiển tầng trình diễn
(Presentation Layer Controller), đồng thời cung cấp hàm `execute_pipeline` đóng gói để
phục vụ kiểm thử tích hợp tự động và các kịch bản chạy dòng lệnh bên ngoài.
"""
from typing import Optional, Tuple
from dotenv import load_dotenv

# Tải cấu hình biến môi trường từ tệp .env (API keys, models, timeouts)
load_dotenv()

from src.infrastructure.factories import ServiceFactory
from src.presentation.controller import get_available_sample_options, run_app


def execute_pipeline(
    file_bytes: Optional[bytes],
    file_name: str,
    period: str = "current",
    enable_ai: bool = True,
) -> Tuple[Optional[object], Optional[object], Optional[object], Optional[str]]:
    """Thực thi đường ống phân tích tài chính toàn diện đầu-cuối (End-to-End Pipeline).

    Hàm này khởi tạo `AnalysisPipelineService` từ `ServiceFactory` và kích hoạt chuỗi xử lý:
    Bóc tách tài liệu -> Chuẩn hóa chỉ tiêu TT200 -> Kiểm định cân đối -> Tính 14 tỷ số -> Diễn giải AI.

    Args:
        file_bytes (Optional[bytes]): Dữ liệu nhị phân của tệp tài liệu trong bộ nhớ.
        file_name (str): Tên định danh tệp (ví dụ: 'bctc_2020.pdf').
        period (str): Kỳ phân tích ('current' hoặc 'previous').
        enable_ai (bool): Cho phép gọi mô hình AI để nhận định chuyên sâu (mặc định True).

    Returns:
        Tuple[Optional[object], Optional[object], Optional[object], Optional[str]]:
            Bộ 4 kết quả: (FinancialRatioReport, FinancialAssessment, AIInterpretationOutput, Phương thức trích xuất).
    """
    pipeline = ServiceFactory.create_pipeline_service()
    return pipeline.execute_pipeline(
        file_bytes=file_bytes,
        file_name=file_name,
        period=period,
        enable_ai=enable_ai,
    )


if __name__ == "__main__":
    # Khởi chạy giao diện người dùng Streamlit
    run_app()
