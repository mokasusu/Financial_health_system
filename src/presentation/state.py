"""Quản lý trạng thái phiên làm việc (Session State) cho ứng dụng Streamlit.

Module này cung cấp các hàm khởi tạo và đặt lại các biến lưu trữ trong bộ nhớ phiên
`st.session_state` giữa các lần chạy lại (rerun) của giao diện người dùng, duy trì kết quả
bóc tách BCTC, bảng biểu chỉnh sửa, tỷ số tài chính, đánh giá rủi ro và nhận định AI.
"""
import streamlit as st


def initialize_session_state() -> None:
    """Khởi tạo các biến trạng thái phiên làm việc nếu chưa tồn tại.

    Đảm bảo việc lưu trữ đệm các kết quả thực thi xuyên suốt các lượt tương tác của người dùng:
    - stage (str): Giai đoạn quy trình hiện tại ("idle", "extracted", "analyzed").
    - report (Optional[FinancialReport]): Mô hình báo cáo tài chính đã bóc tách.
    - df_bs (Optional[pd.DataFrame]): Bảng dữ liệu Bảng CĐKT hiển thị trên giao diện.
    - df_is (Optional[pd.DataFrame]): Bảng dữ liệu Báo cáo KQKD hiển thị trên giao diện.
    - ratio_report (Optional[FinancialRatioReport]): Kết quả tính toán 14 tỷ số.
    - assessment (Optional[FinancialAssessment]): Kết quả sàng lọc và cảnh báo rủi ro.
    - ai_output (Optional[AIInterpretationOutput]): Nhận định từ mô hình AI.
    - source_name (Optional[str]): Tên tệp tài liệu đang xử lý.
    - extraction_method (Optional[str]): Phương thức bóc tách đã áp dụng (Native / PaddleOCR / Hybrid).
    - is_analyzed (bool): Cờ đánh dấu đã phân tích xong.
    - ai_error (Optional[str]): Thông điệp lỗi AI nếu có.
    """
    if "stage" not in st.session_state:
        st.session_state.stage = "idle"
    if "report" not in st.session_state:
        st.session_state.report = None
    if "df_bs" not in st.session_state:
        st.session_state.df_bs = None
    if "df_is" not in st.session_state:
        st.session_state.df_is = None
    if "ratio_report" not in st.session_state:
        st.session_state.ratio_report = None
    if "assessment" not in st.session_state:
        st.session_state.assessment = None
    if "ai_output" not in st.session_state:
        st.session_state.ai_output = None
    if "source_name" not in st.session_state:
        st.session_state.source_name = None
    if "extraction_method" not in st.session_state:
        st.session_state.extraction_method = None
    if "is_analyzed" not in st.session_state:
        st.session_state.is_analyzed = False
    if "ai_error" not in st.session_state:
        st.session_state.ai_error = None


def reset_analysis() -> None:
    """Xóa bỏ an toàn các kết quả phân tích trong bộ nhớ phiên và chuyển về trạng thái ban đầu."""
    st.session_state.stage = "idle"
    st.session_state.report = None
    st.session_state.df_bs = None
    st.session_state.df_is = None
    st.session_state.ratio_report = None
    st.session_state.assessment = None
    st.session_state.ai_output = None
    st.session_state.source_name = None
    st.session_state.extraction_method = None
    st.session_state.is_analyzed = False
    st.session_state.ai_error = None
