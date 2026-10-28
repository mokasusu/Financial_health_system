"""Tầng trình diễn người dùng (Presentation Layer).

Cung cấp bộ điều khiển Streamlit run_app, các tiện ích định dạng số liệu kế toán (formatters),
quản lý trạng thái phiên làm việc (state), hệ thống nhận diện giao diện Glassmorphism (styles),
và các thành phần kết xuất biểu bảng trực quan (components).
"""
from src.presentation.controller import get_available_sample_options, run_app
from src.presentation.formatters import (
    format_currency,
    format_difference,
    format_percentage,
    format_ratio_value,
)
from src.presentation.state import initialize_session_state, reset_analysis
from src.presentation.styles import (
    COLOR_PRIMARY_EMERALD,
    apply_custom_styles,
    get_overall_health_banner_html,
    get_severity_badge_html,
    get_status_badge_html,
)

__all__ = [
    "run_app",
    "get_available_sample_options",
    "format_currency",
    "format_difference",
    "format_percentage",
    "format_ratio_value",
    "initialize_session_state",
    "reset_analysis",
    "apply_custom_styles",
    "get_status_badge_html",
    "get_severity_badge_html",
    "get_overall_health_banner_html",
    "COLOR_PRIMARY_EMERALD",
]
