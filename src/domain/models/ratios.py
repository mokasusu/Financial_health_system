"""Mô hình dữ liệu các Tỷ số tài chính (Financial Ratios) và Báo cáo phân tích tỷ số.

Module này cung cấp các cấu trúc dữ liệu chuẩn hóa đại diện cho 14 chỉ số tài chính,
phân loại theo 4 nhóm chuẩn phân tích tài chính doanh nghiệp:
1. Nhóm thanh khoản (Liquidity)
2. Nhóm đòn bẩy / cơ cấu vốn (Leverage)
3. Nhóm hiệu quả hoạt động (Efficiency)
4. Nhóm khả năng sinh lời (Profitability)
Toàn bộ giá trị tỷ số được lưu giữ bằng kiểu dữ liệu Decimal chính xác tuyệt đối.
"""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RatioCategory(str, Enum):
    """Phân loại 4 nhóm chỉ số phân tích tài chính chuẩn mực.

    Attributes:
        LIQUIDITY: Nhóm chỉ số khả năng thanh toán / thanh khoản.
        LEVERAGE: Nhóm chỉ số cơ cấu vốn và đòn bẩy tài chính.
        EFFICIENCY: Nhóm chỉ số hiệu quả hoạt động và quản lý tài sản.
        PROFITABILITY: Nhóm chỉ số năng lực sinh lời của doanh nghiệp.
    """
    LIQUIDITY = "liquidity"          # Nhóm thanh khoản
    LEVERAGE = "leverage"            # Nhóm cơ cấu vốn / Đòn bẩy
    EFFICIENCY = "efficiency"        # Nhóm hiệu quả hoạt động
    PROFITABILITY = "profitability"  # Nhóm sinh lời


class RatioStatus(str, Enum):
    """Trạng thái thực thi của một phép tính tỷ số tài chính.

    Attributes:
        CALCULATED: Tính toán thành công, kết quả có ý nghĩa kinh tế hợp lệ.
        NOT_AVAILABLE: Thiếu số liệu kế toán đầu vào bắt buộc từ BCTC.
        NOT_APPLICABLE: Mẫu số bằng 0 (ZeroDivision), không áp dụng tỷ số này.
        UNDEFINED: Kết quả bất thường về mặt kinh tế (ví dụ Vốn chủ sở hữu âm làm méo mó ROE).
    """
    CALCULATED = "calculated"        # Tính toán thành công, có ý nghĩa kinh tế hợp lệ
    NOT_AVAILABLE = "not_available"  # Thiếu số liệu đầu vào bắt buộc
    NOT_APPLICABLE = "not_applicable"# Mẫu số bằng 0 (ZeroDivision), không áp dụng
    UNDEFINED = "undefined"          # Kết quả âm bất thường / vốn chủ sở hữu âm


class RatioResult(BaseModel):
    """Kết quả tính toán của một chỉ số tài chính kèm dấu vết kiểm toán số liệu.

    Attributes:
        ratio_key (str): Khóa định danh duy nhất của chỉ số (VD: 'current_ratio', 'debt_to_equity').
        name (str): Tên tiếng Việt chính thức của chỉ số.
        category (RatioCategory): Phân loại nhóm tỷ số (liquidity, leverage, efficiency, profitability).
        value (Optional[Decimal]): Giá trị tính toán chính xác tuyệt đối bằng Decimal (không làm tròn số thực).
        unit (str): Đơn vị đo lường ('lần', '%', hoặc 'vòng').
        display_format (str): Mẫu chuỗi định dạng hiển thị cho người dùng.
        formatted_value (str): Chuỗi định dạng trực quan (VD: '1.85 lần', '15.20%').
        status (RatioStatus): Trạng thái tính toán (CALCULATED, NOT_AVAILABLE, NOT_APPLICABLE, UNDEFINED).
        formula (str): Công thức toán học và diễn giải kế toán.
        input_keys (List[str]): Danh sách mã chỉ tiêu kế toán tham gia vào công thức.
        inputs (Dict[str, Optional[Decimal]]): Giá trị thô của các chỉ tiêu đầu vào tương ứng.
        warnings (List[str]): Cảnh báo kiểm toán hoặc lưu ý phân tích kinh tế.
        description (str): Ý nghĩa tài chính và hướng dẫn nhà quản trị/đầu tư.
    """
    ratio_key: str = Field(description="Mã định danh duy nhất của chỉ số e.g. current_ratio")
    name: str = Field(description="Tên tiếng Việt hiển thị của chỉ số tài chính")
    category: RatioCategory = Field(description="Nhóm phân loại chỉ số")
    value: Optional[Decimal] = Field(default=None, description="Giá trị Decimal chính xác tuyệt đối không sai số làm tròn")
    unit: str = Field(default="lần", description="Đơn vị tính: 'lần', '%', hoặc 'vòng'")
    display_format: str = Field(default="{:.2f} lần", description="Mẫu định dạng chuỗi")
    formatted_value: str = Field(default="N/A", description="Chuỗi định dạng sẵn sàng hiển thị trên giao diện")
    status: RatioStatus = Field(default=RatioStatus.NOT_AVAILABLE, description="Trạng thái tính toán của chỉ số")
    formula: str = Field(description="Công thức toán học kế toán")
    input_keys: List[str] = Field(default_factory=list, description="Danh sách các khóa chỉ tiêu đầu vào được sử dụng")
    inputs: Dict[str, Optional[Decimal]] = Field(default_factory=dict, description="Các số liệu kế toán đầu vào cấu thành")
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo kiểm toán và giải thích bất thường")
    description: str = Field(default="", description="Ý nghĩa kinh tế và định hướng quản trị")


class FinancialRatioReport(BaseModel):
    """Báo cáo tổng hợp toàn bộ 14 chỉ số tài chính doanh nghiệp.

    Hợp nhất kết quả từ 4 nhóm phân tích, cung cấp thống kê số lượng chỉ số hợp lệ,
    các cảnh báo kiểm toán và các phương thức tra cứu chỉ số nhanh chóng.
    """
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    as_of_date: Optional[str] = None
    period: Optional[str] = None
    currency: str = "VND"
    ratios: Dict[str, RatioResult] = Field(
        default_factory=dict,
        description="Từ điển toàn bộ 14 chỉ số tài chính được đánh chỉ mục theo ratio_key"
    )
    categories: Dict[str, List[RatioResult]] = Field(
        default_factory=dict,
        description="Danh sách các chỉ số được gom nhóm theo chuỗi phân loại ('liquidity', 'leverage', 'efficiency', 'profitability')"
    )
    total_ratios: int = 0
    calculated_ratios: int = 0
    not_available_ratios: int = 0
    undefined_ratios: int = 0
    summary: str = Field(default="", description="Đoạn văn tóm tắt kết quả tính toán 14 chỉ số")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata môi trường phân tích")
    calculation_warnings: List[str] = Field(
        default_factory=list,
        description="Danh sách cảnh báo toàn cục trong quá trình tính toán"
    )

    def get_ratio(self, ratio_key: str) -> Optional[RatioResult]:
        """Truy xuất an toàn một đối tượng kết quả chỉ số theo mã ratio_key.

        Args:
            ratio_key (str): Khóa định danh của chỉ số (VD: 'current_ratio', 'roe').

        Returns:
            Optional[RatioResult]: Kết quả tính toán chỉ số tương ứng hoặc None nếu không tồn tại.
        """
        return self.ratios.get(ratio_key)
