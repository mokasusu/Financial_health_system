"""Unit tests for FinancialValidator and accounting equation validation."""
from decimal import Decimal
import pytest
from src.domain.models.bctc import (
    BalanceSheet,
    CheckStatus,
    FinancialReport,
    IncomeStatement,
)
from src.domain.models.line_item import LineItem
from src.domain.accounting.validator import FinancialValidator


class TestFinancialValidator:
    """Test accounting identities, rounding tolerance, and incomplete data handling."""

    def test_balance_sheet_perfect_balance(self):
        bs = BalanceSheet()
        bs.items["total_assets"] = LineItem(
            raw_label="TỔNG CỘNG TÀI SẢN",
            normalized_label="tổng cộng tài sản",
            canonical_key="total_assets",
            current_period_value=Decimal("500000000000"),
        )
        bs.items["total_equity_and_liabilities"] = LineItem(
            raw_label="TỔNG CỘNG NGUỒN VỐN",
            normalized_label="tổng cộng nguồn vốn",
            canonical_key="total_equity_and_liabilities",
            current_period_value=Decimal("500000000000"),
        )
        bs.items["current_assets"] = LineItem(
            raw_label="Tài sản ngắn hạn",
            normalized_label="tài sản ngắn hạn",
            canonical_key="current_assets",
            current_period_value=Decimal("300000000000"),
        )
        bs.items["non_current_assets"] = LineItem(
            raw_label="Tài sản dài hạn",
            normalized_label="tài sản dài hạn",
            canonical_key="non_current_assets",
            current_period_value=Decimal("200000000000"),
        )

        report = FinancialReport(balance_sheet=bs)
        validator = FinancialValidator(tolerance=Decimal("1000"))
        res = validator.validate(report)

        assert res.is_valid is True
        assert res.failed_checks == 0

        # Check BS_EQ_01
        eq01 = next(c for c in res.checks if c.check_id == "BS_EQ_01")
        assert eq01.status == CheckStatus.PASS
        assert eq01.difference == Decimal("0")

        # Check BS_EQ_02 (300k + 200k == 500k)
        eq02 = next(c for c in res.checks if c.check_id == "BS_EQ_02")
        assert eq02.status == CheckStatus.PASS

    def test_balance_sheet_rounding_difference_within_tolerance(self):
        bs = BalanceSheet()
        # 100 VND difference due to rounding
        bs.items["total_assets"] = LineItem(
            raw_label="TỔNG TÀI SẢN",
            normalized_label="tổng tài sản",
            canonical_key="total_assets",
            current_period_value=Decimal("1000000100"),
        )
        bs.items["total_equity_and_liabilities"] = LineItem(
            raw_label="TỔNG NGUỒN VỐN",
            normalized_label="tổng nguồn vốn",
            canonical_key="total_equity_and_liabilities",
            current_period_value=Decimal("1000000000"),
        )

        report = FinancialReport(balance_sheet=bs)
        validator = FinancialValidator(tolerance=Decimal("1000"))  # Tolerance 1000 >= 100
        res = validator.validate(report)

        eq01 = next(c for c in res.checks if c.check_id == "BS_EQ_01")
        assert eq01.status == CheckStatus.PASS
        assert eq01.difference == Decimal("100")
        assert res.is_valid is True

    def test_balance_sheet_unbalanced_failure(self):
        bs = BalanceSheet()
        # 50,000,000 difference > 1,000 tolerance
        bs.items["total_assets"] = LineItem(
            raw_label="TỔNG TÀI SẢN",
            normalized_label="tổng tài sản",
            canonical_key="total_assets",
            current_period_value=Decimal("500000000000"),
        )
        bs.items["total_equity_and_liabilities"] = LineItem(
            raw_label="TỔNG NGUỒN VỐN",
            normalized_label="tổng nguồn vốn",
            canonical_key="total_equity_and_liabilities",
            current_period_value=Decimal("450000000000"),
        )

        report = FinancialReport(balance_sheet=bs)
        validator = FinancialValidator(tolerance=Decimal("1000"))
        res = validator.validate(report)

        assert res.is_valid is False
        assert res.failed_checks >= 1

        eq01 = next(c for c in res.checks if c.check_id == "BS_EQ_01")
        assert eq01.status == CheckStatus.FAIL
        assert eq01.difference == Decimal("50000000000")

    def test_not_checkable_when_data_missing(self):
        bs = BalanceSheet()
        # Only total assets is present; liabilities and equity are missing
        bs.items["total_assets"] = LineItem(
            raw_label="TỔNG TÀI SẢN",
            normalized_label="tổng tài sản",
            canonical_key="total_assets",
            current_period_value=Decimal("500000000"),
        )

        report = FinancialReport(balance_sheet=bs)
        validator = FinancialValidator()
        res = validator.validate(report)

        eq01 = next(c for c in res.checks if c.check_id == "BS_EQ_01")
        assert eq01.status == CheckStatus.NOT_CHECKABLE
        assert "thiếu Tổng Nguồn vốn" in eq01.message

        # Missing data must not be falsely treated as FAIL or 0
        assert eq01.status != CheckStatus.FAIL
        assert eq01.difference is None

    def test_income_statement_identities(self):
        is_ = IncomeStatement()
        is_.items["gross_revenue"] = LineItem(
            raw_label="Doanh thu bán hàng",
            normalized_label="doanh thu bán hàng",
            canonical_key="gross_revenue",
            current_period_value=Decimal("1000000"),
        )
        is_.items["revenue_deductions"] = LineItem(
            raw_label="Giảm trừ doanh thu",
            normalized_label="giảm trừ doanh thu",
            canonical_key="revenue_deductions",
            current_period_value=Decimal("50000"),
        )
        is_.items["net_revenue"] = LineItem(
            raw_label="Doanh thu thuần",
            normalized_label="doanh thu thuần",
            canonical_key="net_revenue",
            current_period_value=Decimal("950000"),  # 1,000,000 - 50,000
        )
        is_.items["cost_of_goods_sold"] = LineItem(
            raw_label="Giá vốn hàng bán",
            normalized_label="giá vốn hàng bán",
            canonical_key="cost_of_goods_sold",
            current_period_value=Decimal("700000"),
        )
        is_.items["gross_profit"] = LineItem(
            raw_label="Lợi nhuận gộp",
            normalized_label="lợi nhuận gộp",
            canonical_key="gross_profit",
            current_period_value=Decimal("250000"),  # 950,000 - 700,000
        )

        report = FinancialReport(income_statement=is_)
        validator = FinancialValidator()
        res = validator.validate(report)

        eq_net_rev = next(c for c in res.checks if c.check_id == "IS_EQ_01")
        assert eq_net_rev.status == CheckStatus.PASS

        eq_gross_profit = next(c for c in res.checks if c.check_id == "IS_EQ_02")
        assert eq_gross_profit.status == CheckStatus.PASS
