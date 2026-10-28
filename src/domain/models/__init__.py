"""Gói mô hình miền (Domain Models) của Hệ thống Sức khỏe Tài chính.

Cung cấp các thực thể và cấu trúc dữ liệu chuẩn hóa của hệ thống:
- Các chỉ tiêu và chuẩn mực kế toán TT200 (LineItem, AccountingStandard)
- Báo cáo tài chính chuẩn (BalanceSheet, IncomeStatement, FinancialReport)
- Kết quả kiểm định cân đối (ValidationCheck, ValidationResult)
- Dữ liệu trích xuất OCR & Layout (DocumentExtractionResult, PageExtractionResult)
- Các chỉ số tài chính Decimal (RatioResult, FinancialRatioReport)
- Đánh giá phân loại rủi ro (FinancialAssessment, FinancialWarning)
- Dữ liệu nhận định AI độc lập 4 chỉ số cốt lõi (AIInterpretationInput, AIInterpretationOutput)
"""
from src.domain.models.line_item import (
    AccountingStandard,
    CheckStatus,
    LineItem,
    MappingMethod,
    MappingStatus,
)
from src.domain.models.bctc import (
    BalanceSheet,
    CashFlowStatement,
    FinancialReport,
    IncomeStatement,
    ValidationCheck,
    ValidationResult,
)
from src.domain.models.ocr import (
    DocumentExtractionResult,
    ExtractionMethod,
    ExtractionStatus,
    LayoutRegion,
    PageExtractionResult,
)
from src.domain.models.ratios import (
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
)
from src.domain.models.assessment import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    OverallHealthStatus,
    RatioAssessment,
    WarningCategory,
    WarningSeverity,
)
from src.domain.models.ai import (
    AIInterpretationInput,
    AIInterpretationOutput,
    AIRiskItem,
    AIStrengthItem,
    CORE_4_KPI_DEFINITIONS,
    CoreKPIData,
    FinancialRatioInput,
    FinancialWarningInput,
)

__all__ = [
    # Line Item
    "AccountingStandard",
    "CheckStatus",
    "LineItem",
    "MappingMethod",
    "MappingStatus",
    # BCTC
    "BalanceSheet",
    "CashFlowStatement",
    "FinancialReport",
    "IncomeStatement",
    "ValidationCheck",
    "ValidationResult",
    # OCR
    "DocumentExtractionResult",
    "ExtractionMethod",
    "ExtractionStatus",
    "LayoutRegion",
    "PageExtractionResult",
    # Ratios
    "FinancialRatioReport",
    "RatioCategory",
    "RatioResult",
    "RatioStatus",
    # Assessment
    "AssessmentStatus",
    "FinancialAssessment",
    "FinancialWarning",
    "OverallHealthStatus",
    "RatioAssessment",
    "WarningCategory",
    "WarningSeverity",
    # AI
    "AIInterpretationInput",
    "AIInterpretationOutput",
    "AIRiskItem",
    "AIStrengthItem",
    "CORE_4_KPI_DEFINITIONS",
    "CoreKPIData",
    "FinancialRatioInput",
    "FinancialWarningInput",
]
