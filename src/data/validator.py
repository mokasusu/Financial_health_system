"""Financial statement accounting equation validator and integrity checks."""
from decimal import Decimal
import logging
from typing import List, Optional
from src.data.schema import (
    BalanceSheet,
    CheckStatus,
    FinancialReport,
    IncomeStatement,
    ValidationCheck,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Default acceptable rounding difference (in unit currency e.g. 1,000 VND)
DEFAULT_ROUNDING_TOLERANCE = Decimal("1000")


class FinancialValidator:
    """Validator implementing core accounting identities and consistency checks."""

    def __init__(self, tolerance: Decimal = DEFAULT_ROUNDING_TOLERANCE):
        """Initialize validator with a rounding tolerance."""
        self.tolerance = abs(tolerance)

    def validate(self, report: FinancialReport, period: str = "current") -> ValidationResult:
        """Run all accounting checks on the financial report for a specific period."""
        checks: List[ValidationCheck] = []

        if report.balance_sheet:
            checks.extend(self._validate_balance_sheet(report.balance_sheet, period))

        if report.income_statement:
            checks.extend(self._validate_income_statement(report.income_statement, period))

        # Check for unmapped or needs_review items
        checks.append(self._check_mapping_health(report))

        # Aggregate results
        passed = sum(1 for c in checks if c.status == CheckStatus.PASS)
        warnings = sum(1 for c in checks if c.status == CheckStatus.WARNING)
        failed = sum(1 for c in checks if c.status == CheckStatus.FAIL)
        not_checkable = sum(1 for c in checks if c.status == CheckStatus.NOT_CHECKABLE)

        is_valid = (failed == 0)

        summary_parts = [
            f"Tổng số {len(checks)} kiểm tra",
            f"{passed} Đạt (PASS)",
            f"{failed} Lỗi (FAIL)",
            f"{warnings} Cảnh báo (WARNING)",
            f"{not_checkable} Chưa đủ số liệu (NOT CHECKABLE)",
        ]

        result = ValidationResult(
            is_valid=is_valid,
            total_checks=len(checks),
            passed_checks=passed,
            warning_checks=warnings,
            failed_checks=failed,
            not_checkable_checks=not_checkable,
            checks=checks,
            summary=" | ".join(summary_parts),
        )

        report.validation_results = result
        return result

    def _validate_balance_sheet(self, bs: BalanceSheet, period: str) -> List[ValidationCheck]:
        """Validate fundamental balance sheet equations."""
        checks: List[ValidationCheck] = []

        # Check 1: TỔNG TÀI SẢN = TỔNG NGUỒN VỐN (MS 270 = MS 440)
        checks.append(
            self._evaluate_equation(
                check_id="BS_EQ_01",
                name="Cân đối Tổng Tài sản và Tổng Nguồn vốn",
                description="Tổng Tài sản (270) == Tổng Nguồn vốn (440)",
                left_val=bs.get_value("total_assets", period),
                right_val=bs.get_value("total_equity_and_liabilities", period),
                var_names=("Tổng Tài sản", "Tổng Nguồn vốn"),
            )
        )

        # Check 2: TỔNG TÀI SẢN = TÀI SẢN NGẮN HẠN + TÀI SẢN DÀI HẠN (MS 270 = MS 100 + MS 200)
        cur_assets = bs.get_value("current_assets", period)
        non_cur_assets = bs.get_value("non_current_assets", period)
        total_assets = bs.get_value("total_assets", period)

        sum_assets = (cur_assets + non_cur_assets) if (cur_assets is not None and non_cur_assets is not None) else None
        checks.append(
            self._evaluate_equation(
                check_id="BS_EQ_02",
                name="Phân rã Tài sản ngắn hạn và dài hạn",
                description="Tổng Tài sản (270) == Tài sản ngắn hạn (100) + Tài sản dài hạn (200)",
                left_val=total_assets,
                right_val=sum_assets,
                var_names=("Tổng Tài sản", "TSNH + TSDH"),
            )
        )

        # Check 3: TỔNG NGUỒN VỐN = NỢ PHẢI TRẢ + VỐN CHỦ SỞ HỮU (MS 440 = MS 300 + MS 400)
        liabilities = bs.get_value("liabilities", period)
        equity = bs.get_value("equity", period)
        total_nv = bs.get_value("total_equity_and_liabilities", period)

        sum_nv = (liabilities + equity) if (liabilities is not None and equity is not None) else None
        checks.append(
            self._evaluate_equation(
                check_id="BS_EQ_03",
                name="Phân rã Nguồn vốn",
                description="Tổng Nguồn vốn (440) == Nợ phải trả (300) + Vốn chủ sở hữu (400)",
                left_val=total_nv,
                right_val=sum_nv,
                var_names=("Tổng Nguồn vốn", "Nợ phải trả + VCSH"),
            )
        )

        # Check 4: NỢ PHẢI TRẢ = NỢ NGẮN HẠN + NỢ DÀI HẠN (MS 300 = MS 310 + MS 330)
        cur_liab = bs.get_value("current_liabilities", period)
        non_cur_liab = bs.get_value("non_current_liabilities", period)
        sum_liab = (cur_liab + non_cur_liab) if (cur_liab is not None and non_cur_liab is not None) else None

        checks.append(
            self._evaluate_equation(
                check_id="BS_EQ_04",
                name="Phân rã Nợ phải trả",
                description="Nợ phải trả (300) == Nợ ngắn hạn (310) + Nợ dài hạn (330)",
                left_val=liabilities,
                right_val=sum_liab,
                var_names=("Nợ phải trả", "Nợ ngắn hạn + Nợ dài hạn"),
            )
        )

        return checks

    def _validate_income_statement(self, is_: IncomeStatement, period: str) -> List[ValidationCheck]:
        """Validate income statement arithmetic identities."""
        checks: List[ValidationCheck] = []

        # Check 5: Doanh thu thuần = Doanh thu gộp - Các khoản giảm trừ (MS 10 = MS 01 - MS 02)
        gross_rev = is_.get_value("gross_revenue", period)
        rev_ded = is_.get_value("revenue_deductions", period)
        net_rev = is_.get_value("net_revenue", period)

        # In VN accounting, if revenue deductions is dash/None, it is often 0
        calc_net_rev = None
        if gross_rev is not None and rev_ded is not None:
            calc_net_rev = gross_rev - rev_ded
        elif gross_rev is not None and rev_ded is None:
            calc_net_rev = gross_rev

        checks.append(
            self._evaluate_equation(
                check_id="IS_EQ_01",
                name="Tính cân đối Doanh thu thuần",
                description="Doanh thu thuần (10) == Doanh thu bán hàng (01) - Giảm trừ (02)",
                left_val=net_rev,
                right_val=calc_net_rev,
                var_names=("Doanh thu thuần", "Doanh thu gộp - Giảm trừ"),
            )
        )

        # Check 6: Lợi nhuận gộp = Doanh thu thuần - Giá vốn hàng bán (MS 20 = MS 10 - MS 11)
        cogs = is_.get_value("cost_of_goods_sold", period)
        gross_profit = is_.get_value("gross_profit", period)
        calc_gross_profit = (net_rev - cogs) if (net_rev is not None and cogs is not None) else None

        checks.append(
            self._evaluate_equation(
                check_id="IS_EQ_02",
                name="Tính cân đối Lợi nhuận gộp",
                description="Lợi nhuận gộp (20) == Doanh thu thuần (10) - Giá vốn (11)",
                left_val=gross_profit,
                right_val=calc_gross_profit,
                var_names=("Lợi nhuận gộp", "Doanh thu thuần - Giá vốn"),
            )
        )

        # Check 7: Lợi nhuận trước thuế (MS 50 = MS 30 + MS 40)
        op_profit = is_.get_value("operating_profit", period)
        other_profit = is_.get_value("net_other_profit", period)
        pbt = is_.get_value("net_profit_before_tax", period)

        sum_pbt = (op_profit + other_profit) if (op_profit is not None and other_profit is not None) else None
        checks.append(
            self._evaluate_equation(
                check_id="IS_EQ_03",
                name="Tổng lợi nhuận trước thuế",
                description="Lợi nhuận trước thuế (50) == LN thuần HĐKD (30) + Lợi nhuận khác (40)",
                left_val=pbt,
                right_val=sum_pbt,
                var_names=("LN trước thuế", "LN thuần HĐKD + LN khác"),
            )
        )

        return checks

    def _evaluate_equation(
        self,
        check_id: str,
        name: str,
        description: str,
        left_val: Optional[Decimal],
        right_val: Optional[Decimal],
        var_names: tuple[str, str],
    ) -> ValidationCheck:
        """Safely evaluate an equality between two Decimal amounts with tolerance."""
        if left_val is None or right_val is None:
            missing_names = []
            if left_val is None:
                missing_names.append(var_names[0])
            if right_val is None:
                missing_names.append(var_names[1])

            return ValidationCheck(
                check_id=check_id,
                name=name,
                description=description,
                status=CheckStatus.NOT_CHECKABLE,
                difference=None,
                tolerance=self.tolerance,
                details={var_names[0]: left_val, var_names[1]: right_val},
                message=f"Chưa đủ dữ liệu để kiểm tra: thiếu {', '.join(missing_names)}.",
            )

        diff = abs(left_val - right_val)

        if diff <= self.tolerance:
            msg = "Đạt cân đối hoàn hảo." if diff == Decimal(0) else f"Đạt cân đối (lệch làm tròn {diff:,} <= {self.tolerance:,})."
            return ValidationCheck(
                check_id=check_id,
                name=name,
                description=description,
                status=CheckStatus.PASS,
                difference=diff,
                tolerance=self.tolerance,
                details={var_names[0]: left_val, var_names[1]: right_val, "diff": diff},
                message=msg,
            )
        else:
            return ValidationCheck(
                check_id=check_id,
                name=name,
                description=description,
                status=CheckStatus.FAIL,
                difference=diff,
                tolerance=self.tolerance,
                details={var_names[0]: left_val, var_names[1]: right_val, "diff": diff},
                message=f"Lệch số học kế toán: {var_names[0]} ({left_val:,}) != {var_names[1]} ({right_val:,}), chênh lệch: {diff:,}.",
            )

    @staticmethod
    def _check_mapping_health(report: FinancialReport) -> ValidationCheck:
        """Check overall mapping confidence and flag items needing review."""
        needs_review_count = 0
        unmapped_count = 0

        for stmt in [report.balance_sheet, report.income_statement]:
            if not stmt:
                continue
            for item in stmt.items.values():
                if item.mapping_status.value == "needs_review":
                    needs_review_count += 1
            unmapped_count += len(stmt.unmapped_items)

        if needs_review_count == 0 and unmapped_count == 0:
            return ValidationCheck(
                check_id="MAP_HEALTH_01",
                name="Chất lượng Mapping Semantic",
                description="Toàn bộ khoản mục kế toán cốt lõi đã được ánh xạ tự tin.",
                status=CheckStatus.PASS,
                message="Toàn bộ khoản mục kế toán cốt lõi đã được ánh xạ tự tin.",
            )
        else:
            return ValidationCheck(
                check_id="MAP_HEALTH_01",
                name="Chất lượng Mapping Semantic",
                description="Kiểm tra các khoản mục chưa ánh xạ hoặc cần rà soát thủ công.",
                status=CheckStatus.WARNING,
                details={"needs_review": needs_review_count, "unmapped": unmapped_count},
                message=f"Có {needs_review_count} khoản mục cần rà soát và {unmapped_count} khoản mục chưa ánh xạ.",
            )
