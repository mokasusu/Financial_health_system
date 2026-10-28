"""Unit tests for FinancialLexiconCorrector and Image Enhancement pipeline."""
from decimal import Decimal
import numpy as np
import pytest

from src.application.services.parsing_service import FinancialStatementParser
from src.domain.accounting.lexicon import FinancialLexiconCorrector
from src.domain.models.line_item import MappingStatus
from src.infrastructure.ocr.preprocessor import ImagePreprocessor


class TestFinancialLexiconCorrector:
    """Test Vietnamese financial statement fuzzy text correction."""

    @pytest.mark.parametrize(
        "raw_input,item_code,context,expected_label",
        [
            ("Tài sn ngn hn", "100", "balance_sheet", "Tài sản ngắn hạn"),
            ("Tài sn ngn hn", None, "balance_sheet", "Tài sản ngắn hạn"),
            ("Tài sn ngn hn", None, "unknown", "Tài sản ngắn hạn"),
            ("Li nhun thun t hot dng kinh doanh", "30", "income_statement", "Lợi nhuận thuần từ hoạt động kinh doanh"),
            ("Li nhun thun t hot dng kinh doanh", None, "income_statement", "Lợi nhuận thuần từ hoạt động kinh doanh"),
            ("VN CH S HU", "400", "balance_sheet", "Vốn chủ sở hữu"),
            ("VN CH S HU", None, "balance_sheet", "Vốn chủ sở hữu"),
            ("N PHI TRÅ", "300", "balance_sheet", "Nợ phải trả"),
            ("Doanh thu hot dng tài chính", "21", "income_statement", "Doanh thu hoạt động tài chính"),
            ("Tài sn dài hn khác", "260", "balance_sheet", "Tài sản dài hạn khác"),
            ("Giá vn hàng bán", "11", "income_statement", "Giá vốn hàng bán"),
            ("Chi phí qun lý doanh nghip", "26", "income_statement", "Chi phí quản lý doanh nghiệp"),
            ("Tng li nhun k toán trưc thu", "50", "income_statement", "Tổng lợi nhuận kế toán trước thuế"),
        ],
    )
    def test_fuzzy_correction_typical_ocr_errors(self, raw_input, item_code, context, expected_label):
        corrected, is_corrected = FinancialLexiconCorrector.correct_label(
            raw_label=raw_input,
            item_code=item_code,
            context=context,
        )
        assert is_corrected is True
        assert corrected == expected_label

    def test_antipattern_safety_guards(self):
        """Verify safety guards prevent false-positive corrections on distinct items."""
        # 'Tài sản dài hạn khác' (Code 200 has antipattern 'khac')
        # It must NOT be wrongly corrected to 'Tài sản dài hạn' (Code 200)
        corrected, is_corr = FinancialLexiconCorrector.correct_label(
            raw_label="Tài sản dài hạn khác",
            item_code="200",
            context="balance_sheet",
        )
        assert corrected != "Tài sản dài hạn"

        # 'Nợ ngắn hạn' with code 330 (Nợ dài hạn) must NOT be forced into Nợ dài hạn
        corrected, is_corr = FinancialLexiconCorrector.correct_label(
            raw_label="Nợ ngắn hạn",
            item_code="330",
            context="balance_sheet",
        )
        assert corrected != "Nợ dài hạn"

    def test_unrelated_text_not_mangled(self):
        """Custom unmapped lines or company notes should not be wrongly corrected."""
        custom_line = "Doanh thu cho thuê kho bãi phụ trợ Tân Bình"
        corrected, is_corr = FinancialLexiconCorrector.correct_label(
            raw_label=custom_line,
            item_code=None,
            context="unknown",
        )
        assert is_corr is False
        assert corrected == custom_line

    def test_full_parser_integration_with_corrupted_ocr(self):
        """Verify parser end-to-end converts corrupted OCR text to canonical items."""
        parser = FinancialStatementParser()
        mock_ocr_text = """
===== PAGE 1 =====
BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
Mẫu B 02 - DN
Chỉ tiêu\tMã số\tNăm nay\tNăm trước
Doanh thu thun v bán hàng\t10\t120.000.000\t100.000.000
Giá vn hàng bán\t11\t80.000.000\t70.000.000
Li nhun gp v bán hàng\t20\t40.000.000\t30.000.000
Li nhun thun t hot dng kinh doanh\t30\t15.000.000\t12.000.000
Tng li nhun k toán trưc thu\t50\t18.000.000\t14.000.000
Li nhun sau thu TNDN\t60\t14.400.000\t11.200.000
"""
        report = parser.parse(mock_ocr_text, source_name="corrupted_ocr_test.txt")
        assert report.income_statement is not None

        # Check net_revenue mapped correctly
        net_rev = report.income_statement.items.get("net_revenue")
        assert net_rev is not None
        assert net_rev.mapping_status == MappingStatus.MAPPED
        assert "Doanh thu thuần" in net_rev.normalized_label

        # Check operating_profit mapped correctly
        op_prof = report.income_statement.items.get("operating_profit")
        assert op_prof is not None
        assert op_prof.mapping_status == MappingStatus.MAPPED
        assert op_prof.normalized_label == "Lợi nhuận thuần từ hoạt động kinh doanh"

        # Check net_profit_after_tax mapped correctly
        npat = report.income_statement.items.get("net_profit_after_tax")
        assert npat is not None
        assert npat.mapping_status == MappingStatus.MAPPED
        assert "Lợi nhuận sau thuế" in npat.normalized_label


class TestImageEnhancement:
    """Test Stage 1 Image Preprocessor Document Text Enhancement."""

    def test_enhance_document_text(self):
        preprocessor = ImagePreprocessor()
        # Create synthetic low contrast image
        img = np.full((300, 400, 3), 180, dtype=np.uint8)
        # Add a dark line representing text
        img[140:160, 50:350] = 50

        enhanced = preprocessor.enhance_document_text(img)
        assert enhanced.shape == img.shape
        assert enhanced.dtype == np.uint8
        # Standard deviation or contrast should increase after unsharp mask and CLAHE
        assert enhanced.std() >= img.std()
