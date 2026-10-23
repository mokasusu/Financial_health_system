"""Unit tests for Financial Ratio Engine (Sprint 4A).

Verifies all 14 standard financial ratios across Liquidity, Leverage, Efficiency, and Profitability,
ensuring Decimal precision, defensive zero/negative division, average balance integrity,
audit provenance tracking, and edge case handling.
"""
from decimal import Decimal
from typing import Optional
import pytest

from src.data.parser import FinancialStatementParser
from src.data.schema import (
    BalanceSheet,
    FinancialReport,
    IncomeStatement,
    LineItem,
    MappingMethod,
    MappingStatus,
)
from src.financial.ratios import (
    FinancialRatioCalculator,
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
)


def _make_line_item(
    canonical_key: str,
    raw_label: str,
    cur_val: Optional[Decimal] = None,
    prev_val: Optional[Decimal] = None,
    status: MappingStatus = MappingStatus.MAPPED,
) -> LineItem:
    """Helper to construct LineItem fixture."""
    return LineItem(
        raw_label=raw_label,
        normalized_label=raw_label.lower(),
        canonical_key=canonical_key,
        current_period_value=cur_val,
        previous_period_value=prev_val,
        mapping_method=MappingMethod.CODE_EXACT,
        mapping_status=status,
        confidence_score=0.95 if status == MappingStatus.MAPPED else 0.50,
    )


@pytest.fixture
def clean_financial_report() -> FinancialReport:
    """Construct a clean, valid FinancialReport fixture with known hand-verifiable numbers."""
    bs = BalanceSheet()
    # Assets
    bs.items["current_assets"] = _make_line_item("current_assets", "Tài sản ngắn hạn", Decimal("1000"), Decimal("800"))
    bs.items["cash_and_equivalents"] = _make_line_item("cash_and_equivalents", "Tiền", Decimal("100"), Decimal("150"))
    bs.items["inventory"] = _make_line_item("inventory", "Hàng tồn kho", Decimal("200"), Decimal("160"))
    bs.items["short_term_receivables"] = _make_line_item("short_term_receivables", "Phải thu ngắn hạn", Decimal("320"), Decimal("280"))
    bs.items["non_current_assets"] = _make_line_item("non_current_assets", "Tài sản dài hạn", Decimal("1000"), Decimal("800"))
    bs.items["total_assets"] = _make_line_item("total_assets", "Tổng tài sản", Decimal("2000"), Decimal("1600"))

    # Liabilities & Equity
    bs.items["current_liabilities"] = _make_line_item("current_liabilities", "Nợ ngắn hạn", Decimal("500"), Decimal("400"))
    bs.items["liabilities"] = _make_line_item("liabilities", "Nợ phải trả", Decimal("800"), Decimal("600"))
    bs.items["equity"] = _make_line_item("equity", "Vốn chủ sở hữu", Decimal("1200"), Decimal("1000"))
    bs.items["total_equity_and_liabilities"] = _make_line_item("total_equity_and_liabilities", "Tổng nguồn vốn", Decimal("2000"), Decimal("1600"))

    # Income Statement
    is_ = IncomeStatement()
    is_.items["gross_revenue"] = _make_line_item("gross_revenue", "Doanh thu bán hàng", Decimal("3600"), Decimal("3000"))
    is_.items["net_revenue"] = _make_line_item("net_revenue", "Doanh thu thuần", Decimal("3600"), Decimal("3000"))
    is_.items["cost_of_goods_sold"] = _make_line_item("cost_of_goods_sold", "Giá vốn hàng bán", Decimal("2400"), Decimal("2000"))
    is_.items["gross_profit"] = _make_line_item("gross_profit", "Lợi nhuận gộp", Decimal("1200"), Decimal("1000"))
    is_.items["operating_profit"] = _make_line_item("operating_profit", "Lợi nhuận thuần HĐKD", Decimal("360"), Decimal("300"))
    is_.items["net_profit_after_tax"] = _make_line_item("net_profit_after_tax", "Lợi nhuận sau thuế", Decimal("270"), Decimal("200"))

    return FinancialReport(
        company_name="CÔNG TY CỔ PHẦN THỬ NGHIỆM",
        fiscal_year=2020,
        unit="VND",
        balance_sheet=bs,
        income_statement=is_,
    )


