"""Unit tests for UI interactive statement editing and Core 4 KPI card rendering."""
from decimal import Decimal
import pandas as pd
import pytest

from src.data.schema import BalanceSheet, FinancialReport, IncomeStatement, LineItem, MappingStatus
from src.financial.ratios import (
    FinancialRatioCalculator,
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
)
from src.ui.components import (
    _evaluate_kpi_visual,
    apply_edits_to_report,
    build_statement_dataframes,
    parse_cell_to_decimal,
)


def test_parse_cell_to_decimal():
    """Verify robust parsing of edited table values."""
    # Standard numbers
    assert parse_cell_to_decimal(1000) == Decimal("1000")
    assert parse_cell_to_decimal(125.5) == Decimal("125")  # converted via str(int)
    assert parse_cell_to_decimal(Decimal("500000")) == Decimal("500000")

    # Formatted strings
    assert parse_cell_to_decimal("120,000,000,000") == Decimal("120000000000")
    assert parse_cell_to_decimal(" 15.000.000 ") == Decimal("15000000")

    # Parenthesized negatives
    assert parse_cell_to_decimal("(50,000,000)") == Decimal("-50000000")
    assert parse_cell_to_decimal("-25000000") == Decimal("-25000000")

    # Dash / zero
    assert parse_cell_to_decimal("-") == Decimal("0")
    assert parse_cell_to_decimal("—") == Decimal("0")

    # None / Empty / Invalid
    assert parse_cell_to_decimal(None) is None
    assert parse_cell_to_decimal("") is None
    assert parse_cell_to_decimal("abc") is None


def test_build_statement_dataframes():
    """Verify DataFrames are properly extracted from FinancialReport."""
    report = FinancialReport(
        balance_sheet=BalanceSheet(
            items={
                "current_assets": LineItem(
                    raw_label="Tài sản ngắn hạn",
                    normalized_label="tai san ngan han",
                    item_code="100",
                    current_period_value=Decimal("120000000000"),
                    previous_period_value=Decimal("110000000000"),
                    mapping_status=MappingStatus.MAPPED,
                ),
            }
        ),
        income_statement=IncomeStatement(
            items={
                "net_revenue": LineItem(
                    raw_label="Doanh thu thuần",
                    normalized_label="doanh thu thuan",
                    item_code="10",
                    current_period_value=Decimal("200000000000"),
                    previous_period_value=Decimal("180000000000"),
                    mapping_status=MappingStatus.MAPPED,
                ),
            }
        ),
    )

    df_bs, df_is = build_statement_dataframes(report)

    assert len(df_bs) == 1
    assert df_bs.iloc[0]["canonical_key"] == "current_assets"
    assert df_bs.iloc[0]["Mã số"] == "100"
    assert "120,000,000,000" in df_bs.iloc[0]["Kỳ này (VND)"]

    assert len(df_is) == 1
    assert df_is.iloc[0]["canonical_key"] == "net_revenue"
    assert df_is.iloc[0]["Mã số"] == "10"


def test_apply_edits_to_report():
    """Verify user manual edits are applied to FinancialReport line items."""
    report = FinancialReport(
        balance_sheet=BalanceSheet(
            items={
                "current_assets": LineItem(
                    raw_label="Tài sản ngắn hạn",
                    normalized_label="tai san ngan han",
                    item_code="100",
                    current_period_value=Decimal("1000000"),
                    previous_period_value=Decimal("900000"),
                ),
            }
        ),
        income_statement=IncomeStatement(
            items={
                "net_revenue": LineItem(
                    raw_label="Doanh thu thuần",
                    normalized_label="doanh thu thuan",
                    item_code="10",
                    current_period_value=Decimal("2000000"),
                    previous_period_value=Decimal("1900000"),
                ),
            }
        ),
    )

    edited_df_bs = pd.DataFrame([
        {
            "canonical_key": "current_assets",
            "Mã số": "100-NEW",
            "Chỉ tiêu BCTC": "Tài sản ngắn hạn",
            "Kỳ này (VND)": "150,000,000",
            "Kỳ trước (VND)": "140,000,000",
        }
    ])
    edited_df_is = pd.DataFrame([
        {
            "canonical_key": "net_revenue",
            "Mã số": "10",
            "Chỉ tiêu BCTC": "Doanh thu thuần",
            "Kỳ này (VND)": "300,000,000",
            "Kỳ trước (VND)": "280,000,000",
        }
    ])

    updated_report = apply_edits_to_report(report, edited_df_bs, edited_df_is)

    # Check updated balance sheet item
    bs_item = updated_report.balance_sheet.items["current_assets"]
    assert bs_item.item_code == "100-NEW"
    assert bs_item.current_period_value == Decimal("150000000")
    assert bs_item.previous_period_value == Decimal("140000000")

    # Check updated income statement item
    is_item = updated_report.income_statement.items["net_revenue"]
    assert is_item.current_period_value == Decimal("300000000")
    assert is_item.previous_period_value == Decimal("280000000")


