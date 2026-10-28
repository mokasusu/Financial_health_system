"""Mô hình dữ liệu Đánh Giá Sức Khỏe Tài Chính và Phân Loại Cảnh Báo Rủi Ro.

Module này cung cấp các thực thể phục vụ việc đánh giá tỷ số theo bộ ngưỡng phân loại chuẩn mực:
- Trạng thái đánh giá từng chỉ số (AssessmentStatus: ADEQUATE, WATCH, ALERT...)
- Mức độ nghiêm trọng của cảnh báo (WarningSeverity: INFO, LOW, MEDIUM, HIGH, CRITICAL)
- Đánh giá tổng quan sức khỏe doanh nghiệp (OverallHealthStatus)
- Cảnh báo rủi ro có bằng chứng số liệu và khuyến nghị điều hành (FinancialWarning)
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.domain.models.ratios import RatioCategory


class AssessmentStatus(str, Enum):
    """Trạng thái đánh giá phân loại cho một chỉ số tài chính cá lẻ.

    Attributes:
        ADEQUATE: Chỉ số đạt mức an toàn theo ngưỡng tham chiếu.
        WATCH: Chỉ số nằm trong vùng đệm cần lưu tâm theo dõi.
        ALERT: Chỉ số rơi vào ngưỡng cảnh báo rủi ro tài chính.
        CALCULATED_NO_BENCHMARK: Tính toán thành công nhưng cần so sánh với bình quân ngành để kết luận.
        NOT_AVAILABLE: Không đủ số liệu đầu vào để đánh giá.
        NOT_APPLICABLE: Phép tính không áp dụng cho cấu trúc doanh nghiệp này (VD: mẫu số bằng 0).
        UNDEFINED: Trạng thái không xác định hoặc bất thường (VD: Vốn CSH âm).
    """
    ADEQUATE = "adequate"                    # Không phát cảnh báo theo ngưỡng sàng lọc minh họa
    WATCH = "watch"                          # Cần theo dõi, nằm trong vùng đệm cảnh giác
    ALERT = "alert"                          # Cảnh báo rủi ro theo ngưỡng sàng lọc minh họa
    CALCULATED_NO_BENCHMARK = "no_benchmark" # Tính toán thành công nhưng cần benchmark ngành để kết luận
    NOT_AVAILABLE = "not_available"          # Thiếu số liệu đầu vào bắt buộc
    NOT_APPLICABLE = "not_applicable"        # Không áp dụng (ví dụ mẫu số bằng 0)
    UNDEFINED = "undefined"                  # Trạng thái không xác định / âm bất thường


class WarningSeverity(str, Enum):
    """Mức độ ưu tiên và mức độ nghiêm trọng của cảnh báo rủi ro tài chính.

    Attributes:
        INFO: Mức thông tin ghi chú, hướng dẫn thêm.
        LOW: Rủi ro thấp, chỉ số lệch nhẹ khỏi mức thông thường.
        MEDIUM: Rủi ro trung bình, cần bộ phận tài chính rà soát.
        HIGH: Rủi ro cao, có thể ảnh hưởng đến khả năng hoạt động liên tục.
        CRITICAL: Nguy cơ mất thanh khoản nghiêm trọng hoặc mất vốn.
    """
    INFO = "info"          # Thông tin ghi chú / hướng dẫn
    LOW = "low"            # Rủi ro thấp / lưu ý theo dõi
    MEDIUM = "medium"      # Rủi ro trung bình / cần rà soát
    HIGH = "high"          # Rủi ro cao / ảnh hưởng nghiêm trọng đến an toàn tài chính
    CRITICAL = "critical"  # Nguy cơ đặc biệt nghiêm trọng


class WarningCategory(str, Enum):
    """Phân loại nhóm rủi ro tài chính.

    Attributes:
        LIQUIDITY: Rủi ro liên quan đến khả năng thanh toán nợ đến hạn.
        LEVERAGE: Rủi ro về đòn bẩy tài chính và áp lực nợ vay.
        EFFICIENCY: Rủi ro về ứ đọng vốn và hiệu quả vòng quay tài sản.
        PROFITABILITY: Rủi ro về suy giảm biên lợi nhuận hoặc thua lỗ.
        DATA_QUALITY: Vấn đề về tính nhất quán hoặc thiếu hụt dữ liệu BCTC.
        GENERAL: Các cảnh báo tổng thể khác.
    """
    LIQUIDITY = "liquidity"          # Rủi ro thanh toán ngắn hạn
    LEVERAGE = "leverage"            # Rủi ro đòn bẩy và cơ cấu nợ
    EFFICIENCY = "efficiency"        # Rủi ro hiệu quả sử dụng tài sản
    PROFITABILITY = "profitability"  # Rủi ro kết quả kinh doanh và khả năng sinh lời
    DATA_QUALITY = "data_quality"    # Vấn đề chất lượng dữ liệu BCTC
    GENERAL = "general"              # Cảnh báo tổng quát


class OverallHealthStatus(str, Enum):
    """Trạng thái tổng hợp sức khỏe tài chính doanh nghiệp cấp độ quy tắc (Rule-Based).

    Attributes:
        INSUFFICIENT_DATA: Báo cáo thiếu quá nhiều chỉ tiêu trọng yếu, không đủ dữ liệu kết luận.
        NEEDS_ATTENTION: Kích hoạt ít nhất một cảnh báo mức độ HIGH hoặc CRITICAL.
        MIXED: Có tín hiệu đan xen giữa các nhóm, có chỉ số tốt và có chỉ số cần theo dõi.
        NO_MAJOR_RULE_BASED_ALERTS: Các chỉ số đều nằm trong ngưỡng an toàn theo quy tắc.
    """
    INSUFFICIENT_DATA = "insufficient_data"                    # Dữ liệu BCTC thiếu hụt đáng kể
    NEEDS_ATTENTION = "needs_attention"                        # Kích hoạt cảnh báo mức HIGH hoặc CRITICAL
    MIXED = "mixed"                                            # Tín hiệu đan xen, có chỉ số cần theo dõi
    NO_MAJOR_RULE_BASED_ALERTS = "no_major_rule_based_alerts"  # Không kích hoạt cảnh báo theo bộ quy tắc hiện tại


class RatioAssessment(BaseModel):
    """Đánh giá chi tiết một tỷ số tài chính đơn lẻ theo ngưỡng phân loại.

    Attributes:
        ratio_key (str): Khóa định danh của chỉ số (VD: 'current_ratio', 'gross_profit_margin').
        label (str): Tên tiếng Việt hiển thị của chỉ số.
        category (RatioCategory): Phân loại nhóm tỷ số.
        value (Optional[Decimal]): Giá trị Decimal chính xác của chỉ số.
        formatted_value (str): Chuỗi định dạng hiển thị kèm đơn vị.
        status (AssessmentStatus): Kết quả phân loại (ADEQUATE, WATCH, ALERT...).
        explanation (str): Giải thích ngắn gọn có căn cứ số liệu tính toán.
        warnings (List[str]): Cảnh báo nghiệp vụ và lưu ý kinh tế.
        rule_id (Optional[str]): Mã quy tắc sàng lọc đã áp dụng.
        limitations (List[str]): Hạn chế phân tích khi không có số liệu ngành đối chiếu.
    """
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
    """Mô hình cảnh báo rủi ro tài chính có căn cứ số liệu và khuyến nghị hành động.

    Attributes:
        code (str): Mã cảnh báo ổn định (VD: 'LIQUIDITY_LOW', 'HIGH_LEVERAGE').
        category (WarningCategory): Phân loại nhóm cảnh báo.
        severity (WarningSeverity): Mức độ ưu tiên/nghiêm trọng.
        title (str): Tiêu đề ngắn gọn của cảnh báo.
        message (str): Nội dung diễn giải rủi ro chi tiết.
        related_ratios (List[str]): Danh sách các tỷ số tài chính liên quan.
        evidence (str): Bằng chứng số liệu kế toán kích hoạt cảnh báo này.
        recommendation (str): Đề xuất biện pháp khắc phục hoặc kiểm soát rủi ro.
    """
    code: str = Field(description="Mã cảnh báo ổn định e.g. LIQUIDITY_LOW")
    category: WarningCategory = Field(description="Phân loại cảnh báo")
    severity: WarningSeverity = Field(description="Mức độ nghiêm trọng")
    title: str = Field(description="Tiêu đề cảnh báo ngắn gọn")
    message: str = Field(description="Nội dung cảnh báo chi tiết có căn cứ số liệu")
    related_ratios: List[str] = Field(default_factory=list, description="Danh sách ratio_key liên quan")
    evidence: str = Field(description="Bằng chứng số liệu làm cơ sở kích hoạt cảnh báo")
    recommendation: str = Field(description="Khuyến nghị hành động tiếp theo")


class FinancialAssessment(BaseModel):
    """Báo cáo đánh giá tổng hợp sức khỏe tài chính doanh nghiệp.

    Hợp nhất toàn bộ kết quả phân loại 14 chỉ số, danh sách cảnh báo có thứ tự ưu tiên,
    nhận định tổng quan theo 4 nhóm và các lưu ý giới hạn phân tích.
    """
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
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata phiên đánh giá")

    def get_assessment(self, ratio_key: str) -> Optional[RatioAssessment]:
        """Truy xuất kết quả đánh giá phân loại của một chỉ số theo ratio_key.

        Args:
            ratio_key (str): Khóa định danh của chỉ số (VD: 'quick_ratio').

        Returns:
            Optional[RatioAssessment]: Đối tượng đánh giá chi tiết hoặc None.
        """
        return self.ratio_assessments.get(ratio_key)
