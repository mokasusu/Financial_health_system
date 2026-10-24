"""Unit and regression tests for PDF OCR Table Row Alignment and Financial Statement Mapping.

Covers the 8 mandatory test criteria:
1. Item name, code, and value on the same row.
2. Item name split across multiple OCR lines/segments.
3. Negative values formatted in parentheses (including cut-off OCR parentheses).
4. Consecutive rows containing the same keyword ('kinh doanh').
5. Summary row with positive value and detailed row with negative value.
6. OCR fails to detect name or code / ambiguous generic keyword ('kinh doanh').
7. Numbers with various thousand separators (dot, comma, footnote letters).
8. Edge cases: merged tokens, malformed coordinates, note references attached to code.
"""
from decimal import Decimal
import pytest
from src.data.normalizer import AccountingNumberNormalizer, NumberStatus
from src.data.parser import FinancialStatementParser
from src.data.schema import MappingMethod, MappingStatus
from src.ocr.models import DocumentExtractionResult, PageExtractionResult
from src.ocr.paddle_engine import PaddleOCREngine


class TestRowAlignmentAndFinancialMapping:
    """Comprehensive test suite for financial statement row alignment and mapping."""

    @pytest.fixture
    def parser(self):
        return FinancialStatementParser()

    # Case 1: Tên chỉ tiêu, mã số và giá trị nằm trên cùng một dòng
    def test_case_1_single_row_alignment(self, parser):
        text = (
            "BẢNG CÂN ĐỐI KẾ TOÁN TẠI NGÀY 31/12/2025\n"
            "Đơn vị tính: VND\n"
            "Các khoản đầu tư tài chính ngắn hạn\t120\t21.354.863.600.460\t23.260.088.671.767\n"
        )
        report = parser.parse(text)
        bs = report.balance_sheet
        assert "short_term_investments" in bs.items
        item = bs.items["short_term_investments"]
        assert item.item_code == "120"
        assert item.current_period_value == Decimal("21354863600460")
        assert item.previous_period_value == Decimal("23260088671767")
        assert item.mapping_status == MappingStatus.MAPPED
        assert item.mapping_method == MappingMethod.CODE_EXACT
        assert item.confidence_score >= 0.95

    # Case 2: Tên chỉ tiêu bị OCR tách thành nhiều đoạn / nhiều dòng
    def test_case_2_multiline_label_reconstruction(self, parser):
        # Line 1 has top label fragment, Line 2 has bottom fragment + code + values
        text = (
            "BẢNG CÂN ĐỐI KẾ TOÁN\n"
            "Đơn vị tính: VND\n"
            "Dự phòng giảm giá chứng khoán\n"
            "kinh doanh\t122\tV.4(a)\t(849.021.293)\t(920.681.738)\n"
        )
        report = parser.parse(text)
        bs = report.balance_sheet
        assert "provision_trading_securities" in bs.items
        item = bs.items["provision_trading_securities"]
        assert "Dự phòng giảm giá chứng khoán kinh doanh" in item.raw_label
        assert item.item_code == "122"
        assert item.current_period_value == Decimal("-849021293")
        assert item.previous_period_value == Decimal("-920681738")
        assert item.mapping_status == MappingStatus.MAPPED

    # Case 3: Giá trị âm được biểu diễn trong ngoặc đơn
    def test_case_3_negative_values_in_parentheses(self):
        # Standard balanced parentheses
        res1 = AccountingNumberNormalizer.parse("(849.021.293)")
        assert res1.is_valid is True
        assert res1.is_negative is True
        assert res1.value == Decimal("-849021293")

        # Cut-off OCR open parenthesis (common in scanned right-column cutoffs)
        res2 = AccountingNumberNormalizer.parse("(22.332.866.679")
        assert res2.is_valid is True
        assert res2.is_negative is True
        assert res2.value == Decimal("-22332866679")

        # Cut-off trailing parenthesis
        res3 = AccountingNumberNormalizer.parse("920.681.738)")
        assert res3.is_valid is True
        assert res3.is_negative is True
        assert res3.value == Decimal("-920681738")

    # Case 4: Hai dòng liên tiếp có tên chứa cùng từ khóa 'kinh doanh'
    def test_case_4_consecutive_rows_with_same_keyword(self, parser):
        text = (
            "BẢNG CÂN ĐỐI KẾ TOÁN\n"
            "Đơn vị tính: VND\n"
            "1. Chứng khoán kinh doanh\t121\tV.4(a)\t1.288.677.349\t1.248.322.211\n"
            "2. Dự phòng giảm giá chứng khoán kinh doanh\t122\tV.4(a)\t(849.021.293)\t(920.681.738)\n"
        )
        report = parser.parse(text)
        bs = report.balance_sheet

        # Row 121: trading_securities
        assert "trading_securities" in bs.items
        item_121 = bs.items["trading_securities"]
        assert item_121.item_code == "121"
        assert item_121.current_period_value == Decimal("1288677349")
        assert item_121.previous_period_value == Decimal("1248322211")

        # Row 122: provision_trading_securities
        assert "provision_trading_securities" in bs.items
        item_122 = bs.items["provision_trading_securities"]
        assert item_122.item_code == "122"
        assert item_122.current_period_value == Decimal("-849021293")
        assert item_122.previous_period_value == Decimal("-920681738")

        # Crucial check: Neither row was erroneously hijacked by 'short_term_investments' (120)
        assert "short_term_investments" not in bs.items

    # Case 5: Dòng tổng hợp có giá trị dương và dòng chi tiết có giá trị âm
    def test_case_5_summary_positive_and_detail_negative_alignment(self, parser):
        text = (
            "BẢNG CÂN ĐỐI KẾ TOÁN\n"
            "Đơn vị tính: VND\n"
            "II. Các khoản đầu tư tài chính ngắn hạn\t120\t21.354.863.600.460\t23.260.088.671.767\n"
            "1. Chứng khoán kinh doanh\t121\t1.288.677.349\t1.248.322.211\n"
            "2. Dự phòng giảm giá chứng khoán kinh doanh\t122\t(849.021.293)\t(920.681.738)\n"
            "3. Đầu tư nắm giữ đến ngày đáo hạn\t123\t21.354.423.944.404\t23.259.761.031.294\n"
        )
        report = parser.parse(text)
        bs = report.balance_sheet

        # Summary line 120 must strictly preserve its own positive values
        assert bs.short_term_investments == Decimal("21354863600460")
        item_120 = bs.items["short_term_investments"]
        assert item_120.previous_period_value == Decimal("23260088671767")
        assert item_120.current_period_value > 0

        # Detail line 122 must strictly preserve its negative values
        item_122 = bs.items["provision_trading_securities"]
        assert item_122.current_period_value == Decimal("-849021293")
        assert item_122.previous_period_value == Decimal("-920681738")

    # Case 6: OCR không nhận diện được tên hoặc mã số / từ khóa chung chung
    def test_case_6_ambiguous_keyword_and_conflicting_code(self, parser):
        # 6.A: Standalone generic keyword 'kinh doanh' without valid code must NOT map to short_term_investments
        item_generic = parser.map_line_item(
            raw_label="kinh doanh",
            item_code=None,
            cur_val=Decimal("1000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="balance_sheet",
        )
        assert item_generic.canonical_key != "short_term_investments"
        assert item_generic.mapping_status == MappingStatus.UNMAPPED

        # 6.B: Code 120 with conflicting antipattern label (e.g. 'Dự phòng giảm giá chứng khoán kinh doanh')
        # Row inconsistency must trigger NEEDS_REVIEW
        item_conflict = parser.map_line_item(
            raw_label="Dự phòng giảm giá chứng khoán kinh doanh",
            item_code="120",
            cur_val=Decimal("-849021293"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="balance_sheet",
        )
        assert item_conflict.mapping_status == MappingStatus.NEEDS_REVIEW
        assert item_conflict.confidence_score <= 0.50
        assert item_conflict.row_consistency is not None and item_conflict.row_consistency < 0.50
        assert any("xung đột" in w for w in item_conflict.warnings)

        # 6.C: Code 122 must not be mapped to Code 120 key
        item_122 = parser.map_line_item(
            raw_label="chứng khoán kinh doanh",
            item_code="122",
            cur_val=Decimal("-849021293"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="balance_sheet",
        )
        assert item_122.canonical_key != "short_term_investments"

    # Case 7: Giá trị có dấu phân cách hàng nghìn (dấu chấm, dấu phẩy, footnote noise)
    def test_case_7_thousand_separators(self):
        # Comma thousand separator
        res_comma = AccountingNumberNormalizer.parse("1,288,677,349")
        assert res_comma.is_valid is True
        assert res_comma.value == Decimal("1288677349")

        # Dot thousand separator
        res_dot = AccountingNumberNormalizer.parse("21.354.863.600.460")
        assert res_dot.is_valid is True
        assert res_dot.value == Decimal("21354863600460")

        # Footnote trailing letter
        res_footnote = AccountingNumberNormalizer.parse("4.793.132.726.166S")
        assert res_footnote.is_valid is True
        assert res_footnote.value == Decimal("4793132726166")

    # Case 8: Dữ liệu thiếu tọa độ, token dính khoảng trắng, note dính code
    def test_case_8_edge_cases_and_merged_tokens(self, parser):
        # 8.A: Space-separated numbers in single column
        text = (
            "BẢNG CÂN ĐỐI KẾ TOÁN\n"
            "Đơn vị tính: VND\n"
            "Đầu tư tài chính ngắn hạn\t120\t21.354.863.600.460 23.260.088.671.767\n"
        )
        report = parser.parse(text)
        bs = report.balance_sheet
        assert bs.short_term_investments == Decimal("21354863600460")
        assert bs.items["short_term_investments"].previous_period_value == Decimal("23260088671767")

        # 8.B: Code with note reference merged into single cell e.g. '121 V.4(a)'
        tokens = ["Chứng khoán kinh doanh", "121 V.4(a)", "1.288.677.349", "1.248.322.211"]
        expanded = parser._expand_cell_tokens(tokens)
        assert "121" in expanded
        assert "V.4(a)" in expanded
