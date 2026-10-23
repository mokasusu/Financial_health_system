"""Unit tests for UI formatting functions and design badge helpers (Sprint 6)."""
from decimal import Decimal
import pytest

from src.financial.assessment_models import AssessmentStatus, WarningSeverity
from src.ui.formatters import (
    format_currency,
    format_difference,
    format_percentage,
    format_ratio_value,
)
from src.ui.styles import (
    get_overall_health_banner_html,
    get_severity_badge_html,
    get_status_badge_html,
)


class TestUIFormatters:
    """Test defensive formatting for monetary numbers, percentages, and ratios."""

    def test_format_currency_with_none(self):
        assert format_currency(None) == "N/A"
        assert format_currency(None, default="--") == "--"

    def test_format_currency_integers_and_decimals(self):
        assert format_currency(1000000) == "1,000,000 VND"
        assert format_currency(Decimal("145230000")) == "145,230,000 VND"
        assert format_currency(Decimal("1234.56")) == "1,234.56 VND"
        assert format_currency("50000000") == "50,000,000 VND"
        assert format_currency("1,200,000") == "1,200,000 VND"

    def test_format_currency_invalid_string(self):
        assert format_currency("invalid_number") == "N/A"
        assert format_currency(object()) == "N/A"

    def test_format_currency_custom_unit(self):
        assert format_currency(Decimal("2500"), unit="USD") == "2,500 USD"
        assert format_currency(Decimal("100"), unit="") == "100"

    def test_format_percentage_with_none(self):
        assert format_percentage(None) == "N/A"
        assert format_percentage(None, default="Trống") == "Trống"

    def test_format_percentage_decimal_conversion(self):
        # 0.1542 should become 15.42%
        assert format_percentage(Decimal("0.1542")) == "15.42%"
        assert format_percentage(Decimal("0.05")) == "5.00%"
        assert format_percentage(Decimal("-0.025")) == "-2.50%"
        assert format_percentage(0.504) == "50.40%"

    def test_format_percentage_invalid_input(self):
        assert format_percentage("abc") == "N/A"

    def test_format_ratio_value_with_none(self):
        assert format_ratio_value(None) == "N/A"
        assert format_ratio_value(None, unit="vòng") == "N/A"

    def test_format_ratio_value_standard(self):
        assert format_ratio_value(Decimal("1.452")) == "1.45 lần"
        assert format_ratio_value(Decimal("2.10"), unit="vòng") == "2.10 vòng"
        assert format_ratio_value(Decimal("0.6336"), unit="%") == "63.36%"

    def test_format_difference_handling(self):
        assert format_difference(None) == "Không xác định"
        assert format_difference(Decimal("0")) == "Cân đối tuyệt đối (0 VND)"
        assert "Chênh lệch: 12,000 VND" in format_difference(Decimal("12000"))

        diff_with_tol = format_difference(Decimal("500"), tolerance=Decimal("1000"))
        assert "500 VND" in diff_with_tol
        assert "1,000 VND" in diff_with_tol


class TestUIBadgeHelpers:
    """Test HTML badge rendering for statuses and severities."""

    def test_get_status_badge_html_all_statuses(self):
        for status_val in [
            "adequate",
            "watch",
            "alert",
            "no_benchmark",
            "not_available",
            "not_applicable",
            "undefined",
        ]:
            html = get_status_badge_html(status_val)
            assert "class=\"status-badge\"" in html
            assert "background-color:" in html

    def test_get_status_badge_html_with_none_or_unknown(self):
        html_none = get_status_badge_html(None)
        assert "KHÔNG XÁC ĐỊNH" in html_none

        html_unknown = get_status_badge_html("some_unknown_status")
        assert "KHÔNG XÁC ĐỊNH" in html_unknown

    def test_get_status_badge_custom_text(self):
        html = get_status_badge_html("adequate", custom_text="ĐẠT CHUẨN")
        assert "ĐẠT CHUẨN" in html

    def test_get_severity_badge_html_all_levels(self):
        for sev in ["critical", "high", "medium", "low", "info"]:
            html = get_severity_badge_html(sev)
            assert "class=\"severity-badge\"" in html
            assert "background-color:" in html

    def test_get_overall_health_banner_html(self):
        for health_status in [
            "needs_attention",
            "mixed",
            "no_major_rule_based_alerts",
            "insufficient_data",
        ]:
            banner = get_overall_health_banner_html(health_status)
            assert "Đánh giá rule-based" in banner
