"""Gói thẩm định sức khỏe tài chính và phân loại rủi ro (Domain Assessment).

Cung cấp:
- FinancialHealthAssessor: Động cơ thẩm định quy tắc 14 chỉ số tài chính.
- DEFAULT_SCREENING_THRESHOLDS: Bảng ngưỡng sàng lọc rủi ro tham chiếu minh họa.
- STANDARD_DISCLAIMERS: Danh sách các tuyên bố miễn trừ trách nhiệm phân tích.
"""
from src.domain.assessment.thresholds import (
    DEFAULT_SCREENING_THRESHOLDS,
    STANDARD_DISCLAIMERS,
)
from src.domain.assessment.evaluator import FinancialHealthAssessor

__all__ = [
    "DEFAULT_SCREENING_THRESHOLDS",
    "STANDARD_DISCLAIMERS",
    "FinancialHealthAssessor",
]
