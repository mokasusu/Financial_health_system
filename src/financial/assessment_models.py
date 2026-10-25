"""Data models for Financial Ratio Assessment and Warning Engine (Sprint 4B).

Provides structured Pydantic schemas representing rule-based ratio assessments,
prioritized financial risk warnings, category overviews, and overall health synthesis.
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.financial.ratios import RatioCategory


class AssessmentStatus(str, Enum):
    """Evaluation status for an individual financial ratio."""
    ADEQUATE = "adequate"                    # Không phát cảnh báo theo ngưỡng sàng lọc minh họa
    WATCH = "watch"                          # Cần theo dõi, nằm trong vùng đệm cảnh giác
    ALERT = "alert"                          # Cảnh báo rủi ro theo ngưỡng sàng lọc minh họa
    CALCULATED_NO_BENCHMARK = "no_benchmark" # Tính toán thành công nhưng cần benchmark ngành để kết luận
    NOT_AVAILABLE = "not_available"          # Thiếu số liệu đầu vào bắt buộc
    NOT_APPLICABLE = "not_applicable"        # Không áp dụng (ví dụ mẫu số bằng 0)
    UNDEFINED = "undefined"                  # Trạng thái không xác định / âm bất thường (ví dụ VCSH âm)


class WarningSeverity(str, Enum):
    """Severity priority levels for financial risk warnings."""
    INFO = "info"          # Thông tin ghi chú / hướng dẫn
    LOW = "low"            # Rủi ro thấp / lưu ý theo dõi
    MEDIUM = "medium"      # Rủi ro trung bình / cần rà soát
    HIGH = "high"          # Rủi ro cao / ảnh hưởng nghiêm trọng đến an toàn tài chính
    CRITICAL = "critical"  # Nguy cơ đặc biệt nghiêm trọng (ví dụ âm vốn CSH, lỗ lũy kế vượt vốn)


class WarningCategory(str, Enum):
    """Categorization of financial risk warnings."""
    LIQUIDITY = "liquidity"          # Rủi ro thanh toán ngắn hạn
    LEVERAGE = "leverage"            # Rủi ro đòn bẩy và cơ cấu nợ
    EFFICIENCY = "efficiency"        # Rủi ro hiệu quả sử dụng tài sản
    PROFITABILITY = "profitability"  # Rủi ro kết quả kinh doanh và khả năng sinh lời
    DATA_QUALITY = "data_quality"    # Vấn đề chất lượng dữ liệu BCTC
    GENERAL = "general"              # Cảnh báo tổng quát


class OverallHealthStatus(str, Enum):
    """High-level rule-based financial health synthesis status."""
    INSUFFICIENT_DATA = "insufficient_data"                    # Dữ liệu BCTC thiếu hụt đáng kể
    NEEDS_ATTENTION = "needs_attention"                        # Kích hoạt cảnh báo mức HIGH hoặc CRITICAL
    MIXED = "mixed"                                            # Tín hiệu đan xen, có chỉ số cần theo dõi
    NO_MAJOR_RULE_BASED_ALERTS = "no_major_rule_based_alerts"  # Không kích hoạt cảnh báo theo bộ quy tắc hiện tại


class RatioAssessment(BaseModel):
    """Structured rule-based assessment of a single financial ratio."""
    ratio_key: str = Field(description="Mã định danh tỷ số e.g. current_ratio")
    label: str = Field(description="Tên hiển thị tiếng Việt")
    category: RatioCategory = Field(description="Nhóm tỷ số tài chính")
    value: Optional[Decimal] = Field(default=None, description="Giá trị Decimal chính xác")
    formatted_value: str = Field(default="N/A", description="Giá trị hiển thị kèm đơn vị")
    status: AssessmentStatus = Field(description="Trạng thái đánh giá theo quy tắc")
    explanation: str = Field(description="Giải thích ngắn gọn có căn cứ từ dữ liệu tính toán")
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo kỹ thuật và nghiệp vụ")
    rule_id: Optional[str] = Field(default=None, description="Mã quy tắc đã áp dụng")
    limitations: List[str] = Field(default_factory=list, description="Hạn chế và lưu ý diễn giải")


class FinancialWarning(BaseModel):
    """A prioritized, actionable financial risk or data quality warning."""
    code: str = Field(description="Mã cảnh báo ổn định e.g. LIQUIDITY_LOW")
    category: WarningCategory = Field(description="Phân loại cảnh báo")
    severity: WarningSeverity = Field(description="Mức độ nghiêm trọng")
    title: str = Field(description="Tiêu đề cảnh báo ngắn gọn")
    message: str = Field(description="Nội dung cảnh báo chi tiết có căn cứ số liệu")
    related_ratios: List[str] = Field(default_factory=list, description="Danh sách ratio_key liên quan")
    evidence: str = Field(description="Bằng chứng số liệu làm cơ sở kích hoạt cảnh báo")
    recommendation: str = Field(description="Khuyến nghị hành động tiếp theo")


class FinancialAssessment(BaseModel):
    """Consolidated financial health assessment combining all evaluated ratios and synthesized alerts."""
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    as_of_date: Optional[str] = None
    period: Optional[str] = None
    currency: str = "VND"
    overall_status: OverallHealthStatus = Field(description="Đánh giá tổng quan mức rule-based")
    ratio_assessments: Dict[str, RatioAssessment] = Field(
        default_factory=dict, description="Đánh giá chi tiết 14 tỷ số theo ratio_key"
    )
    warnings: List[FinancialWarning] = Field(
        default_factory=list, description="Danh sách cảnh báo đã lọc trùng và sắp xếp theo mức độ ưu tiên"
    )
    category_overviews: Dict[str, str] = Field(
        default_factory=dict, description="Tóm tắt nhận định theo 4 nhóm: liquidity, leverage, efficiency, profitability"
    )
    key_findings: List[str] = Field(
        default_factory=list, description="Các phát hiện trọng yếu rút ra từ số liệu BCTC"
    )
    limitations: List[str] = Field(
        default_factory=list, description="Giới hạn phân tích và tuyên bố miễn trừ"
    )
    rule_set_version: str = Field(default="1.0", description="Phiên bản của bộ quy tắc sàng lọc")
    total_ratios_evaluated: int = 14
    calculated_count: int = 0
    alert_count: int = 0
    watch_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_assessment(self, ratio_key: str) -> Optional[RatioAssessment]:
        """Fetch evaluation for a specific ratio safely."""
        return self.ratio_assessments.get(ratio_key)
