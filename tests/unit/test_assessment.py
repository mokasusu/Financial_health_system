"""Unit and Integration tests for Financial Health Assessment & Warning Engine (Sprint 4B).

Verifies rule-based ratio evaluation, illustrative threshold boundaries, prioritized warning
generation, negative equity/ROE traps, missing data handling, warning deduplication,
overall status synthesis, Decimal preservation, and integration with real sample data.
"""
from decimal import Decimal
import json
from typing import Dict, List, Optional
import pytest

from src.data.parser import FinancialStatementParser
from src.financial.assessment import (
    DEFAULT_SCREENING_THRESHOLDS,
    FinancialHealthAssessor,
)
from src.financial.assessment_models import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    OverallHealthStatus,
    RatioAssessment,
    WarningCategory,
    WarningSeverity,
)
from src.financial.ratios import (
    FinancialRatioCalculator,
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
    RATIO_METADATA,
)


def _make_ratio_result(
    ratio_key: str,
    value: Optional[Decimal] = None,
    status: RatioStatus = RatioStatus.CALCULATED,
    warnings: Optional[List[str]] = None,
    inputs: Optional[Dict[str, Optional[Decimal]]] = None,
) -> RatioResult:
    """Helper to construct realistic RatioResult fixtures matching Sprint 4A."""
    meta = RATIO_METADATA[ratio_key]
    unit = meta["unit"]
    fmt = meta["display_format"]

    if value is not None and status == RatioStatus.CALCULATED:
        if "%" in fmt:
            formatted_value = f"{(value * Decimal('100')):.2f}%"
        else:
            formatted_value = f"{value:.2f} {unit}"
    elif status == RatioStatus.UNDEFINED and value is not None:
        formatted_value = f"{value:.2f} {unit}"
    else:
        formatted_value = "N/A"

    return RatioResult(
        ratio_key=ratio_key,
        name=meta["name"],
        category=meta["category"],
        value=value,
        unit=unit,
        display_format=fmt,
        formatted_value=formatted_value,
        status=status,
        formula=meta["formula"],
        input_keys=meta["input_keys"],
        inputs=inputs or {},
        warnings=warnings or [],
        description=meta["description"],
    )


@pytest.fixture
def baseline_ratio_report() -> FinancialRatioReport:
    """Fixture with all 14 ratios calculated at healthy/safe baseline levels."""
    ratios: Dict[str, RatioResult] = {
        # Liquidity (all ADEQUATE)
        "current_ratio": _make_ratio_result("current_ratio", Decimal("2.0")),
        "quick_ratio": _make_ratio_result("quick_ratio", Decimal("1.2")),
        "cash_ratio": _make_ratio_result("cash_ratio", Decimal("0.3")),
        # Leverage (all ADEQUATE)
        "debt_to_assets": _make_ratio_result("debt_to_assets", Decimal("0.40")),
        "debt_to_equity": _make_ratio_result("debt_to_equity", Decimal("0.70")),
        "equity_ratio": _make_ratio_result("equity_ratio", Decimal("0.60")),
        # Efficiency (CALCULATED_NO_BENCHMARK)
        "total_asset_turnover": _make_ratio_result("total_asset_turnover", Decimal("1.5")),
        "inventory_turnover": _make_ratio_result("inventory_turnover", Decimal("4.0")),
        "receivables_turnover": _make_ratio_result("receivables_turnover", Decimal("8.0")),
        # Profitability (all positive -> CALCULATED_NO_BENCHMARK)
        "gross_profit_margin": _make_ratio_result("gross_profit_margin", Decimal("0.25")),
        "operating_profit_margin": _make_ratio_result("operating_profit_margin", Decimal("0.12")),
        "net_profit_margin": _make_ratio_result("net_profit_margin", Decimal("0.08")),
        "roa": _make_ratio_result("roa", Decimal("0.10")),
        "roe": _make_ratio_result("roe", Decimal("0.18")),
    }
    return FinancialRatioReport(
        company_name="CTY BASELINE",
        fiscal_year=2020,
        currency="VND",
        ratios=ratios,
        total_ratios=14,
        calculated_ratios=14,
    )


