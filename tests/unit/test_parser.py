"""Unit tests for FinancialStatementParser and Semantic Mapping."""
from decimal import Decimal
import pytest
from src.data.parser import FinancialStatementParser
from src.data.schema import MappingMethod, MappingStatus
from src.ocr.models import DocumentExtractionResult, PageExtractionResult


class TestFinancialStatementParser:
    """Test semantic mapping, disambiguation, and document parsing."""

    def test_exact_code_mapping(self):
        parser = FinancialStatementParser()
        # Item with code "100"
        item_100 = parser.map_line_item(
            raw_label="A. TÀI SẢN NGẮN HẠN",
            item_code="100",
            cur_val=Decimal("356691280424"),
            prev_val=Decimal("298767972671"),
            unit="VND",
            source_page=1,
            context="balance_sheet",
        )
        assert item_100.canonical_key == "current_assets"
        assert item_100.mapping_method == MappingMethod.CODE_EXACT
        assert item_100.mapping_status == MappingStatus.MAPPED
        assert item_100.current_period_value == Decimal("356691280424")

    def test_disambiguation_between_similar_revenue_items(self):
        parser = FinancialStatementParser()

        # Gross revenue (Doanh thu bán hàng và cung cấp dịch vụ - MS 01)
        item_gross = parser.map_line_item(
            raw_label="Doanh thu bán hàng và cung cấp dịch vụ",
            item_code=None,
            cur_val=Decimal("650000000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="income_statement",
        )
        assert item_gross.canonical_key == "gross_revenue"
        assert item_gross.canonical_key != "net_revenue"

        # Net revenue (Doanh thu thuần về bán hàng - MS 10)
        item_net = parser.map_line_item(
            raw_label="Doanh thu thuần về bán hàng và cung cấp dịch vụ",
            item_code=None,
            cur_val=Decimal("650000000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="income_statement",
        )
        assert item_net.canonical_key == "net_revenue"
        assert item_net.canonical_key != "gross_revenue"

    def test_disambiguation_between_profit_items(self):
        parser = FinancialStatementParser()

        # Gross profit
        p_gross = parser.map_line_item(
            raw_label="Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
            item_code=None,
            cur_val=Decimal("130000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="income_statement",
        )
        assert p_gross.canonical_key == "gross_profit"

        # Operating profit
        p_op = parser.map_line_item(
            raw_label="Lợi nhuận thuần từ hoạt động kinh doanh",
            item_code=None,
            cur_val=Decimal("50000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="income_statement",
        )
        assert p_op.canonical_key == "operating_profit"

        # Profit before tax
        p_pbt = parser.map_line_item(
            raw_label="Tổng lợi nhuận kế toán trước thuế",
            item_code=None,
            cur_val=Decimal("55000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="income_statement",
        )
        assert p_pbt.canonical_key == "net_profit_before_tax"

        # Profit after tax
        p_pat = parser.map_line_item(
            raw_label="Lợi nhuận sau thuế thu nhập doanh nghiệp",
            item_code=None,
            cur_val=Decimal("44000000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="income_statement",
        )
        assert p_pat.canonical_key == "net_profit_after_tax"

    def test_disambiguation_between_assets_and_liabilities(self):
        parser = FinancialStatementParser()

        # Short term vs Long term assets
        item_ca = parser.map_line_item("Tài sản ngắn hạn", None, Decimal("100"), None, "VND", 1, "balance_sheet")
        item_nca = parser.map_line_item("Tài sản dài hạn", None, Decimal("200"), None, "VND", 1, "balance_sheet")
        assert item_ca.canonical_key == "current_assets"
        assert item_nca.canonical_key == "non_current_assets"

        # Short term vs Long term liabilities
        item_cl = parser.map_line_item("Nợ ngắn hạn", None, Decimal("50"), None, "VND", 1, "balance_sheet")
        item_ncl = parser.map_line_item("Nợ dài hạn", None, Decimal("30"), None, "VND", 1, "balance_sheet")
        assert item_cl.canonical_key == "current_liabilities"
        assert item_ncl.canonical_key == "non_current_liabilities"

    def test_unmapped_and_ambiguous_line_item(self):
        parser = FinancialStatementParser()
        item_unknown = parser.map_line_item(
            raw_label="Khoản mục bất thường không có trong từ điển",
            item_code=None,
            cur_val=Decimal("1000"),
            prev_val=None,
            unit="VND",
            source_page=1,
            context="balance_sheet",
        )
        assert item_unknown.canonical_key is None
        assert item_unknown.mapping_status == MappingStatus.UNMAPPED
        assert item_unknown.mapping_method == MappingMethod.UNMAPPED

    def test_parsing_from_html_table(self):
        html_snippet = (
            "CÔNG TY CỔ PHẦN 32\n"
            "BÁNG CÂN ĐỐI KẾ TOÁN TẠI NGÀY 31/12/2020\n"
            "Đơn vị tính: VND\n"
            "<table>"
            "<tr><td>TÀI SẢN NGẮN HẠN</td><td>100</td><td>356.691.280.424</td><td>298.767.972.671</td></tr>"
            "<tr><td>Tiền và các khoản tương đương tiền</td><td>110</td><td>44.359.080.786</td><td>60.513.753.437</td></tr>"
            "<tr><td>TỔNG CỘNG TÀI SẢN</td><td>270</td><td>488.295.453.917</td><td>434.930.314.417</td></tr>"
            "</table>"
        )
        parser = FinancialStatementParser()
        report = parser.parse(html_snippet, source_name="test_a32.txt")

        assert report.unit == "VND"
        assert report.fiscal_year == 2020
        assert report.company_name is not None
        assert "CÔNG TY CỔ PHẦN 32" in report.company_name

        bs = report.balance_sheet
        assert bs is not None
        assert bs.current_assets == Decimal("356691280424")
        assert bs.cash_and_equivalents == Decimal("44359080786")
        assert bs.total_assets == Decimal("488295453917")

    def test_integration_with_document_extraction_result(self):
        # Create a mock DocumentExtractionResult like from Sprint 2
        page1 = PageExtractionResult(
            source_name="report.pdf",
            page_number=1,
            text=(
                "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH NĂM 2020\n"
                "Đơn vị tính: triệu đồng\n"
                "1. Doanh thu bán hàng và cung cấp dịch vụ   01   500.000   450.000\n"
                "2. Các khoản giảm trừ doanh thu            02   0         0\n"
                "3. Doanh thu thuần về bán hàng             10   500.000   450.000\n"
                "4. Giá vốn hàng bán                        11   380.000   350.000\n"
                "5. Lợi nhuận gộp về bán hàng               20   120.000   100.000\n"
            ),
        )
        doc_res = DocumentExtractionResult(
            source_name="report.pdf",
            total_pages=1,
            pages=[page1],
        )

        parser = FinancialStatementParser()
        report = parser.parse(doc_res)

        assert report.unit == "triệu VND"
        assert report.income_statement is not None
        is_ = report.income_statement

        assert is_.gross_revenue == Decimal("500000")
        assert is_.net_revenue == Decimal("500000")
        assert is_.cost_of_goods_sold == Decimal("380000")
        assert is_.gross_profit == Decimal("120000")

    def test_note_reference_filtering_in_table_row(self):
        # Rows with note references like "VI.1." between code and amount
        table_snippet = (
            "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH\n"
            "<table>\n"
            "<tr><td>1. Doanh thu bán hàng</td><td>01</td><td>VI.1.</td><td>728.582.496.415</td><td>691.485.702.395</td></tr>\n"
            "<tr><td>4. Giá vốn hàng bán</td><td>11</td><td>VI.3.</td><td>648.984.925.398</td><td>609.205.657.982</td></tr>\n"
            "</table>"
        )
        parser = FinancialStatementParser()
        report = parser.parse(table_snippet)
        is_ = report.income_statement

        assert is_.gross_revenue == Decimal("728582496415")
        assert is_.items["gross_revenue"].previous_period_value == Decimal("691485702395")
        assert is_.cost_of_goods_sold == Decimal("648984925398")
        assert is_.items["cost_of_goods_sold"].previous_period_value == Decimal("609205657982")

    def test_notes_section_does_not_overwrite_primary_statements(self):
        doc_text = (
            "===== PAGE 8 =====\n"
            "CÔNG TY CỔ PHẦN 32\n"
            "Mẫu số B 01 - DN\n"
            "BẢNG CÂN ĐỐI KẾ TOÁN\n"
            "<table>\n"
            "<tr><td>A</td><td>TÀI SẢN NGẮN HẠN</td><td>100</td><td></td><td>356.691.280.424</td><td>298.767.972.671</td></tr>\n"
            "<tr><td colspan='2'>TỔNG CỘNG TÀI SẢN</td><td>270</td><td></td><td>488.295.453.917</td><td>434.930.314.417</td></tr>\n"
            "</table>\n"
            "===== PAGE 12 =====\n"
            "Mẫu số B 09 - DN\n"
            "BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH\n"
            "<table>\n"
            "<tr><td>Chi tiết khoản mục con</td><td>100</td><td>999.999</td><td>888.888</td></tr>\n"
            "</table>\n"
        )
        parser = FinancialStatementParser()
        report = parser.parse(doc_text)
        bs = report.balance_sheet

        # Primary value from Page 8 must NOT be overwritten by Page 12 (notes)
        assert bs.current_assets == Decimal("356691280424")
        assert bs.total_assets == Decimal("488295453917")
