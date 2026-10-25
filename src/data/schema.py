"""Pydantic data models for Vietnamese financial statements (VAS / Circular 200/2014/TT-BTC)."""
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MappingMethod(str, Enum):
    """Method used to map a raw line item to a canonical financial key."""
    CODE_EXACT = "code_exact"          # Matched official item code (e.g., MS 100, 110)
    LABEL_EXACT = "label_exact"        # Exact normalized string match
    LABEL_SYNONYM = "label_synonym"    # Matched known synonym dictionary
    REGEX_RULE = "regex_rule"          # Matched contextual regex rule
    UNMAPPED = "unmapped"              # Could not map confidently


class MappingStatus(str, Enum):
    """Confidence and audit status of the mapping result."""
    MAPPED = "mapped"                  # High confidence mapping
    NEEDS_REVIEW = "needs_review"      # Ambiguous or partial match requiring manual check
    UNMAPPED = "unmapped"              # No valid mapping candidate found


class AccountingStandard(str, Enum):
    """Applicable accounting standards in Vietnam."""
    TT200_2014 = "TT200/2014/TT-BTC"   # Circular 200 standard for enterprises
    VAS = "VAS"                        # Vietnamese Accounting Standards generic
    UNKNOWN = "unknown"


class CheckStatus(str, Enum):
    """Result status of a validation equation or check."""
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NOT_CHECKABLE = "not_checkable"    # Required data points are missing or incomplete


class LineItem(BaseModel):
    """A single normalized accounting line item with audit provenance."""
    raw_label: str = Field(description="Original uncleaned label as extracted by OCR/parser")
    normalized_label: str = Field(description="Cleaned, lowercased, stripped label")
    canonical_key: Optional[str] = Field(default=None, description="System canonical key (e.g., current_assets)")
    item_code: Optional[str] = Field(default=None, description="Official line item code (e.g., 100, 110) if verified")
    accounting_standard: AccountingStandard = Field(default=AccountingStandard.TT200_2014)
    current_period_value: Optional[Decimal] = Field(default=None, description="Value for current reporting period")
    previous_period_value: Optional[Decimal] = Field(default=None, description="Value for previous comparison period")
    unit: Optional[str] = Field(default="VND", description="Currency unit (VND, nghin VND, trieu VND, ty VND)")
    source_page: Optional[int] = Field(default=None, description="1-indexed source document page")
    mapping_method: MappingMethod = Field(default=MappingMethod.UNMAPPED)
    mapping_status: MappingStatus = Field(default=MappingStatus.UNMAPPED)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    ocr_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="OCR text recognition confidence")
    mapping_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Semantic mapping confidence")
    row_consistency: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Consistency score between label, code, and values")
    warnings: List[str] = Field(default_factory=list, description="Warnings encountered during parsing/mapping")


class BalanceSheet(BaseModel):
    """Bảng cân đối kế toán (Form B 01 - DN / Circular 200)."""
    statement_name: str = "BẢNG CÂN ĐỐI KẾ TOÁN"
    as_of_date: Optional[str] = Field(default=None, description="Report date e.g. 31/12/2020")
    currency: str = Field(default="VND")
    current_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ hiện tại e.g. 31/12/2020 hoặc Số cuối năm")
    previous_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ trước e.g. 01/01/2020 hoặc Số đầu năm")
    items: Dict[str, LineItem] = Field(
        default_factory=dict,
        description="Mapped canonical items keyed by canonical_key"
    )
    unmapped_items: List[LineItem] = Field(
        default_factory=list,
        description="Items that could not be mapped to canonical keys"
    )

    def get_value(self, canonical_key: str, period: str = "current") -> Optional[Decimal]:
        """Retrieve Decimal value for a canonical key safely."""
        item = self.items.get(canonical_key)
        if not item:
            return None
        return item.current_period_value if period == "current" else item.previous_period_value

    # Key Balance Sheet Properties
    @property
    def current_assets(self) -> Optional[Decimal]:
        return self.get_value("current_assets")

    @property
    def cash_and_equivalents(self) -> Optional[Decimal]:
        return self.get_value("cash_and_equivalents")

    @property
    def short_term_investments(self) -> Optional[Decimal]:
        return self.get_value("short_term_investments")

    @property
    def trading_securities(self) -> Optional[Decimal]:
        return self.get_value("trading_securities")

    @property
    def provision_trading_securities(self) -> Optional[Decimal]:
        return self.get_value("provision_trading_securities")

    @property
    def held_to_maturity_investments(self) -> Optional[Decimal]:
        return self.get_value("held_to_maturity_investments")

    @property
    def short_term_receivables(self) -> Optional[Decimal]:
        return self.get_value("short_term_receivables")

    @property
    def inventory(self) -> Optional[Decimal]:
        return self.get_value("inventory")

    @property
    def non_current_assets(self) -> Optional[Decimal]:
        return self.get_value("non_current_assets")

    @property
    def fixed_assets(self) -> Optional[Decimal]:
        return self.get_value("fixed_assets")

    @property
    def total_assets(self) -> Optional[Decimal]:
        return self.get_value("total_assets")

    @property
    def liabilities(self) -> Optional[Decimal]:
        return self.get_value("liabilities")

    @property
    def current_liabilities(self) -> Optional[Decimal]:
        return self.get_value("current_liabilities")

    @property
    def non_current_liabilities(self) -> Optional[Decimal]:
        return self.get_value("non_current_liabilities")

    @property
    def equity(self) -> Optional[Decimal]:
        return self.get_value("equity")

    @property
    def total_equity_and_liabilities(self) -> Optional[Decimal]:
        return self.get_value("total_equity_and_liabilities")


