"""Gói quy tắc kế toán nghiệp vụ (Domain Accounting Rules) theo Thông tư 200/2014/TT-BTC.

Module này cung cấp:
- Từ điển chuẩn hóa chỉ tiêu BCTC Mẫu B01-DN & B02-DN (canonical).
- Chuẩn hóa số học Việt Nam, số âm ngoặc đơn và quy đổi đơn vị tính (normalizer).
- Động cơ kiểm định 4 đẳng thức cân đối kế toán bắt buộc (validator).
- Bộ hiệu đính lỗi chính tả OCR chuyên ngành kế toán (lexicon).
- Bộ trích xuất niên độ, ngày tháng và bộ lọc hãng kiểm toán (metadata_extractor).
"""
from src.domain.accounting.canonical import (
    BALANCE_SHEET_CANONICAL,
    GENERIC_FINANCIAL_WORDS,
    INCOME_STATEMENT_CANONICAL,
)
from src.domain.accounting.lexicon import FinancialLexiconCorrector
from src.domain.accounting.metadata_extractor import (
    AUDITOR_BLACKLIST,
    StatementMetadataExtractor,
)
from src.domain.accounting.normalizer import (
    AccountingNumberNormalizer,
    NumberStatus,
    ParsedNumber,
    UNIT_MULTIPLIERS,
)
from src.domain.accounting.validator import (
    DEFAULT_ROUNDING_TOLERANCE,
    FinancialValidator,
)

__all__ = [
    "BALANCE_SHEET_CANONICAL",
    "INCOME_STATEMENT_CANONICAL",
    "GENERIC_FINANCIAL_WORDS",
    "FinancialLexiconCorrector",
    "AUDITOR_BLACKLIST",
    "StatementMetadataExtractor",
    "AccountingNumberNormalizer",
    "NumberStatus",
    "ParsedNumber",
    "UNIT_MULTIPLIERS",
    "DEFAULT_ROUNDING_TOLERANCE",
    "FinancialValidator",
]