class TestFinancialRatioCalculator:
    """Test suite for financial ratio calculations."""

    def test_all_14_ratios_hand_calculated_accuracy(self, clean_financial_report):
        calculator = FinancialRatioCalculator()
        report: FinancialRatioReport = calculator.calculate_all(clean_financial_report)

        assert report.total_ratios == 14
        assert report.calculated_ratios == 14
        assert report.not_available_ratios == 0
        assert report.undefined_ratios == 0

        # 1. Current Ratio = 1000 / 500 = 2.00
        cr = report.get_ratio("current_ratio")
        assert cr is not None
        assert cr.status == RatioStatus.CALCULATED
        assert cr.value == Decimal("2")
        assert cr.formatted_value == "2.00 lần"
        assert cr.input_keys == ["current_assets", "current_liabilities"]

        # 2. Quick Ratio = (1000 - 200) / 500 = 1.60
        qr = report.get_ratio("quick_ratio")
        assert qr is not None
        assert qr.status == RatioStatus.CALCULATED
        assert qr.value == Decimal("1.6")
        assert qr.formatted_value == "1.60 lần"

        # 3. Cash Ratio = 100 / 500 = 0.20
        cash_r = report.get_ratio("cash_ratio")
        assert cash_r is not None
        assert cash_r.status == RatioStatus.CALCULATED
        assert cash_r.value == Decimal("0.2")
        assert cash_r.formatted_value == "0.20 lần"

        # 4. Debt to Assets = 800 / 2000 = 0.40 (40.00%)
        dta = report.get_ratio("debt_to_assets")
        assert dta is not None
        assert dta.status == RatioStatus.CALCULATED
        assert dta.value == Decimal("0.4")
        assert dta.formatted_value == "40.00%"

        # 5. Debt to Equity = 800 / 1200 = 2/3 = 0.6666...
        dte = report.get_ratio("debt_to_equity")
        assert dte is not None
        assert dte.status == RatioStatus.CALCULATED
        assert dte.value == Decimal("800") / Decimal("1200")
        assert dte.formatted_value == "0.67 lần"

        # 6. Equity Ratio = 1200 / 2000 = 0.60 (60.00%)
        er = report.get_ratio("equity_ratio")
        assert er is not None
        assert er.status == RatioStatus.CALCULATED
        assert er.value == Decimal("0.6")
        assert er.formatted_value == "60.00%"

        # 7. Total Asset Turnover = 3600 / ((1600 + 2000)/2 = 1800) = 2.00 vòng
        tat = report.get_ratio("total_asset_turnover")
        assert tat is not None
        assert tat.status == RatioStatus.CALCULATED
        assert tat.value == Decimal("2")
        assert tat.formatted_value == "2.00 vòng"

        # 8. Inventory Turnover = 2400 / ((160 + 200)/2 = 180) = 13.3333... vòng
        it = report.get_ratio("inventory_turnover")
        assert it is not None
        assert it.status == RatioStatus.CALCULATED
        assert it.value == Decimal("2400") / Decimal("180")
        assert it.formatted_value == "13.33 vòng"

        # 9. Receivables Turnover = 3600 / ((280 + 320)/2 = 300) = 12.00 vòng
        rt = report.get_ratio("receivables_turnover")
        assert rt is not None
        assert rt.status == RatioStatus.CALCULATED
        assert rt.value == Decimal("12")
        assert rt.formatted_value == "12.00 vòng"

        # 10. Gross Profit Margin = 1200 / 3600 = 33.33%
        gpm = report.get_ratio("gross_profit_margin")
        assert gpm is not None
        assert gpm.status == RatioStatus.CALCULATED
        assert gpm.value == Decimal("1200") / Decimal("3600")
        assert gpm.formatted_value == "33.33%"

        # 11. Operating Profit Margin = 360 / 3600 = 10.00%
        opm = report.get_ratio("operating_profit_margin")
        assert opm is not None
        assert opm.status == RatioStatus.CALCULATED
        assert opm.value == Decimal("0.1")
        assert opm.formatted_value == "10.00%"

        # 12. Net Profit Margin = 270 / 3600 = 7.50%
        npm = report.get_ratio("net_profit_margin")
        assert npm is not None
        assert npm.status == RatioStatus.CALCULATED
        assert npm.value == Decimal("0.075")
        assert npm.formatted_value == "7.50%"

        # 13. ROA = 270 / 1800 = 15.00%
        roa = report.get_ratio("roa")
        assert roa is not None
        assert roa.status == RatioStatus.CALCULATED
        assert roa.value == Decimal("270") / Decimal("1800")
        assert roa.formatted_value == "15.00%"

        # 14. ROE = 270 / ((1000 + 1200)/2 = 1100) = 24.55%
        roe = report.get_ratio("roe")
        assert roe is not None
        assert roe.status == RatioStatus.CALCULATED
        assert roe.value == Decimal("270") / Decimal("1100")
        assert roe.formatted_value == "24.55%"

    def test_missing_required_data_returns_not_available(self):
        """When an essential input is None, ratio is NOT_AVAILABLE, not zero."""
        bs = BalanceSheet()
        # Only current_assets provided, current_liabilities is missing
        bs.items["current_assets"] = _make_line_item("current_assets", "TSNH", Decimal("500"))

        calc = FinancialRatioCalculator()
        liq = calc.calculate_liquidity(bs)

        cr = liq["current_ratio"]
        assert cr.status == RatioStatus.NOT_AVAILABLE
        assert cr.value is None
        assert cr.formatted_value == "N/A"
        assert any("Nợ ngắn hạn" in w for w in cr.warnings)

    def test_distinguish_zero_from_none(self):
        """A cash amount of 0 is valid numeric zero, not missing None."""
        bs = BalanceSheet()
        bs.items["cash_and_equivalents"] = _make_line_item("cash_and_equivalents", "Tiền", Decimal("0"))
        bs.items["current_liabilities"] = _make_line_item("current_liabilities", "Nợ ngắn hạn", Decimal("200"))

        calc = FinancialRatioCalculator()
        liq = calc.calculate_liquidity(bs)

        cash_r = liq["cash_ratio"]
        assert cash_r.status == RatioStatus.CALCULATED
        assert cash_r.value == Decimal("0")
        assert cash_r.formatted_value == "0.00 lần"

    def test_zero_denominator_no_division_error(self):
        """Zero denominator must return NOT_APPLICABLE without raising ZeroDivisionError."""
        bs = BalanceSheet()
        bs.items["current_assets"] = _make_line_item("current_assets", "TSNH", Decimal("500"))
        bs.items["current_liabilities"] = _make_line_item("current_liabilities", "Nợ ngắn hạn", Decimal("0"))

        calc = FinancialRatioCalculator()
        liq = calc.calculate_liquidity(bs)

        cr = liq["current_ratio"]
        assert cr.status == RatioStatus.NOT_APPLICABLE
        assert cr.value is None
        assert cr.formatted_value == "N/A"
        assert any("Mẫu số bằng 0" in w for w in cr.warnings)

    def test_negative_equity_in_debt_to_equity(self):
        """When equity is negative, ratio is flagged UNDEFINED with explanatory warning."""
        bs = BalanceSheet()
        bs.items["liabilities"] = _make_line_item("liabilities", "Nợ phải trả", Decimal("1000"))
        bs.items["equity"] = _make_line_item("equity", "VCSH", Decimal("-200"))
        bs.items["total_assets"] = _make_line_item("total_assets", "Tổng tài sản", Decimal("800"))

        calc = FinancialRatioCalculator()
        lev = calc.calculate_leverage(bs)

        dte = lev["debt_to_equity"]
        assert dte.status == RatioStatus.UNDEFINED
        assert dte.value == Decimal("1000") / Decimal("-200")
        assert any("Vốn chủ sở hữu âm" in w for w in dte.warnings)

    def test_negative_equity_and_negative_npat_roe_trap(self):
        """Mathematical positive ROE from (-NPAT) / (-Equity) must be marked UNDEFINED."""
        bs = BalanceSheet()
        # Average equity is negative (-300 + -500)/2 = -400
        bs.items["equity"] = _make_line_item("equity", "VCSH", Decimal("-500"), Decimal("-300"))
        is_ = IncomeStatement()
        # Loss of 80
        is_.items["net_profit_after_tax"] = _make_line_item("net_profit_after_tax", "LNST", Decimal("-80"))
        is_.items["net_revenue"] = _make_line_item("net_revenue", "DTT", Decimal("1000"))

        calc = FinancialRatioCalculator()
        prof = calc.calculate_profitability(bs, is_)

        roe = prof["roe"]
        # (-80) / (-400) = +0.20 (+20%) mathematically
        assert roe.value == Decimal("0.2")
        assert roe.status == RatioStatus.UNDEFINED
        assert any("Vốn chủ sở hữu bình quân âm và Lợi nhuận sau thuế âm" in w for w in roe.warnings)

    def test_missing_beginning_balance_prevents_silent_fallback(self):
        """If beginning balance is missing, turnover ratios must NOT silently fall back to ending balance."""
        bs = BalanceSheet()
        # Has current period 1000, but previous period is None!
        bs.items["total_assets"] = _make_line_item("total_assets", "TTS", Decimal("1000"), None)
        is_ = IncomeStatement()
        is_.items["net_revenue"] = _make_line_item("net_revenue", "DTT", Decimal("2000"))

        calc = FinancialRatioCalculator()
        eff = calc.calculate_efficiency(bs, is_)

        tat = eff["total_asset_turnover"]
        assert tat.status == RatioStatus.NOT_AVAILABLE
        assert tat.value is None
        assert any("Thiếu số dư đầu kỳ" in w for w in tat.warnings)

    def test_line_item_needing_review_propagates_warning(self):
        """If input line item has MappingStatus.NEEDS_REVIEW, a warning must be attached."""
        bs = BalanceSheet()
        bs.items["current_assets"] = _make_line_item(
            "current_assets", "TSNH Mơ hồ", Decimal("1000"), status=MappingStatus.NEEDS_REVIEW
        )
        bs.items["current_liabilities"] = _make_line_item("current_liabilities", "Nợ ngắn hạn", Decimal("500"))

        calc = FinancialRatioCalculator()
        liq = calc.calculate_liquidity(bs)

        cr = liq["current_ratio"]
        assert cr.status == RatioStatus.CALCULATED
        assert any("needs_review" in w for w in cr.warnings)

    def test_decimal_precision_exact_no_float_loss(self):
        """Decimal precision must be preserved across division and representation."""
        bs = BalanceSheet()
        bs.items["current_assets"] = _make_line_item("current_assets", "TSNH", Decimal("1"))
        bs.items["current_liabilities"] = _make_line_item("current_liabilities", "Nợ ngắn hạn", Decimal("3"))

        calc = FinancialRatioCalculator()
        liq = calc.calculate_liquidity(bs)

        cr = liq["current_ratio"]
        assert isinstance(cr.value, Decimal)
        # Decimal division 1/3 does not lose precision to float
        assert str(cr.value).startswith("0.333333")
        assert cr.formatted_value == "0.33 lần"

    def test_integration_with_conghuy_real_sample(self):
        """Integrate with real extracted sample conghuy_A32_2020_sample.txt."""
        with open("data/samples/conghuy_A32_2020_sample.txt", "r", encoding="utf-8") as f:
            content = f.read()

        parser = FinancialStatementParser()
        report = parser.parse(content, source_name="conghuy_A32_2020_sample.txt")

        calc = FinancialRatioCalculator()
        ratio_report: FinancialRatioReport = calc.calculate_all(report)

        assert ratio_report.company_name == "CÔNG TY CỔ PHẦN 32"
        assert ratio_report.fiscal_year == 2020
        assert ratio_report.total_ratios == 14
        assert ratio_report.calculated_ratios == 14

        # Verify key ratios match real accounting numbers:
        # Current Ratio: 356,691,280,424 / 246,078,511,317 = 1.45 lần
        cr = ratio_report.get_ratio("current_ratio")
        assert cr.formatted_value == "1.45 lần"

        # Quick Ratio: (356,691,280,424 - 190,450,695,083) / 246,078,511,317 = 0.68 lần
        qr = ratio_report.get_ratio("quick_ratio")
        assert qr.formatted_value == "0.68 lần"

        # Debt to Assets: 246,078,511,317 / 488,295,453,917 = 50.40%
        dta = ratio_report.get_ratio("debt_to_assets")
        assert dta.formatted_value == "50.40%"

        # Debt to Equity: 246,078,511,317 / 242,216,942,600 = 1.02 lần
        dte = ratio_report.get_ratio("debt_to_equity")
        assert dte.formatted_value == "1.02 lần"

        # Gross Profit Margin: 79,596,121,017 / 728,581,046,415 = 10.92%
        gpm = ratio_report.get_ratio("gross_profit_margin")
        assert gpm.formatted_value == "10.92%"

        # Net Profit Margin: 42,107,027,168 / 728,581,046,415 = 5.78%
        npm = ratio_report.get_ratio("net_profit_margin")
        assert npm.formatted_value == "5.78%"

        # ROA: 42,107,027,168 / ((434,930,314,417 + 488,295,453,917)/2) = 9.12%
        roa = ratio_report.get_ratio("roa")
        assert roa.formatted_value == "9.12%"

        # ROE: 42,107,027,168 / ((223,612,748,462 + 242,216,942,600)/2) = 18.08%
        roe = ratio_report.get_ratio("roe")
        assert roe.formatted_value == "18.08%"