class IncomeStatement(BaseModel):
    """Báo cáo kết quả hoạt động kinh doanh (Form B 02 - DN / Circular 200)."""
    statement_name: str = "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"
    period: Optional[str] = Field(default=None, description="e.g. Năm 2020 or Quý 4/2020")
    currency: str = Field(default="VND")
    current_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ hiện tại e.g. Năm 2020")
    previous_period_name: Optional[str] = Field(default=None, description="Tên cột kỳ trước e.g. Năm 2019")
    items: Dict[str, LineItem] = Field(default_factory=dict)
    unmapped_items: List[LineItem] = Field(default_factory=list)

    def get_value(self, canonical_key: str, period: str = "current") -> Optional[Decimal]:
        item = self.items.get(canonical_key)
        if not item:
            return None
        return item.current_period_value if period == "current" else item.previous_period_value

    @property
    def gross_revenue(self) -> Optional[Decimal]:
        return self.get_value("gross_revenue")

    @property
    def revenue_deductions(self) -> Optional[Decimal]:
        return self.get_value("revenue_deductions")

    @property
    def net_revenue(self) -> Optional[Decimal]:
        return self.get_value("net_revenue")

    @property
    def cost_of_goods_sold(self) -> Optional[Decimal]:
        return self.get_value("cost_of_goods_sold")

    @property
    def gross_profit(self) -> Optional[Decimal]:
        return self.get_value("gross_profit")

    @property
    def financial_income(self) -> Optional[Decimal]:
        return self.get_value("financial_income")

    @property
    def financial_expenses(self) -> Optional[Decimal]:
        return self.get_value("financial_expenses")

    @property
    def interest_expenses(self) -> Optional[Decimal]:
        return self.get_value("interest_expenses")

    @property
    def selling_expenses(self) -> Optional[Decimal]:
        return self.get_value("selling_expenses")

    @property
    def administrative_expenses(self) -> Optional[Decimal]:
        return self.get_value("administrative_expenses")

    @property
    def operating_profit(self) -> Optional[Decimal]:
        return self.get_value("operating_profit")

    @property
    def other_income(self) -> Optional[Decimal]:
        return self.get_value("other_income")

    @property
    def other_expenses(self) -> Optional[Decimal]:
        return self.get_value("other_expenses")

    @property
    def net_other_profit(self) -> Optional[Decimal]:
        return self.get_value("net_other_profit")

    @property
    def net_profit_before_tax(self) -> Optional[Decimal]:
        return self.get_value("net_profit_before_tax")

    @property
    def income_tax_expense(self) -> Optional[Decimal]:
        return self.get_value("income_tax_expense")

    @property
    def net_profit_after_tax(self) -> Optional[Decimal]:
        return self.get_value("net_profit_after_tax")


class CashFlowStatement(BaseModel):
    """Báo cáo lưu chuyển tiền tệ (Form B 03 - DN / Circular 200)."""
    statement_name: str = "BÁO CÁO LƯU CHUYỂN TIỀN TỆ"
    period: Optional[str] = Field(default=None)
    currency: str = Field(default="VND")
    items: Dict[str, LineItem] = Field(default_factory=dict)
    unmapped_items: List[LineItem] = Field(default_factory=list)

    def get_value(self, canonical_key: str, period: str = "current") -> Optional[Decimal]:
        item = self.items.get(canonical_key)
        if not item:
            return None
        return item.current_period_value if period == "current" else item.previous_period_value


class ValidationCheck(BaseModel):
    """A single financial statement balance or consistency check result."""
    check_id: str = Field(description="Unique check identifier e.g. BS_EQ_01")
    name: str = Field(description="Human readable name of check")
    description: str = Field(description="Equation or rule being evaluated")
    status: CheckStatus = Field(description="Check result: pass, warning, fail, or not_checkable")
    difference: Optional[Decimal] = Field(default=None, description="Absolute or signed difference")
    tolerance: Optional[Decimal] = Field(default=None, description="Acceptable rounding tolerance applied")
    details: Dict[str, Any] = Field(default_factory=dict, description="Variables and values used in calculation")
    message: str = Field(default="", description="Human explanation of outcome")


class ValidationResult(BaseModel):
    """Comprehensive validation report for a financial statement."""
    is_valid: bool = Field(default=True, description="False if any check marked FAIL")
    total_checks: int = 0
    passed_checks: int = 0
    warning_checks: int = 0
    failed_checks: int = 0
    not_checkable_checks: int = 0
    checks: List[ValidationCheck] = Field(default_factory=list)
    summary: str = Field(default="")


class FinancialReport(BaseModel):
    """Aggregated financial report model consolidating all parsed and validated statements."""
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
    metadata: Dict[str, Any] = Field(default_factory=dict)
