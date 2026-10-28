"""Mô hình dữ liệu Báo cáo tài chính chuẩn hóa theo Thông tư 200/2014/TT-BTC.

Module này cung cấp các mô hình thực thể tổng hợp cho Báo cáo tài chính doanh nghiệp:
- Bảng cân đối kế toán (Mẫu B01-DN)
- Báo cáo kết quả hoạt động kinh doanh (Mẫu B02-DN)
- Báo cáo lưu chuyển tiền tệ (Mẫu B03-DN)
- Báo cáo kiểm định 4 đẳng thức cân đối kế toán (ValidationResult)
- Báo cáo tài chính tổng hợp đa kỳ (FinancialReport)
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.domain.models.line_item import AccountingStandard, CheckStatus, LineItem


class BalanceSheet(BaseModel):
    """Mô hình dữ liệu Bảng Cân Đối Kế Toán (Mẫu số B 01 - DN / Thông tư 200).

    Đại diện cho báo cáo tài chính phản ánh tổng quát toàn bộ giá trị tài sản
    hiện có và nguồn hình thành tài sản của doanh nghiệp tại một thời điểm nhất định.

    Attributes:
        statement_name (str): Tên báo cáo chính thức.
        as_of_date (Optional[str]): Ngày chốt số liệu kế toán (VD: '31/12/2020').
        currency (str): Đơn vị tiền tệ hạch toán (mặc định 'VND').
        current_period_name (Optional[str]): Nhãn hiển thị cột kỳ này (VD: '31/12/2020' hoặc 'Số cuối năm').
        previous_period_name (Optional[str]): Nhãn hiển thị cột kỳ trước (VD: '01/01/2020' hoặc 'Số đầu năm').
        items (Dict[str, LineItem]): Từ điển các chỉ tiêu chuẩn hóa đã ánh xạ, truy xuất theo canonical_key.
        unmapped_items (List[LineItem]): Danh sách các dòng chỉ tiêu thô chưa được ánh xạ vào chuẩn.
    """
    statement_name: str = "BẢNG CÂN ĐỐI KẾ TOÁN"
    as_of_date: Optional[str] = Field(default=None, description="Ngày khóa sổ/thời điểm lập BCTC e.g. 31/12/2020")
    currency: str = Field(default="VND", description="Đơn vị tiền tệ hạch toán")
    current_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ hiện tại e.g. 31/12/2020 hoặc Số cuối năm")
    previous_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ trước e.g. 01/01/2020 hoặc Số đầu năm")
    items: Dict[str, LineItem] = Field(
        default_factory=dict,
        description="Từ điển các chỉ tiêu kế toán chuẩn đã ánh xạ, đánh chỉ mục theo canonical_key"
    )
    unmapped_items: List[LineItem] = Field(
        default_factory=list,
        description="Các chỉ tiêu thô chưa thể ánh xạ tự động vào mã chuẩn"
    )

    def get_value(self, canonical_key: str, period: str = "current") -> Optional[Decimal]:
        """Truy xuất giá trị số học Decimal an toàn của một chỉ tiêu theo mã định danh chuẩn.

        Args:
            canonical_key (str): Khóa định danh chuẩn của hệ thống (VD: 'current_assets', 'total_assets').
            period (str): Kỳ kế toán cần lấy ('current' cho kỳ này, 'previous' cho kỳ trước).

        Returns:
            Optional[Decimal]: Giá trị số học kiểu Decimal hoặc None nếu chỉ tiêu không tồn tại.
        """
        item = self.items.get(canonical_key)
        if not item:
            return None
        return item.current_period_value if period == "current" else item.previous_period_value

    # Các thuộc tính tiện ích truy xuất nhanh chỉ tiêu trọng yếu Bảng cân đối kế toán
    @property
    def current_assets(self) -> Optional[Decimal]:
        """Tài sản ngắn hạn (Mã số 100)."""
        return self.get_value("current_assets")

    @property
    def cash_and_equivalents(self) -> Optional[Decimal]:
        """Tiền và các khoản tương đương tiền (Mã số 110)."""
        return self.get_value("cash_and_equivalents")

    @property
    def short_term_investments(self) -> Optional[Decimal]:
        """Đầu tư tài chính ngắn hạn (Mã số 120)."""
        return self.get_value("short_term_investments")

    @property
    def trading_securities(self) -> Optional[Decimal]:
        """Chứng khoán kinh doanh (Mã số 121)."""
        return self.get_value("trading_securities")

    @property
    def provision_trading_securities(self) -> Optional[Decimal]:
        """Dự phòng giảm giá chứng khoán kinh doanh (Mã số 129)."""
        return self.get_value("provision_trading_securities")

    @property
    def held_to_maturity_investments(self) -> Optional[Decimal]:
        """Đầu tư nắm giữ đến ngày đáo hạn (Mã số 123)."""
        return self.get_value("held_to_maturity_investments")

    @property
    def short_term_receivables(self) -> Optional[Decimal]:
        """Các khoản phải thu ngắn hạn (Mã số 130)."""
        return self.get_value("short_term_receivables")

    @property
    def inventory(self) -> Optional[Decimal]:
        """Hàng tồn kho (Mã số 140)."""
        return self.get_value("inventory")

    @property
    def non_current_assets(self) -> Optional[Decimal]:
        """Tài sản dài hạn (Mã số 200)."""
        return self.get_value("non_current_assets")

    @property
    def fixed_assets(self) -> Optional[Decimal]:
        """Tài sản cố định (Mã số 220)."""
        return self.get_value("fixed_assets")

    @property
    def total_assets(self) -> Optional[Decimal]:
        """TỔNG CỘNG TÀI SẢN (Mã số 270)."""
        return self.get_value("total_assets")

    @property
    def liabilities(self) -> Optional[Decimal]:
        """NỢ PHẢI TRẢ (Mã số 300)."""
        return self.get_value("liabilities")

    @property
    def current_liabilities(self) -> Optional[Decimal]:
        """Nợ ngắn hạn (Mã số 310)."""
        return self.get_value("current_liabilities")

    @property
    def non_current_liabilities(self) -> Optional[Decimal]:
        """Nợ dài hạn (Mã số 330)."""
        return self.get_value("non_current_liabilities")

    @property
    def equity(self) -> Optional[Decimal]:
        """VỐN CHỦ SỞ HỮU (Mã số 400)."""
        return self.get_value("equity")

    @property
    def total_equity_and_liabilities(self) -> Optional[Decimal]:
        """TỔNG CỘNG NGUỒN VỐN (Mã số 440)."""
        return self.get_value("total_equity_and_liabilities")


class IncomeStatement(BaseModel):
    """Mô hình dữ liệu Báo Cáo Kết Quả Hoạt Động Kinh Doanh (Mẫu B 02 - DN / Thông tư 200).

    Phản ánh tình hình và kết quả hoạt động kinh doanh của doanh nghiệp trong một kỳ kế toán,
    bao gồm hoạt động kinh doanh cốt lõi, hoạt động tài chính và hoạt động khác.
    """
    statement_name: str = "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"
    period: Optional[str] = Field(default=None, description="Kỳ báo cáo e.g. Năm 2020 hoặc Quý 4/2020")
    currency: str = Field(default="VND", description="Đơn vị tiền tệ hạch toán")
    current_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ hiện tại e.g. Năm 2020")
    previous_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ trước e.g. Năm 2019")
    items: Dict[str, LineItem] = Field(default_factory=dict, description="Các chỉ tiêu kinh doanh chuẩn đã ánh xạ")
    unmapped_items: List[LineItem] = Field(default_factory=list, description="Các chỉ tiêu thô chưa ánh xạ được")

    def get_value(self, canonical_key: str, period: str = "current") -> Optional[Decimal]:
        """Truy xuất giá trị số học Decimal an toàn của chỉ tiêu kết quả kinh doanh.

        Args:
            canonical_key (str): Khóa định danh chuẩn (VD: 'net_revenue', 'gross_profit').
            period (str): Kỳ kế toán cần lấy ('current' hoặc 'previous').

        Returns:
            Optional[Decimal]: Giá trị chỉ tiêu hoặc None nếu không tồn tại.
        """
        item = self.items.get(canonical_key)
        if not item:
            return None
        return item.current_period_value if period == "current" else item.previous_period_value

    # Các thuộc tính tiện ích Báo cáo kết quả hoạt động kinh doanh
    @property
    def gross_revenue(self) -> Optional[Decimal]:
        """Doanh thu bán hàng và cung cấp dịch vụ (Mã số 01)."""
        return self.get_value("gross_revenue")

    @property
    def revenue_deductions(self) -> Optional[Decimal]:
        """Các khoản giảm trừ doanh thu (Mã số 02)."""
        return self.get_value("revenue_deductions")

    @property
    def net_revenue(self) -> Optional[Decimal]:
        """Doanh thu thuần về bán hàng và cung cấp dịch vụ (Mã số 10)."""
        return self.get_value("net_revenue")

    @property
    def cost_of_goods_sold(self) -> Optional[Decimal]:
        """Giá vốn hàng bán (Mã số 11)."""
        return self.get_value("cost_of_goods_sold")

    @property
    def gross_profit(self) -> Optional[Decimal]:
        """Lợi nhuận gộp về bán hàng và cung cấp dịch vụ (Mã số 20)."""
        return self.get_value("gross_profit")

    @property
    def financial_income(self) -> Optional[Decimal]:
        """Doanh thu hoạt động tài chính (Mã số 21)."""
        return self.get_value("financial_income")

    @property
    def financial_expenses(self) -> Optional[Decimal]:
        """Chi phí tài chính (Mã số 22)."""
        return self.get_value("financial_expenses")

    @property
    def interest_expenses(self) -> Optional[Decimal]:
        """Trong đó: Chi phí lãi vay (Mã số 23)."""
        return self.get_value("interest_expenses")

    @property
    def selling_expenses(self) -> Optional[Decimal]:
        """Chi phí bán hàng (Mã số 25)."""
        return self.get_value("selling_expenses")

    @property
    def administrative_expenses(self) -> Optional[Decimal]:
        """Chi phí quản lý doanh nghiệp (Mã số 26)."""
        return self.get_value("administrative_expenses")

    @property
    def operating_profit(self) -> Optional[Decimal]:
        """Lợi nhuận thuần từ hoạt động kinh doanh (Mã số 30)."""
        return self.get_value("operating_profit")

    @property
    def other_income(self) -> Optional[Decimal]:
        """Thu nhập khác (Mã số 31)."""
        return self.get_value("other_income")

    @property
    def other_expenses(self) -> Optional[Decimal]:
        """Chi phí khác (Mã số 32)."""
        return self.get_value("other_expenses")

    @property
    def net_other_profit(self) -> Optional[Decimal]:
        """Lợi nhuận khác (Mã số 40)."""
        return self.get_value("net_other_profit")

    @property
    def net_profit_before_tax(self) -> Optional[Decimal]:
        """Tổng lợi nhuận kế toán trước thuế (Mã số 50)."""
        return self.get_value("net_profit_before_tax")

    @property
    def income_tax_expense(self) -> Optional[Decimal]:
        """Chi phí thuế thu nhập doanh nghiệp hiện hành (Mã số 51)."""
        return self.get_value("income_tax_expense")

    @property
    def net_profit_after_tax(self) -> Optional[Decimal]:
        """LỢI NHUẬN SAU THUẾ THU NHẬP DOANH NGHIỆP (Mã số 60)."""
        return self.get_value("net_profit_after_tax")


class CashFlowStatement(BaseModel):
    """Mô hình dữ liệu Báo Cáo Lưu Chuyển Tiền Tệ (Mẫu B 03 - DN / Thông tư 200).

    Phản ánh việc hình thành và sử dụng các luồng tiền phát sinh trong kỳ theo 3 hoạt động:
    Kinh doanh, Đầu tư và Tài chính.
    """
    statement_name: str = "BÁO CÁO LƯU CHUYỂN TIỀN TỆ"
    period: Optional[str] = Field(default=None, description="Kỳ báo cáo lưu chuyển tiền tệ")
    currency: str = Field(default="VND", description="Đơn vị tiền tệ hạch toán")
    items: Dict[str, LineItem] = Field(default_factory=dict, description="Các chỉ tiêu lưu chuyển tiền tệ đã ánh xạ")
    unmapped_items: List[LineItem] = Field(default_factory=list, description="Các chỉ tiêu thô chưa ánh xạ")

    def get_value(self, canonical_key: str, period: str = "current") -> Optional[Decimal]:
        """Truy xuất giá trị số học Decimal an toàn của chỉ tiêu lưu chuyển tiền tệ.

        Args:
            canonical_key (str): Khóa chuẩn của dòng tiền.
            period (str): Kỳ kế toán ('current' hoặc 'previous').

        Returns:
            Optional[Decimal]: Giá trị dòng tiền hoặc None.
        """
        item = self.items.get(canonical_key)
        if not item:
            return None
        return item.current_period_value if period == "current" else item.previous_period_value


class ValidationCheck(BaseModel):
    """Kết quả kiểm định một đẳng thức cân đối kế toán hoặc tính nhất quán dữ liệu.

    Attributes:
        check_id (str): Mã định danh duy nhất của phép kiểm (VD: 'BS_EQ_01', 'IS_EQ_01').
        name (str): Tên hiển thị tiếng Việt của đẳng thức kiểm tra.
        description (str): Công thức toán học và căn cứ quy định kế toán.
        status (CheckStatus): Trạng thái kết quả (pass, warning, fail, not_checkable).
        difference (Optional[Decimal]): Độ chênh lệch giữa hai vế đẳng thức (VND).
        tolerance (Optional[Decimal]): Ngưỡng dung sai làm tròn số được chấp nhận (VND).
        details (Dict[str, Any]): Giá trị của từng biến số tham gia vào đẳng thức kiểm tra.
        message (str): Thông điệp diễn giải kết quả kiểm định thân thiện cho người dùng.
    """
    check_id: str = Field(description="Mã kiểm định duy nhất e.g. BS_EQ_01")
    name: str = Field(description="Tên phép kiểm tra cân đối kế toán")
    description: str = Field(description="Phương trình hoặc quy tắc kế toán được đánh giá")
    status: CheckStatus = Field(description="Trạng thái kiểm định: pass, warning, fail hoặc not_checkable")
    difference: Optional[Decimal] = Field(default=None, description="Độ chênh lệch tuyệt đối hoặc có dấu (VND)")
    tolerance: Optional[Decimal] = Field(default=None, description="Mức dung sai làm tròn chấp nhận được")
    details: Dict[str, Any] = Field(default_factory=dict, description="Chi tiết các biến số và giá trị cấu thành")
    message: str = Field(default="", description="Thông điệp kết luận kiểm định")


class ValidationResult(BaseModel):
    """Báo cáo tổng hợp kết quả kiểm định 4 đẳng thức cân đối kế toán TT200.

    Attributes:
        is_valid (bool): True nếu toàn bộ các phép kiểm bắt buộc đều ĐẠT (không có FAIL).
        total_checks (int): Tổng số phép kiểm tra được thực hiện.
        passed_checks (int): Số lượng phép kiểm tra đạt chuẩn hoàn hảo.
        warning_checks (int): Số lượng phép kiểm tra có cảnh báo chênh lệch nhỏ.
        failed_checks (int): Số lượng phép kiểm tra mất cân đối kế toán nghiêm trọng.
        not_checkable_checks (int): Số lượng phép kiểm tra thiếu số liệu đầu vào.
        checks (List[ValidationCheck]): Danh sách kết quả chi tiết từng đẳng thức.
        summary (str): Tóm tắt tổng quan tình hình cân đối của BCTC.
    """
    is_valid: bool = Field(default=True, description="False nếu có bất kỳ phép kiểm nào rơi vào trạng thái FAIL")
    total_checks: int = 0
    passed_checks: int = 0
    warning_checks: int = 0
    failed_checks: int = 0
    not_checkable_checks: int = 0
    checks: List[ValidationCheck] = Field(default_factory=list, description="Danh sách chi tiết kết quả từng phép kiểm")
    summary: str = Field(default="", description="Đoạn văn tóm tắt đánh giá độ tin cậy của BCTC")


class FinancialReport(BaseModel):
    """Báo cáo tài chính tổng hợp hợp nhất toàn bộ dữ liệu bóc tách và kiểm định.

    Đóng vai trò là thực thể gốc (Aggregate Root) trong Tầng Domain,
    kết nối Bảng cân đối kế toán, Báo cáo KQKD, Lưu chuyển tiền tệ và kết quả kiểm định.
    """
    company_name: Optional[str] = None
    stock_ticker: Optional[str] = None
    fiscal_year: Optional[int] = None
    as_of_date: Optional[str] = Field(default=None, description="Ngày khóa sổ/thời điểm lập BCTC e.g. 31/12/2020")
    period: Optional[str] = Field(default=None, description="Kỳ báo cáo e.g. Năm 2020 hoặc Quý 1/2026")
    report_type: Optional[str] = None
    unit: str = "VND"
    balance_sheet: Optional[BalanceSheet] = None
    income_statement: Optional[IncomeStatement] = None
    cash_flow_statement: Optional[CashFlowStatement] = None
    validation_results: Optional[ValidationResult] = None
    source_document: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata bổ sung trích xuất từ tài liệu")
