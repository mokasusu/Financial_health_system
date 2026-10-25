"""Unit tests for date extraction, column header detection, and date propagation across the pipeline."""
from decimal import Decimal
from pathlib import Path
import pytest

from src.data.parser import FinancialStatementParser
from src.data.schema import (
    FinancialReport,
    BalanceSheet,
    IncomeStatement,
    LineItem,
    MappingMethod,
    MappingStatus,
)
from src.financial.ai_models import AIInterpretationInput
from src.financial.assessment import FinancialHealthAssessor
from src.financial.ratios import (
    FinancialRatioCalculator,
    RatioCategory,
    RatioResult,
    FinancialRatioReport,
)
from src.ui.components import get_statement_column_names
from src.ui.export import export_analysis_to_json


def _make_item(key: str, label: str, cur: Decimal, prev: Decimal) -> LineItem:
    return LineItem(
        raw_label=label,
        normalized_label=label.lower(),
        canonical_key=key,
        current_period_value=cur,
        previous_period_value=prev,
        mapping_method=MappingMethod.CODE_EXACT,
        mapping_status=MappingStatus.MAPPED,
        confidence_score=0.95,
    )


class TestDateAndHeaderDetection:
    """Test parser static date detection helper functions."""

    def test_detect_as_of_date_vietnamese_formal(self):
        sample = "BẢNG CÂN ĐỐI KẾ TOÁN\nTại ngày 31 tháng 12 năm 2020\nĐơn vị tính: VND"
        d, y = FinancialStatementParser._detect_as_of_date(sample)
        assert d == "31/12/2020"
        assert y == 2020

    def test_detect_as_of_date_quarter(self):
        sample = "BÁO CÁO TÌNH HÌNH TÀI CHÍNH\nTại ngày 31 tháng 03 năm 2026\nMẫu số B 01a - DN"
        d, y = FinancialStatementParser._detect_as_of_date(sample)
        assert d == "31/03/2026"
        assert y == 2026

    def test_detect_as_of_date_slash_format(self):
        sample = "BẢNG CÂN ĐỐI KẾ TOÁN\nTại ngày 30/06/2024\n(Ban hành theo TT 200)"
        d, y = FinancialStatementParser._detect_as_of_date(sample)
        assert d == "30/06/2024"
        assert y == 2024

    def test_detect_as_of_date_fiscal_year_end(self):
        sample = "Cho năm tài chính kết thúc ngày 31/12/2021\nBáo cáo kết quả hoạt động kinh doanh"
        d, y = FinancialStatementParser._detect_as_of_date(sample)
        assert d == "31/12/2021"
        assert y == 2021

    def test_detect_as_of_date_english_format(self):
        sample = "CONSOLIDATED STATEMENT OF FINANCIAL POSITION\nAs at 30 September 2023\nIn VND"
        d, y = FinancialStatementParser._detect_as_of_date(sample)
        assert d == "30/09/2023"
        assert y == 2023

    def test_detect_as_of_date_none_when_absent(self):
        sample = "Không có thông tin ngày tháng cụ thể trong dòng này"
        d, y = FinancialStatementParser._detect_as_of_date(sample)
        assert d is None
        assert y is None

    def test_detect_period_label(self):
        lbl, y = FinancialStatementParser._detect_period_label("Cho năm tài chính kết thúc ngày 31/12/2020")
        assert lbl == "Năm 2020"
        assert y == 2020

        lbl, y = FinancialStatementParser._detect_period_label("Quý 1 năm 2026")
        assert lbl == "Quý 1/2026"
        assert y == 2026

        lbl, y = FinancialStatementParser._detect_period_label("Quý III năm 2024")
        assert lbl == "Quý III/2024"
        assert y == 2024

        lbl, y = FinancialStatementParser._detect_period_label("6 tháng đầu năm 2023")
        assert lbl == "6 tháng 2023"
        assert y == 2023

        lbl, y = FinancialStatementParser._detect_period_label("Văn bản chung")
        assert lbl is None
        assert y is None

    def test_detect_column_headers_balance_sheet_dates(self):
        cells = ["MÃ SỐ", "THUYẾT MINH", "31/12/2020", "01/01/2020"]
        cur, prev = FinancialStatementParser._detect_column_headers(cells, "balance_sheet")
        assert cur == "31/12/2020"
        assert prev == "01/01/2020"

    def test_detect_column_headers_balance_sheet_cuoi_dau_nam(self):
        cells = ["Chỉ tiêu", "Mã số", "Thuyết minh", "Số cuối năm", "Số đầu năm"]
        cur, prev = FinancialStatementParser._detect_column_headers(cells, "balance_sheet")
        assert cur == "Số cuối năm"
        assert prev == "Số đầu năm"

    def test_detect_column_headers_quarter_balance_sheet(self):
        cells = ["MÃ SỐ", "THUYẾT MINH", "31/03/2026", "01/01/2026"]
        cur, prev = FinancialStatementParser._detect_column_headers(cells, "balance_sheet")
        assert cur == "31/03/2026"
        assert prev == "01/01/2026"

    def test_detect_column_headers_income_statement_nam_nay_nam_truoc(self):
        cells = ["Chỉ tiêu", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"]
        cur, prev = FinancialStatementParser._detect_column_headers(cells, "income_statement")
        assert cur == "Năm nay"
        assert prev == "Năm trước"

    def test_detect_column_headers_quarter_income_statement(self):
        cells = ["Chỉ tiêu", "Mã số", "Quý 1/2026", "Quý 1/2025"]
        cur, prev = FinancialStatementParser._detect_column_headers(cells, "income_statement")
        assert cur == "Quý 1/2026"
        assert prev == "Quý 1/2025"


class TestParserSampleDateExtraction:
    """Test integration parsing on real sample files."""

    def test_conghuy_a32_date_and_header_extraction(self):
        sample_path = Path("data/samples/conghuy_A32_2020_sample.txt")
        if not sample_path.exists():
            pytest.skip("Sample file not present in data/samples")

        content = sample_path.read_text(encoding="utf-8")
        parser = FinancialStatementParser()
        report = parser.parse(content)

        assert report.fiscal_year == 2020
        assert report.as_of_date == "31/12/2020"
        assert report.period == "Năm 2020"

        # Check Balance Sheet columns
        assert report.balance_sheet is not None
        assert report.balance_sheet.current_period_name == "31/12/2020"
        assert report.balance_sheet.previous_period_name == "01/01/2020"

        # Check Income Statement columns
        assert report.income_statement is not None
        assert report.income_statement.current_period_name == "Năm 2020"
        assert report.income_statement.previous_period_name == "Năm 2019"

        # Check UI helper
        (bs_cur, bs_prev), (is_cur, is_prev) = get_statement_column_names(report)
        assert bs_cur == "31/12/2020"
        assert bs_prev == "01/01/2020"
        assert is_cur == "Năm 2020"
        assert is_prev == "Năm 2019"

    def test_vduydong_a32_date_and_header_extraction(self):
        sample_path = Path("data/samples/vduydong_A32_2017_sample.txt")
        if not sample_path.exists():
            pytest.skip("Sample file not present in data/samples")

        content = sample_path.read_text(encoding="utf-8")
        parser = FinancialStatementParser()
        report = parser.parse(content)

        assert report.fiscal_year == 2017
        assert report.as_of_date == "31/12/2017"
        assert report.period == "Năm 2017"

        assert report.balance_sheet is not None
        assert report.balance_sheet.current_period_name == "Số cuối năm"
        assert report.balance_sheet.previous_period_name == "Số đầu năm"

        # Formatted UI column headers combine date with raw header
        (bs_cur, bs_prev), (is_cur, is_prev) = get_statement_column_names(report)
        assert bs_cur == "31/12/2017 (Số cuối năm)"
        assert bs_prev == "01/01/2017 (Số đầu năm)"


class TestDatePropagationAcrossPipeline:
    """Test propagation of as_of_date and period across ratios, assessment, AI and export."""

    @pytest.fixture
    def mock_report(self) -> FinancialReport:
        bs = BalanceSheet(
            as_of_date="31/03/2026",
            current_period_name="31/03/2026",
            previous_period_name="01/01/2026",
        )
        bs.items["total_assets"] = _make_item("total_assets", "TỔNG CỘNG TÀI SẢN", Decimal("1000"), Decimal("800"))
        bs.items["current_assets"] = _make_item("current_assets", "Tài sản ngắn hạn", Decimal("600"), Decimal("500"))
        bs.items["cash_and_equivalents"] = _make_item("cash_and_equivalents", "Tiền", Decimal("200"), Decimal("150"))
        bs.items["short_term_investments"] = _make_item("short_term_investments", "Đầu tư ngắn hạn", Decimal("100"), Decimal("50"))
        bs.items["inventory"] = _make_item("inventory", "Hàng tồn kho", Decimal("150"), Decimal("120"))
        bs.items["short_term_receivables"] = _make_item("short_term_receivables", "Phải thu ngắn hạn", Decimal("150"), Decimal("180"))
        bs.items["total_liabilities"] = _make_item("total_liabilities", "NỢ PHẢI TRẢ", Decimal("400"), Decimal("350"))
        bs.items["current_liabilities"] = _make_item("current_liabilities", "Nợ ngắn hạn", Decimal("300"), Decimal("250"))
        bs.items["short_term_borrowings"] = _make_item("short_term_borrowings", "Vay ngắn hạn", Decimal("100"), Decimal("80"))
        bs.items["long_term_borrowings"] = _make_item("long_term_borrowings", "Vay dài hạn", Decimal("50"), Decimal("50"))
        bs.items["owner_equity"] = _make_item("owner_equity", "VỐN CHỦ SỞ HỮU", Decimal("600"), Decimal("450"))

        is_stmt = IncomeStatement(
            fiscal_year=2026,
            period="Quý 1/2026",
            current_period_name="Quý 1/2026",
            previous_period_name="Quý 1/2025",
        )
        is_stmt.items["net_revenue"] = _make_item("net_revenue", "Doanh thu thuần", Decimal("1200"), Decimal("1000"))
        is_stmt.items["cogs"] = _make_item("cogs", "Giá vốn hàng bán", Decimal("800"), Decimal("700"))
        is_stmt.items["gross_profit"] = _make_item("gross_profit", "Lợi nhuận gộp", Decimal("400"), Decimal("300"))
        is_stmt.items["operating_profit"] = _make_item("operating_profit", "Lợi nhuận từ HĐKD", Decimal("200"), Decimal("150"))
        is_stmt.items["financial_expenses"] = _make_item("financial_expenses", "Chi phí tài chính", Decimal("20"), Decimal("15"))
        is_stmt.items["interest_expenses"] = _make_item("interest_expenses", "Chi phí lãi vay", Decimal("10"), Decimal("10"))
        is_stmt.items["net_profit_after_tax"] = _make_item("net_profit_after_tax", "LN sau thuế", Decimal("150"), Decimal("120"))

        return FinancialReport(
            company_name="Công ty Cổ phần Sữa Việt Nam",
            fiscal_year=2026,
            as_of_date="31/03/2026",
            period="Quý 1/2026",
            balance_sheet=bs,
            income_statement=is_stmt,
        )

    def test_ratio_calculator_propagates_date(self, mock_report):
        calc = FinancialRatioCalculator()
        ratio_report = calc.calculate_all(mock_report)
        assert ratio_report.fiscal_year == 2026
        assert ratio_report.as_of_date == "31/03/2026"
        assert ratio_report.period == "Quý 1/2026"

    def test_assessor_propagates_date(self, mock_report):
        calc = FinancialRatioCalculator()
        ratio_report = calc.calculate_all(mock_report)
        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(ratio_report)
        assert assessment.fiscal_year == 2026
        assert assessment.as_of_date == "31/03/2026"
        assert assessment.period == "Quý 1/2026"

    def test_ai_prompt_context_includes_exact_date(self, mock_report):
        calc = FinancialRatioCalculator()
        ratio_report = calc.calculate_all(mock_report)
        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(ratio_report)
        ai_input = AIInterpretationInput.from_4_core_kpis(
            assessment=assessment,
            ratio_report=ratio_report,
        )
        assert ai_input.as_of_date == "31/03/2026"
        prompt_text = ai_input.to_formatted_prompt_context()
        assert "Tại ngày 31/03/2026" in prompt_text

    def test_json_export_includes_as_of_date(self, mock_report):
        calc = FinancialRatioCalculator()
        ratio_report = calc.calculate_all(mock_report)
        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(ratio_report)
        
        json_output = export_analysis_to_json(
            assessment=assessment,
            report=mock_report,
            ai_output=None,
        )
        assert "31/03/2026" in json_output
        assert '"as_of_date": "31/03/2026"' in json_output
        assert '"period": "Quý 1/2026"' in json_output
