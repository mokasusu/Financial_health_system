"""Kiểm định các đẳng thức cân đối kế toán theo Thông tư 200/2014/TT-BTC.

Module này cung cấp công cụ kiểm định toàn diện (FinancialValidator) thực thi
4 đẳng thức cân đối kế toán trọng yếu của Việt Nam và các phép kiểm tra số học:
1. Đẳng thức 1: Tổng Tài sản (270) == Tổng Nguồn vốn (440)
2. Đẳng thức 2: Tổng Tài sản (270) == Tài sản ngắn hạn (100) + Tài sản dài hạn (200)
3. Đẳng thức 3: Tổng Nguồn vốn (440) == Nợ phải trả (300) + Vốn chủ sở hữu (400)
4. Đẳng thức 4: Nợ phải trả (300) == Nợ ngắn hạn (310) + Nợ dài hạn (330)
5. Tính cân đối Doanh thu thuần và Lợi nhuận gộp trên Báo cáo KQKD (B02-DN)
Toàn bộ các phép so sánh sử dụng kiểu Decimal kèm ngưỡng dung sai làm tròn (tolerance).
"""
from decimal import Decimal
import logging
from typing import List, Optional, Tuple

from src.domain.models.bctc import (
    BalanceSheet,
    FinancialReport,
    IncomeStatement,
    ValidationCheck,
    ValidationResult,
)
from src.domain.models.line_item import CheckStatus

logger = logging.getLogger(__name__)

# Mức dung sai làm tròn mặc định chấp nhận được trong kế toán (VD: 1.000 VND)
DEFAULT_ROUNDING_TOLERANCE = Decimal("1000")


class FinancialValidator:
    """Động cơ kiểm định tính cân đối và nhất quán số liệu kế toán TT200.

    Attributes:
        tolerance (Decimal): Mức chênh lệch tối đa do làm tròn số được coi là PASS.
    """

    def __init__(self, tolerance: Decimal = DEFAULT_ROUNDING_TOLERANCE):
        """Khởi tạo bộ kiểm định kế toán với mức dung sai làm tròn.

        Args:
            tolerance (Decimal): Mức dung sai chấp nhận được (mặc định 1.000 VND).
        """
        self.tolerance = abs(tolerance)

    def validate(self, report: FinancialReport, period: str = "current") -> ValidationResult:
        """Thực thi toàn bộ các phép kiểm tra kế toán trên BCTC cho một kỳ cụ thể.

        Args:
            report (FinancialReport): Báo cáo tài chính tổng hợp chứa B01-DN và B02-DN.
            period (str): Kỳ kế toán cần kiểm tra ('current' hoặc 'previous').

        Returns:
            ValidationResult: Báo cáo kết quả kiểm định tổng hợp (PASS, WARNING, FAIL).
        """
        checks: List[ValidationCheck] = []

        # 1. Kiểm tra các đẳng thức trên Bảng Cân Đối Kế Toán
        if report.balance_sheet:
            checks.extend(self._validate_balance_sheet(report.balance_sheet, period))

        # 2. Kiểm tra các đẳng thức trên Báo Cáo Kết Quả Kinh Doanh
        if report.income_statement:
            checks.extend(self._validate_income_statement(report.income_statement, period))

        # 3. Đánh giá chất lượng ánh xạ chỉ tiêu (Semantic Mapping Health)
        checks.append(self._check_mapping_health(report))

        # Tổng hợp số liệu thống kê
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
        """Kiểm định 4 đẳng thức cân đối kế toán nền tảng của Bảng cân đối kế toán.

        Args:
            bs (BalanceSheet): Đối tượng Bảng cân đối kế toán Mẫu B01-DN.
            period (str): Kỳ phân tích ('current' hoặc 'previous').

        Returns:
            List[ValidationCheck]: Danh sách kết quả kiểm định chi tiết của 4 đẳng thức.
        """
        checks: List[ValidationCheck] = []

        # Đẳng thức 1: TỔNG TÀI SẢN = TỔNG NGUỒN VỐN (MS 270 = MS 440)
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

        # Đẳng thức 2: TỔNG TÀI SẢN = TÀI SẢN NGẮN HẠN + TÀI SẢN DÀI HẠN (MS 270 = MS 100 + MS 200)
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

        # Đẳng thức 3: TỔNG NGUỒN VỐN = NỢ PHẢI TRẢ + VỐN CHỦ SỞ HỮU (MS 440 = MS 300 + MS 400)
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

        # Đẳng thức 4: NỢ PHẢI TRẢ = NỢ NGẮN HẠN + NỢ DÀI HẠN (MS 300 = MS 310 + MS 330)
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
        """Kiểm định các đẳng thức số học trên Báo cáo Kết quả kinh doanh (Mẫu B02-DN).

        Args:
            is_ (IncomeStatement): Đối tượng Báo cáo KQKD.
            period (str): Kỳ phân tích ('current' hoặc 'previous').

        Returns:
            List[ValidationCheck]: Danh sách kết quả kiểm định của báo cáo KQKD.
        """
        checks: List[ValidationCheck] = []

        # Kiểm tra 5: Doanh thu thuần = Doanh thu bán hàng - Giảm trừ doanh thu (MS 10 = MS 01 - MS 02)
        gross_rev = is_.get_value("gross_revenue", period)
        rev_ded = is_.get_value("revenue_deductions", period)
        net_rev = is_.get_value("net_revenue", period)

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

        # Kiểm tra 6: Lợi nhuận gộp = Doanh thu thuần - Giá vốn hàng bán (MS 20 = MS 10 - MS 11)
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

        # Kiểm tra 7: Lợi nhuận kế toán trước thuế (MS 50 = MS 30 + MS 40)
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
        var_names: Tuple[str, str],
    ) -> ValidationCheck:
        """Đánh giá an toàn đẳng thức giữa hai vế số học Decimal kèm dung sai làm tròn.

        Args:
            check_id (str): Mã định danh kiểm định.
            name (str): Tên hiển thị của phép kiểm.
            description (str): Mô tả công thức kế toán.
            left_val (Optional[Decimal]): Giá trị vế trái đẳng thức.
            right_val (Optional[Decimal]): Giá trị vế phải đẳng thức.
            var_names (Tuple[str, str]): Tên mô tả hai vế (vế trái, vế phải).

        Returns:
            ValidationCheck: Kết quả đánh giá (PASS, FAIL hoặc NOT_CHECKABLE).
        """
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
        """Đánh giá tổng thể chất lượng ánh xạ chỉ tiêu và phát hiện các dòng cần rà soát thủ công.

        Args:
            report (FinancialReport): Báo cáo tài chính tổng hợp.

        Returns:
            ValidationCheck: Kết quả đánh giá sức khỏe ánh xạ (PASS hoặc WARNING).
        """
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
