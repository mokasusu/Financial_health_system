"""Unit tests for AccountingNumberNormalizer."""
from decimal import Decimal
import pytest
from src.domain.accounting.normalizer import AccountingNumberNormalizer, NumberStatus


class TestAccountingNumberNormalizer:
    """Test number normalization rules and edge cases."""

    def test_positive_integers_and_standard_separators(self):
        # Vietnamese format: dot thousands separator
        res1 = AccountingNumberNormalizer.parse("356.691.280.424")
        assert res1.is_valid is True
        assert res1.value == Decimal("356691280424")
        assert res1.status == NumberStatus.VALID

        # Space thousands separator
        res2 = AccountingNumberNormalizer.parse("123 456 789")
        assert res2.is_valid is True
        assert res2.value == Decimal("123456789")

        # Plain digits
        res3 = AccountingNumberNormalizer.parse("5000000")
        assert res3.is_valid is True
        assert res3.value == Decimal("5000000")

    def test_parenthesized_negative_numbers(self):
        # Vietnamese standard accounting negative e.g. (1.070.569.223)
        res1 = AccountingNumberNormalizer.parse("(1.070.569.223)")
        assert res1.is_valid is True
        assert res1.is_negative is True
        assert res1.value == Decimal("-1070569223")

        # Plain parentheses negative
        res2 = AccountingNumberNormalizer.parse("(50000)")
        assert res2.is_valid is True
        assert res2.value == Decimal("-50000")

        # Trailing minus
        res3 = AccountingNumberNormalizer.parse("15.000-")
        assert res3.is_valid is True
        assert res3.value == Decimal("-15000")

    def test_dash_not_applicable_vs_zero(self):
        # Dash '-' indicates zero balance or non-applicable line
        res_dash = AccountingNumberNormalizer.parse("-", treat_dash_as_zero=True)
        assert res_dash.status == NumberStatus.DASH_NOT_APPLICABLE
        assert res_dash.is_valid is True
        assert res_dash.value == Decimal("0")

        # Em-dash
        res_emdash = AccountingNumberNormalizer.parse("—", treat_dash_as_zero=True)
        assert res_emdash.status == NumberStatus.DASH_NOT_APPLICABLE
        assert res_emdash.value == Decimal("0")

        # Explicit 0
        res_zero = AccountingNumberNormalizer.parse("0")
        assert res_zero.status == NumberStatus.VALID
        assert res_zero.value == Decimal("0")

    def test_missing_and_empty_cells(self):
        res_empty = AccountingNumberNormalizer.parse("")
        assert res_empty.status == NumberStatus.MISSING
        assert res_empty.value is None
        assert res_empty.is_valid is False

        res_none = AccountingNumberNormalizer.parse(None)
        assert res_none.status == NumberStatus.MISSING
        assert res_none.value is None

        res_spaces = AccountingNumberNormalizer.parse("   ")
        assert res_spaces.status == NumberStatus.MISSING
        assert res_spaces.value is None

    def test_ambiguous_ocr_characters_not_guessed(self):
        # String with letter O inside digits - must not guess 0
        res1 = AccountingNumberNormalizer.parse("12O.345")
        assert res1.status == NumberStatus.AMBIGUOUS
        assert res1.value is None
        assert res1.is_valid is False
        assert any("Ambiguous OCR characters" in w for w in res1.warnings)

        # String with letter l/I
        res2 = AccountingNumberNormalizer.parse("45I.000")
        assert res2.status == NumberStatus.AMBIGUOUS
        assert res2.value is None

    def test_decimal_convention_handling(self):
        # Vietnamese convention: comma as decimal, dot as thousands
        res_vi = AccountingNumberNormalizer.parse("1.234,50", decimal_convention="vi")
        assert res_vi.is_valid is True
        assert res_vi.value == Decimal("1234.50")

        # US convention: dot as decimal, comma as thousands
        res_us = AccountingNumberNormalizer.parse("1,234.50", decimal_convention="us")
        assert res_us.is_valid is True
        assert res_us.value == Decimal("1234.50")

    def test_unit_scaling(self):
        # Scaling millions to base VND
        res1 = AccountingNumberNormalizer.parse("250", unit="triệu VND", scale_to_base_vnd=True)
        assert res1.is_valid is True
        assert res1.value == Decimal("250000000")  # 250 * 1,000,000

        # Scaling billions to base VND
        res2 = AccountingNumberNormalizer.parse("10.5", unit="tỷ VND", scale_to_base_vnd=True)
        assert res2.is_valid is True
        assert res2.value == Decimal("10500000000")  # 10.5 * 1,000,000,000

    def test_clean_label_utility(self):
        assert AccountingNumberNormalizer.clean_label("A. TÀI SẢN NGẮN HẠN") == "tài sản ngắn hạn"
        assert AccountingNumberNormalizer.clean_label("I. Tiền và các khoản tương đương tiền") == "tiền và các khoản tương đương tiền"
        assert AccountingNumberNormalizer.clean_label("1. Tiền (*)") == "tiền"
        assert AccountingNumberNormalizer.clean_label("<td>2. Các khoản tương đương tiền</td>") == "các khoản tương đương tiền"
        assert AccountingNumberNormalizer.clean_label("  Dự phòng giảm giá (*)  ") == "dự phòng giảm giá"

    def test_currency_symbol_stripping_and_detection(self):
        # VND suffix
        res_vnd = AccountingNumberNormalizer.parse("500.000 VND")
        assert res_vnd.is_valid is True
        assert res_vnd.value == Decimal("500000")
        assert res_vnd.unit == "VND"

        # Dong symbol
        res_dong = AccountingNumberNormalizer.parse("1.250.000 đ")
        assert res_dong.is_valid is True
        assert res_dong.value == Decimal("1250000")
        assert res_dong.unit == "VND"

        # Dollar prefix
        res_usd = AccountingNumberNormalizer.parse("$1,500.50", decimal_convention="us")
        assert res_usd.is_valid is True
        assert res_usd.value == Decimal("1500.50")
        assert res_usd.unit == "USD"

    def test_invalid_digit_grouping_rejected(self):
        # Format 12.34.56 has non-3 digit groups and must be flagged INVALID
        res = AccountingNumberNormalizer.parse("12.34.56")
        assert res.is_valid is False
        assert res.status == NumberStatus.INVALID

    def test_prevent_double_scaling(self):
        # Scaling already converted to VND should not re-scale
        res = AccountingNumberNormalizer.parse("100", unit="triệu VND", scale_to_base_vnd=True)
        assert res.value == Decimal("100000000")
        assert res.unit == "VND"
        # If passed again with unit="VND", it stays 100000000
        res2 = AccountingNumberNormalizer.parse(str(res.value), unit=res.unit, scale_to_base_vnd=True)
        assert res2.value == Decimal("100000000")