class TestFinancialHealthAssessor:
    """Unit test suite for FinancialHealthAssessor rule engine."""

    # Scenario 1: Group Evaluation
    def test_evaluation_across_all_groups(self, baseline_ratio_report):
        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(baseline_ratio_report)

        assert len(assessment.ratio_assessments) == 14
        assert len(assessment.category_overviews) == 4
        assert "liquidity" in assessment.category_overviews
        assert "leverage" in assessment.category_overviews
        assert "efficiency" in assessment.category_overviews
        assert "profitability" in assessment.category_overviews
        assert assessment.overall_status == OverallHealthStatus.NO_MAJOR_RULE_BASED_ALERTS

    # Scenario 2: Threshold Boundary Values (below, exactly on, and above threshold)
    def test_threshold_boundary_conditions(self):
        assessor = FinancialHealthAssessor()

        # Current ratio: < 1.0 (Alert), 1.0 <= val < 1.5 (Watch), >= 1.5 (Adequate)
        cr_below = _make_ratio_result("current_ratio", Decimal("0.99"))
        cr_exact_watch = _make_ratio_result("current_ratio", Decimal("1.00"))
        cr_mid_watch = _make_ratio_result("current_ratio", Decimal("1.25"))
        cr_exact_adequate = _make_ratio_result("current_ratio", Decimal("1.50"))
        cr_above = _make_ratio_result("current_ratio", Decimal("2.10"))

        assert assessor._assess_single_ratio(cr_below)[0].status == AssessmentStatus.ALERT
        assert assessor._assess_single_ratio(cr_exact_watch)[0].status == AssessmentStatus.WATCH
        assert assessor._assess_single_ratio(cr_mid_watch)[0].status == AssessmentStatus.WATCH
        assert assessor._assess_single_ratio(cr_exact_adequate)[0].status == AssessmentStatus.ADEQUATE
        assert assessor._assess_single_ratio(cr_above)[0].status == AssessmentStatus.ADEQUATE

        # Debt to assets: > 0.7 (Alert), 0.5 < val <= 0.7 (Watch), <= 0.5 (Adequate)
        dta_adequate = _make_ratio_result("debt_to_assets", Decimal("0.50"))
        dta_watch_low = _make_ratio_result("debt_to_assets", Decimal("0.51"))
        dta_watch_exact = _make_ratio_result("debt_to_assets", Decimal("0.70"))
        dta_alert = _make_ratio_result("debt_to_assets", Decimal("0.71"))

        assert assessor._assess_single_ratio(dta_adequate)[0].status == AssessmentStatus.ADEQUATE
        assert assessor._assess_single_ratio(dta_watch_low)[0].status == AssessmentStatus.WATCH
        assert assessor._assess_single_ratio(dta_watch_exact)[0].status == AssessmentStatus.WATCH
        assert assessor._assess_single_ratio(dta_alert)[0].status == AssessmentStatus.ALERT

    # Scenario 3: Missing Required Data (NOT_AVAILABLE)
    def test_missing_data_assessment(self):
        assessor = FinancialHealthAssessor()
        cr_missing = _make_ratio_result("current_ratio", None, status=RatioStatus.NOT_AVAILABLE)
        eval_res, warnings = assessor._assess_single_ratio(cr_missing)

        assert eval_res.status == AssessmentStatus.NOT_AVAILABLE
        assert eval_res.value is None
        assert "chưa thể tính toán" in eval_res.explanation
        assert len(warnings) == 1
        assert warnings[0].code == "DATA_MISSING_CURRENT_RATIO"
        assert warnings[0].severity == WarningSeverity.INFO

    # Scenario 4: Distinguish Numeric Zero from None
    def test_distinguish_zero_from_none(self):
        assessor = FinancialHealthAssessor()
        # Margin = 0.00% is break-even, not missing
        npm_zero = _make_ratio_result("net_profit_margin", Decimal("0.0"))
        eval_res, _ = assessor._assess_single_ratio(npm_zero)

        assert eval_res.status == AssessmentStatus.WATCH
        assert eval_res.value == Decimal("0.0")
        assert "hòa vốn" in eval_res.explanation
        assert "không phải do thiếu dữ liệu" in eval_res.explanation

    # Scenario 5: Zero Denominator (NOT_APPLICABLE)
    def test_zero_denominator_not_applicable(self):
        assessor = FinancialHealthAssessor()
        cr_na = _make_ratio_result("current_ratio", None, status=RatioStatus.NOT_APPLICABLE)
        eval_res, warnings = assessor._assess_single_ratio(cr_na)

        assert eval_res.status == AssessmentStatus.NOT_APPLICABLE
        assert eval_res.value is None
        assert "mẫu số bằng 0" in eval_res.explanation.lower()
        assert warnings[0].code == "DATA_NOT_APPLICABLE_CURRENT_RATIO"

    # Scenario 6: Negative Equity in Debt-to-Equity and ROE Trap
    def test_negative_equity_trap_handling(self):
        assessor = FinancialHealthAssessor()

        # D/E with negative equity
        dte_undef = _make_ratio_result(
            "debt_to_equity",
            Decimal("-3.5"),
            status=RatioStatus.UNDEFINED,
            inputs={"liabilities": Decimal("700"), "equity": Decimal("-200")},
        )
        eval_res, warnings = assessor._assess_single_ratio(dte_undef)

        assert eval_res.status == AssessmentStatus.UNDEFINED
        assert any(w.severity == WarningSeverity.CRITICAL for w in warnings)
        assert any(w.code == "EQUITY_NEGATIVE_CRITICAL" for w in warnings)

        # ROE with negative equity and loss: (-100) / (-500) = +0.20
        roe_undef = _make_ratio_result(
            "roe",
            Decimal("0.20"),
            status=RatioStatus.UNDEFINED,
            inputs={"net_profit_after_tax": Decimal("-100"), "equity_avg": Decimal("-500")},
        )
        eval_roe, roe_warnings = assessor._assess_single_ratio(roe_undef)

        assert eval_roe.status == AssessmentStatus.UNDEFINED
        assert any(w.severity == WarningSeverity.CRITICAL for w in roe_warnings)
        assert "không phản ánh khả năng sinh lời" in eval_roe.explanation or any(
            "không phản ánh khả năng sinh lời" in w.message for w in roe_warnings
        )

    # Scenario 7: Warnings from Line Items (needs_review) Propagated
    def test_inherited_data_quality_warnings(self, baseline_ratio_report):
        assessor = FinancialHealthAssessor()
        # Inject needs_review warning into current_ratio
        baseline_ratio_report.ratios["current_ratio"].warnings.append(
            "Khoản mục đầu vào 'current_assets' đang ở trạng thái cần rà soát (needs_review)."
        )

        assessment = assessor.assess(baseline_ratio_report)

        # Check that ratio assessment kept the warning
        cr_eval = assessment.get_assessment("current_ratio")
        assert any("needs_review" in w for w in cr_eval.warnings)

        # Check that a synthesized DATA_QUALITY warning was created
        assert any(w.code == "DATA_QUALITY_NEEDS_REVIEW" for w in assessment.warnings)
        assert any(w.severity == WarningSeverity.MEDIUM for w in assessment.warnings)

    # Scenario 8: Efficiency Ratios No Absolute Benchmark
    def test_efficiency_no_benchmark_status(self):
        assessor = FinancialHealthAssessor()
        tat = _make_ratio_result("total_asset_turnover", Decimal("2.5"))
        eval_res, warnings = assessor._assess_single_ratio(tat)

        assert eval_res.status == AssessmentStatus.CALCULATED_NO_BENCHMARK
        assert len(warnings) == 0
        assert "cần được so sánh với các doanh nghiệp cùng ngành" in eval_res.explanation

    # Scenario 9: Negative Profitability Alerts
    def test_negative_profitability_alerts(self):
        assessor = FinancialHealthAssessor()
        npm_loss = _make_ratio_result("net_profit_margin", Decimal("-0.05"))
        eval_res, warnings = assessor._assess_single_ratio(npm_loss)

        assert eval_res.status == AssessmentStatus.ALERT
        assert len(warnings) == 1
        assert warnings[0].code == "PROFITABILITY_NET_PROFIT_MARGIN_NEGATIVE"
        assert warnings[0].severity == WarningSeverity.HIGH

    # Scenario 10: Deduplication of Warnings
    def test_warning_deduplication(self, baseline_ratio_report):
        assessor = FinancialHealthAssessor()
        # Trigger same alert code twice or duplicate codes
        w1 = FinancialWarning(
            code="TEST_ALERT",
            category=WarningCategory.LIQUIDITY,
            severity=WarningSeverity.HIGH,
            title="Alert 1",
            message="Msg",
            evidence="Ev",
            recommendation="Rec",
        )
        w2 = FinancialWarning(
            code="TEST_ALERT",
            category=WarningCategory.LIQUIDITY,
            severity=WarningSeverity.HIGH,
            title="Alert 1 Duplicate",
            message="Msg",
            evidence="Ev",
            recommendation="Rec",
        )
        deduped = assessor._prioritize_and_deduplicate_warnings([w1, w2])
        assert len(deduped) == 1
        assert deduped[0].code == "TEST_ALERT"

    # Scenario 11: Insufficient Data Overall Status
    def test_insufficient_data_overall_status(self, baseline_ratio_report):
        assessor = FinancialHealthAssessor()
        # Set 4 ratios to NOT_AVAILABLE
        for k in ["current_ratio", "quick_ratio", "cash_ratio", "debt_to_assets"]:
            baseline_ratio_report.ratios[k] = _make_ratio_result(k, None, status=RatioStatus.NOT_AVAILABLE)

        assessment = assessor.assess(baseline_ratio_report)
        assert assessment.overall_status == OverallHealthStatus.INSUFFICIENT_DATA

    # Scenario 12: Decimal Precision Preserved
    def test_decimal_precision_in_assessment(self):
        assessor = FinancialHealthAssessor()
        # Highly precise decimal 0.3333333333333333333333333333
        high_prec = Decimal("1") / Decimal("3")
        cr = _make_ratio_result("current_ratio", high_prec)
        eval_res, _ = assessor._assess_single_ratio(cr)

        assert isinstance(eval_res.value, Decimal)
        assert eval_res.value == high_prec
        assert not isinstance(eval_res.value, float)

    # Scenario 13: Deterministic Assessment (Same input gives identical output)
    def test_deterministic_consistency(self, baseline_ratio_report):
        assessor = FinancialHealthAssessor()
        res1 = assessor.assess(baseline_ratio_report)
        res2 = assessor.assess(baseline_ratio_report)

        assert res1.overall_status == res2.overall_status
        assert len(res1.warnings) == len(res2.warnings)
        for k in res1.ratio_assessments:
            assert res1.ratio_assessments[k].status == res2.ratio_assessments[k].status
            assert res1.ratio_assessments[k].explanation == res2.ratio_assessments[k].explanation

    # Scenario 14: No Business Alerts on Invalid/Missing Ratios
    def test_no_business_alerts_on_invalid_ratios(self):
        assessor = FinancialHealthAssessor()
        cr_missing = _make_ratio_result("current_ratio", None, status=RatioStatus.NOT_AVAILABLE)
        _, warnings = assessor._assess_single_ratio(cr_missing)

        # Must not generate business liquidity alert like LIQUIDITY_CURRENT_RATIO_LOW
        assert not any(w.code == "LIQUIDITY_CURRENT_RATIO_LOW" for w in warnings)
        assert all(w.category == WarningCategory.DATA_QUALITY for w in warnings)

    # Scenario 15: Pydantic Model Serialization
    def test_pydantic_model_json_serialization(self, baseline_ratio_report):
        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(baseline_ratio_report)

        # Serialize to json string
        json_data = assessment.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize back
        data_dict = json.loads(json_data)
        assert data_dict["overall_status"] == OverallHealthStatus.NO_MAJOR_RULE_BASED_ALERTS.value
        assert len(data_dict["ratio_assessments"]) == 14

    # Scenario 16: Integration with Real Sample Data (conghuy_A32_2020_sample.txt)
    def test_integration_with_real_conghuy_sample(self):
        with open("data/samples/conghuy_A32_2020_sample.txt", "r", encoding="utf-8") as f:
            content = f.read()

        parser = FinancialStatementParser()
        report = parser.parse(content, source_name="conghuy_A32_2020_sample.txt")

        calc = FinancialRatioCalculator()
        ratio_report = calc.calculate_all(report)

        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(ratio_report)

        assert assessment.company_name == "CÔNG TY CỔ PHẦN 32"
        assert assessment.fiscal_year == 2020
        assert assessment.total_ratios_evaluated == 14
        assert assessment.calculated_count == 14

        # Verify real status of key ratios:
        # Current ratio: 1.45 (Watch)
        assert assessment.get_assessment("current_ratio").status == AssessmentStatus.WATCH
        # Quick ratio: 0.68 (Watch)
        assert assessment.get_assessment("quick_ratio").status == AssessmentStatus.WATCH
        # Debt to assets: 50.40% (Watch)
        assert assessment.get_assessment("debt_to_assets").status == AssessmentStatus.WATCH
        # Profitability margins: all positive -> CALCULATED_NO_BENCHMARK
        assert assessment.get_assessment("gross_profit_margin").status == AssessmentStatus.CALCULATED_NO_BENCHMARK
        assert assessment.get_assessment("net_profit_margin").status == AssessmentStatus.CALCULATED_NO_BENCHMARK
        # Overall health status should be MIXED (cần theo dõi thanh khoản và đòn bẩy vùng đệm, kinh doanh có lãi)
        assert assessment.overall_status == OverallHealthStatus.MIXED
        assert len(assessment.key_findings) >= 2
        assert len(assessment.limitations) == 4

        # Verify 1-to-1 consistency between WATCH ratios and FinancialWarnings:
        # 6 ratios in WATCH: 3 liquidity + 3 leverage -> exactly 6 warnings of severity LOW
        assert assessment.watch_count == 6
        assert len(assessment.warnings) == 6
        assert all(w.severity == WarningSeverity.LOW for w in assessment.warnings)
        
        liq_warns = [w for w in assessment.warnings if w.category == WarningCategory.LIQUIDITY]
        lev_warns = [w for w in assessment.warnings if w.category == WarningCategory.LEVERAGE]
        assert len(liq_warns) == 3
        assert len(lev_warns) == 3
        assert {w.code for w in liq_warns} == {
            "LIQUIDITY_CURRENT_RATIO_WATCH",
            "LIQUIDITY_QUICK_RATIO_WATCH",
            "LIQUIDITY_CASH_RATIO_WATCH",
        }
        assert {w.code for w in lev_warns} == {
            "LEVERAGE_DEBT_TO_ASSETS_WATCH",
            "LEVERAGE_DEBT_TO_EQUITY_WATCH",
            "LEVERAGE_EQUITY_RATIO_WATCH",
        }

    # Scenario 17: Consistency Between Leverage Rules, Warnings, and Category Overviews
    def test_leverage_rules_consistency(self):
        assessor = FinancialHealthAssessor()

        # Case 1: Alert triggered on debt_to_assets (> 0.70)
        dta_alert = _make_ratio_result("debt_to_assets", Decimal("0.75"))
        eval_dta, warns = assessor._assess_single_ratio(dta_alert)
        assert eval_dta.status == AssessmentStatus.ALERT
        assert len(warns) == 1
        assert warns[0].code == "LEVERAGE_DEBT_TO_ASSETS_HIGH"
        assert warns[0].severity == WarningSeverity.HIGH

        # Case 2: Watch triggered on debt_to_assets (0.50 < x <= 0.70)
        dta_watch = _make_ratio_result("debt_to_assets", Decimal("0.60"))
        eval_watch, warns_watch = assessor._assess_single_ratio(dta_watch)
        assert eval_watch.status == AssessmentStatus.WATCH
        assert len(warns_watch) == 1
        assert warns_watch[0].code == "LEVERAGE_DEBT_TO_ASSETS_WATCH"
        assert warns_watch[0].severity == WarningSeverity.LOW

        # Case 3: Adequate on debt_to_assets (<= 0.50)
        dta_adeq = _make_ratio_result("debt_to_assets", Decimal("0.45"))
        eval_adeq, warns_adeq = assessor._assess_single_ratio(dta_adeq)
        assert eval_adeq.status == AssessmentStatus.ADEQUATE
        assert len(warns_adeq) == 0

        # Case 4: Category overview reflects alert if ANY leverage ratio is ALERT
        overviews = assessor._build_category_overviews({
            "debt_to_assets": eval_adeq,     # ADEQUATE
            "debt_to_equity": eval_dta,     # ALERT (using alert evaluation)
            "equity_ratio": eval_watch,     # WATCH
        })
        assert "Mức độ đòn bẩy tài chính cao" in overviews["leverage"]

        # Case 5: Category overview reflects watch if no ALERT but has WATCH
        overviews_watch = assessor._build_category_overviews({
            "debt_to_assets": eval_adeq,     # ADEQUATE
            "debt_to_equity": eval_watch,    # WATCH
            "equity_ratio": eval_adeq,      # ADEQUATE
        })
        assert "vùng đệm theo dõi" in overviews_watch["leverage"]