def test_evaluate_kpi_visual_color_thresholds():
    """Verify that KPI cards color the numbers correctly (Green, Yellow, Red)."""
    # 1. Current Ratio
    # Safe >= 1.5 -> Green (#16a34a)
    cr_safe = RatioResult(
        ratio_key="current_ratio", name="Current Ratio", category=RatioCategory.LIQUIDITY,
        value=Decimal("1.85"), status=RatioStatus.CALCULATED, formula="TSNH/NợNH"
    )
    val_str, color, badge, bg, border = _evaluate_kpi_visual("current_ratio", cr_safe)
    assert color == "#16a34a"
    assert badge == "AN TOÀN"

    # Watch [1.0, 1.5) -> Yellow/Amber (#d97706)
    cr_watch = RatioResult(
        ratio_key="current_ratio", name="Current Ratio", category=RatioCategory.LIQUIDITY,
        value=Decimal("1.20"), status=RatioStatus.CALCULATED, formula="TSNH/NợNH"
    )
    val_str, color, badge, bg, border = _evaluate_kpi_visual("current_ratio", cr_watch)
    assert color == "#d97706"
    assert badge == "CẢNH BÁO"

    # Alert < 1.0 -> Red (#dc2626)
    cr_alert = RatioResult(
        ratio_key="current_ratio", name="Current Ratio", category=RatioCategory.LIQUIDITY,
        value=Decimal("0.85"), status=RatioStatus.CALCULATED, formula="TSNH/NợNH"
    )
    val_str, color, badge, bg, border = _evaluate_kpi_visual("current_ratio", cr_alert)
    assert color == "#dc2626"
    assert badge == "NGUY HIỂM"

    # 2. Debt to Equity
    # Safe <= 1.0 -> Green
    dte_safe = RatioResult(
        ratio_key="debt_to_equity", name="Debt to Equity", category=RatioCategory.LEVERAGE,
        value=Decimal("0.75"), status=RatioStatus.CALCULATED, formula="Nợ/VCSH"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("debt_to_equity", dte_safe)
    assert color == "#16a34a"
    assert badge == "AN TOÀN"

    # Watch (1.0, 2.0] -> Yellow
    dte_watch = RatioResult(
        ratio_key="debt_to_equity", name="Debt to Equity", category=RatioCategory.LEVERAGE,
        value=Decimal("1.60"), status=RatioStatus.CALCULATED, formula="Nợ/VCSH"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("debt_to_equity", dte_watch)
    assert color == "#d97706"
    assert badge == "CẢNH BÁO"

    # Danger > 2.0 -> Red
    dte_alert = RatioResult(
        ratio_key="debt_to_equity", name="Debt to Equity", category=RatioCategory.LEVERAGE,
        value=Decimal("2.40"), status=RatioStatus.CALCULATED, formula="Nợ/VCSH"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("debt_to_equity", dte_alert)
    assert color == "#dc2626"
    assert badge == "NGUY HIỂM"

    # 3. ROA
    # Safe >= 5% -> Green
    roa_safe = RatioResult(
        ratio_key="roa", name="ROA", category=RatioCategory.PROFITABILITY,
        value=Decimal("0.08"), status=RatioStatus.CALCULATED, formula="LNST/TS"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("roa", roa_safe)
    assert color == "#16a34a"

    # Watch [0, 5%) -> Yellow
    roa_watch = RatioResult(
        ratio_key="roa", name="ROA", category=RatioCategory.PROFITABILITY,
        value=Decimal("0.03"), status=RatioStatus.CALCULATED, formula="LNST/TS"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("roa", roa_watch)
    assert color == "#d97706"

    # Danger < 0% -> Red
    roa_neg = RatioResult(
        ratio_key="roa", name="ROA", category=RatioCategory.PROFITABILITY,
        value=Decimal("-0.02"), status=RatioStatus.CALCULATED, formula="LNST/TS"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("roa", roa_neg)
    assert color == "#dc2626"

    # 4. ROE
    # Safe >= 12% -> Green
    roe_safe = RatioResult(
        ratio_key="roe", name="ROE", category=RatioCategory.PROFITABILITY,
        value=Decimal("0.16"), status=RatioStatus.CALCULATED, formula="LNST/VCSH"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("roe", roe_safe)
    assert color == "#16a34a"

    # Watch [0, 12%) -> Yellow
    roe_watch = RatioResult(
        ratio_key="roe", name="ROE", category=RatioCategory.PROFITABILITY,
        value=Decimal("0.07"), status=RatioStatus.CALCULATED, formula="LNST/VCSH"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("roe", roe_watch)
    assert color == "#d97706"

    # Danger < 0% -> Red
    roe_neg = RatioResult(
        ratio_key="roe", name="ROE", category=RatioCategory.PROFITABILITY,
        value=Decimal("-0.05"), status=RatioStatus.CALCULATED, formula="LNST/VCSH"
    )
    _, color, badge, _, _ = _evaluate_kpi_visual("roe", roe_neg)
    assert color == "#dc2626"
