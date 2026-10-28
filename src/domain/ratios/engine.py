"""Động cơ tính toán 14 tỷ số tài chính doanh nghiệp bằng số học Decimal tuyệt đối.

Module này cung cấp:
- RATIO_METADATA: Danh mục từ điển siêu dữ liệu cho toàn bộ 14 chỉ số tài chính chuẩn mực
  thuộc 4 nhóm: Thanh khoản (3 chỉ số), Đòn bẩy (3 chỉ số), Hiệu quả (3 chỉ số), Sinh lời (5 chỉ số).
- FinancialRatioCalculator: Bộ tính toán độc lập thực thi chính xác các công thức kế toán,
  xử lý các tình huống biên (mẫu số bằng 0, vốn chủ sở hữu âm làm méo mó ROE, thiếu số dư đầu kỳ khi tính bình quân).
"""
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.domain.models.bctc import (
    BalanceSheet,
    FinancialReport,
    IncomeStatement,
)
from src.domain.models.line_item import MappingStatus
from src.domain.models.ratios import (
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
)

logger = logging.getLogger(__name__)

# Danh mục định nghĩa và Metadata chi tiết của 14 chỉ số tài chính chuẩn TT200
RATIO_METADATA: Dict[str, Dict[str, Any]] = {
    # 1. Nhóm thanh khoản
    "current_ratio": {
        "name": "Hệ số khả năng thanh toán hiện hành (Current Ratio)",
        "category": RatioCategory.LIQUIDITY,
        "formula": "Tài sản ngắn hạn (100) / Nợ ngắn hạn (310)",
        "unit": "lần",
        "display_format": "{:.2f} lần",
        "input_keys": ["current_assets", "current_liabilities"],
        "description": "Đo lường năng lực của doanh nghiệp trong việc thanh toán các khoản nợ ngắn hạn bằng tài sản ngắn hạn.",
    },
    "quick_ratio": {
        "name": "Hệ số khả năng thanh toán nhanh (Quick Ratio)",
        "category": RatioCategory.LIQUIDITY,
        "formula": "(Tài sản ngắn hạn (100) - Hàng tồn kho (140)) / Nợ ngắn hạn (310)",
        "unit": "lần",
        "display_format": "{:.2f} lần",
        "input_keys": ["current_assets", "inventory", "current_liabilities"],
        "description": "Đo lường khả năng thanh toán ngay lập tức các khoản nợ ngắn hạn mà không cần thanh lý hàng tồn kho.",
    },
    "cash_ratio": {
        "name": "Hệ số khả năng thanh toán tức thời (Cash Ratio)",
        "category": RatioCategory.LIQUIDITY,
        "formula": "Tiền và tương đương tiền (110) / Nợ ngắn hạn (310)",
        "unit": "lần",
        "display_format": "{:.2f} lần",
        "input_keys": ["cash_and_equivalents", "current_liabilities"],
        "description": "Đo lường mức độ đảm bảo của tiền mặt và chứng khoán tương đương tiền đối với nợ ngắn hạn.",
    },

    # 2. Nhóm cơ cấu vốn
    "debt_to_assets": {
        "name": "Hệ số nợ trên tổng tài sản (Debt-to-Assets)",
        "category": RatioCategory.LEVERAGE,
        "formula": "Tổng nợ phải trả (300) / Tổng tài sản (270)",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["liabilities", "total_assets"],
        "description": "Cho biết tỷ trọng tài sản của doanh nghiệp được tài trợ bởi các khoản nợ vay và nợ chiếm dụng.",
    },
    "debt_to_equity": {
        "name": "Hệ số nợ trên vốn chủ sở hữu (Debt-to-Equity)",
        "category": RatioCategory.LEVERAGE,
        "formula": "Tổng nợ phải trả (300) / Vốn chủ sở hữu (400)",
        "unit": "lần",
        "display_format": "{:.2f} lần",
        "input_keys": ["liabilities", "equity"],
        "description": "Đo lường mức độ đòn bẩy tài chính và tương quan giữa vốn vay và vốn chủ sở hữu.",
    },
    "equity_ratio": {
        "name": "Hệ số tự tài trợ (Equity Ratio)",
        "category": RatioCategory.LEVERAGE,
        "formula": "Vốn chủ sở hữu (400) / Tổng tài sản (270)",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["equity", "total_assets"],
        "description": "Thể hiện tỷ lệ tài sản doanh nghiệp được tài trợ từ nguồn vốn tự có.",
    },

    # 3. Nhóm hiệu quả hoạt động
    "total_asset_turnover": {
        "name": "Vòng quay tổng tài sản (Total Asset Turnover)",
        "category": RatioCategory.EFFICIENCY,
        "formula": "Doanh thu thuần (10) / Tổng tài sản bình quân",
        "unit": "vòng",
        "display_format": "{:.2f} vòng",
        "input_keys": ["net_revenue", "total_assets_avg"],
        "description": "Đo lường hiệu quả sử dụng tổng tài sản để tạo ra doanh thu trong kỳ.",
    },
    "inventory_turnover": {
        "name": "Vòng quay hàng tồn kho (Inventory Turnover)",
        "category": RatioCategory.EFFICIENCY,
        "formula": "Giá vốn hàng bán (11) / Hàng tồn kho bình quân",
        "unit": "vòng",
        "display_format": "{:.2f} vòng",
        "input_keys": ["cost_of_goods_sold", "inventory_avg"],
        "description": "Số lần hàng tồn kho được luân chuyển hay bán đi và thay mới trong kỳ kế toán.",
    },
    "receivables_turnover": {
        "name": "Vòng quay các khoản phải thu (Receivables Turnover)",
        "category": RatioCategory.EFFICIENCY,
        "formula": "Doanh thu thuần (10) / Phải thu ngắn hạn bình quân",
        "unit": "vòng",
        "display_format": "{:.2f} vòng",
        "input_keys": ["net_revenue", "short_term_receivables_avg"],
        "description": "Đo lường tốc độ thu hồi nợ từ khách hàng của doanh nghiệp trong kỳ.",
    },

    # 4. Nhóm sinh lời
    "gross_profit_margin": {
        "name": "Tỷ suất lợi nhuận gộp (Gross Profit Margin)",
        "category": RatioCategory.PROFITABILITY,
        "formula": "Lợi nhuận gộp (20) / Doanh thu thuần (10)",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["gross_profit", "net_revenue"],
        "description": "Tỷ lệ phần trăm doanh thu thuần còn lại sau khi trừ đi giá vốn hàng bán.",
    },
    "operating_profit_margin": {
        "name": "Tỷ suất lợi nhuận hoạt động (Operating Profit Margin)",
        "category": RatioCategory.PROFITABILITY,
        "formula": "Lợi nhuận thuần từ HĐKD (30) / Doanh thu thuần (10)",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["operating_profit", "net_revenue"],
        "description": "Đo lường khả năng sinh lời trực tiếp từ hoạt động kinh doanh cốt lõi của công ty.",
    },
    "net_profit_margin": {
        "name": "Tỷ suất lợi nhuận sau thuế (Net Profit Margin)",
        "category": RatioCategory.PROFITABILITY,
        "formula": "Lợi nhuận sau thuế (60) / Doanh thu thuần (10)",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["net_profit_after_tax", "net_revenue"],
        "description": "Tỷ lệ lợi nhuận ròng thu về trên mỗi đồng doanh thu thuần.",
    },
    "roa": {
        "name": "Tỷ suất sinh lời trên tổng tài sản (ROA)",
        "category": RatioCategory.PROFITABILITY,
        "formula": "Lợi nhuận sau thuế (60) / Tổng tài sản bình quân",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["net_profit_after_tax", "total_assets_avg"],
        "description": "Hiệu quả sử dụng tài sản để tạo ra lợi nhuận ròng cho doanh nghiệp.",
    },
    "roe": {
        "name": "Tỷ suất sinh lời trên vốn chủ sở hữu (ROE)",
        "category": RatioCategory.PROFITABILITY,
        "formula": "Lợi nhuận sau thuế (60) / Vốn chủ sở hữu bình quân",
        "unit": "%",
        "display_format": "{:.2%}",
        "input_keys": ["net_profit_after_tax", "equity_avg"],
        "description": "Đo lường mức độ sinh lời trên mỗi đồng vốn của các cổ đông, chủ sở hữu.",
    },
}


class FinancialRatioCalculator:
    """Bộ động cơ tính toán 14 tỷ số tài chính độc lập theo chuẩn Thông tư 200.

    Thực thi toàn bộ các phép tính tỷ số với số học Decimal tuyệt đối,
    tự động đối soát độ tin cậy của chỉ tiêu đầu vào và phân loại trạng thái tỷ số.
    """

    def calculate_all(
        self,
        report: FinancialReport,
        period: str = "current",
    ) -> FinancialRatioReport:
        """Tính toán toàn diện 14 chỉ số tài chính từ Báo cáo tài chính đã qua kiểm định.

        Args:
            report (FinancialReport): Báo cáo tài chính tổng hợp chứa B01-DN và B02-DN.
            period (str): Kỳ kế toán cần tính toán ('current' cho kỳ này, 'previous' cho kỳ trước).

        Returns:
            FinancialRatioReport: Báo cáo tỷ số tổng hợp chứa 14 kết quả RatioResult,
                thống kê số lượng chỉ số hợp lệ, gom nhóm theo 4 phân loại và cảnh báo kiểm toán.
        """
        bs = report.balance_sheet or BalanceSheet()
        is_ = report.income_statement or IncomeStatement()

        ratios: Dict[str, RatioResult] = {}

        # 1. Nhóm thanh khoản (3 chỉ số: current_ratio, quick_ratio, cash_ratio)
        ratios.update(self.calculate_liquidity(bs, period=period))

        # 2. Nhóm cơ cấu vốn / đòn bẩy (3 chỉ số: debt_to_assets, debt_to_equity, equity_ratio)
        ratios.update(self.calculate_leverage(bs, period=period))

        # 3. Nhóm hiệu quả hoạt động (3 chỉ số: total_asset_turnover, inventory_turnover, receivables_turnover)
        ratios.update(self.calculate_efficiency(bs, is_, period=period))

        # 4. Nhóm khả năng sinh lời (5 chỉ số: gross_profit_margin, operating_profit_margin, net_profit_margin, roa, roe)
        ratios.update(self.calculate_profitability(bs, is_, period=period))

        # Phân loại theo category
        categories: Dict[str, List[RatioResult]] = {
            RatioCategory.LIQUIDITY.value: [],
            RatioCategory.LEVERAGE.value: [],
            RatioCategory.EFFICIENCY.value: [],
            RatioCategory.PROFITABILITY.value: [],
        }
        for res in ratios.values():
            categories[res.category.value].append(res)

        calc_count = sum(1 for r in ratios.values() if r.status == RatioStatus.CALCULATED)
        na_count = sum(1 for r in ratios.values() if r.status in (RatioStatus.NOT_AVAILABLE, RatioStatus.NOT_APPLICABLE))
        undef_count = sum(1 for r in ratios.values() if r.status == RatioStatus.UNDEFINED)

        summary = (
            f"Tính toán hoàn tất 14 chỉ số tài chính: {calc_count} chỉ số hợp lệ, "
            f"{na_count} không đủ số liệu/không áp dụng, {undef_count} trạng thái không xác định."
        )

        return FinancialRatioReport(
            company_name=report.company_name,
            fiscal_year=report.fiscal_year,
            as_of_date=getattr(report, "as_of_date", None),
            period=getattr(report, "period", None),
            currency=report.unit,
            ratios=ratios,
            categories=categories,
            total_ratios=len(ratios),
            calculated_ratios=calc_count,
            not_available_ratios=na_count,
            undefined_ratios=undef_count,
            summary=summary,
        )

    def calculate_liquidity(
        self, bs: BalanceSheet, period: str = "current"
    ) -> Dict[str, RatioResult]:
        """Tính toán các chỉ số thuộc Nhóm Thanh Khoản (Liquidity Ratios).

        Bao gồm:
        1. Khả năng thanh toán hiện hành (Current Ratio): TS ngắn hạn (100) / Nợ ngắn hạn (310)
        2. Khả năng thanh toán nhanh (Quick Ratio): (TS ngắn hạn (100) - Hàng tồn kho (140)) / Nợ ngắn hạn (310)
        3. Khả năng thanh toán tức thời (Cash Ratio): Tiền & tương đương tiền (110) / Nợ ngắn hạn (310)

        Args:
            bs (BalanceSheet): Bảng cân đối kế toán.
            period (str): Kỳ kế toán cần tính ('current' hoặc 'previous').

        Returns:
            Dict[str, RatioResult]: Từ điển chứa 3 kết quả chỉ số thanh khoản.
        """
        results: Dict[str, RatioResult] = {}

        ca = bs.get_value("current_assets", period)
        cl = bs.get_value("current_liabilities", period)
        inv = bs.get_value("inventory", period)
        cash = bs.get_value("cash_and_equivalents", period)

        ca_warn = self._check_item_reliability(bs, "current_assets")
        cl_warn = self._check_item_reliability(bs, "current_liabilities")
        inv_warn = self._check_item_reliability(bs, "inventory")
        cash_warn = self._check_item_reliability(bs, "cash_and_equivalents")

        results["current_ratio"] = self._compute_simple_ratio(
            ratio_key="current_ratio",
            numerator=ca,
            denominator=cl,
            num_name="Tài sản ngắn hạn (100)",
            den_name="Nợ ngắn hạn (310)",
            inputs={"current_assets": ca, "current_liabilities": cl},
            custom_warnings=ca_warn + cl_warn,
        )

        quick_inputs = {"current_assets": ca, "inventory": inv, "current_liabilities": cl}
        quick_warnings = ca_warn + cl_warn + inv_warn
        if ca is not None and inv is None:
            quick_warnings.append("Hàng tồn kho không có số liệu; không thể suy đoán bằng 0 khi tính Quick Ratio.")
            results["quick_ratio"] = self._build_unavailable_result(
                "quick_ratio",
                inputs=quick_inputs,
                warnings=quick_warnings + ["Thiếu dữ liệu Hàng tồn kho (140)."],
            )
        elif ca is not None and inv is not None:
            quick_assets = ca - inv
            results["quick_ratio"] = self._compute_simple_ratio(
                ratio_key="quick_ratio",
                numerator=quick_assets,
                denominator=cl,
                num_name="Tài sản nhanh (TSNH - HTK)",
                den_name="Nợ ngắn hạn (310)",
                inputs=quick_inputs,
                custom_warnings=quick_warnings,
            )
        else:
            missing = []
            if ca is None:
                missing.append("Tài sản ngắn hạn (100)")
            if cl is None:
                missing.append("Nợ ngắn hạn (310)")
            results["quick_ratio"] = self._build_unavailable_result(
                "quick_ratio",
                inputs=quick_inputs,
                warnings=quick_warnings + [f"Thiếu dữ liệu đầu vào bắt buộc: {', '.join(missing)}."],
            )

        results["cash_ratio"] = self._compute_simple_ratio(
            ratio_key="cash_ratio",
            numerator=cash,
            denominator=cl,
            num_name="Tiền và tương đương tiền (110)",
            den_name="Nợ ngắn hạn (310)",
            inputs={"cash_and_equivalents": cash, "current_liabilities": cl},
            custom_warnings=cash_warn + cl_warn,
        )

        return results

    def calculate_leverage(
        self, bs: BalanceSheet, period: str = "current"
    ) -> Dict[str, RatioResult]:
        """Tính toán các chỉ số thuộc Nhóm Cơ Cấu Vốn / Đòn Bẩy Tài Chính (Leverage Ratios).

        Bao gồm:
        1. Hệ số Nợ / Tổng tài sản (Debt to Assets): Tổng nợ (300) / Tổng tài sản (270)
        2. Hệ số Nợ / Vốn CSH (Debt to Equity): Tổng nợ (300) / Vốn chủ sở hữu (400)
        3. Hệ số Tự tài trợ (Equity Ratio): Vốn chủ sở hữu (400) / Tổng tài sản (270)

        Note:
            Nếu Vốn chủ sở hữu âm (do lỗ lũy kế vượt vốn góp), tỷ số Debt to Equity sẽ mang
            trạng thái UNDEFINED kèm cảnh báo mất an toàn tài chính cực kỳ nghiêm trọng.

        Args:
            bs (BalanceSheet): Bảng cân đối kế toán.
            period (str): Kỳ kế toán cần tính ('current' hoặc 'previous').

        Returns:
            Dict[str, RatioResult]: Từ điển chứa 3 kết quả chỉ số cơ cấu vốn.
        """
        results: Dict[str, RatioResult] = {}

        liab = bs.get_value("liabilities", period)
        ta = bs.get_value("total_assets", period)
        eq = bs.get_value("equity", period)

        liab_warn = self._check_item_reliability(bs, "liabilities")
        ta_warn = self._check_item_reliability(bs, "total_assets")
        eq_warn = self._check_item_reliability(bs, "equity")

        results["debt_to_assets"] = self._compute_simple_ratio(
            ratio_key="debt_to_assets",
            numerator=liab,
            denominator=ta,
            num_name="Tổng nợ phải trả (300)",
            den_name="Tổng tài sản (270)",
            inputs={"liabilities": liab, "total_assets": ta},
            custom_warnings=liab_warn + ta_warn,
        )

        d_e_warnings = liab_warn + eq_warn
        if eq is not None and eq < Decimal("0"):
            d_e_warnings.append(
                "Vốn chủ sở hữu âm do lỗ lũy kế vượt vốn góp. Tỷ số Nợ/VCSH mang dấu âm, "
                "không phản ánh đòn bẩy thông thường và cảnh báo rủi ro mất an toàn tài chính cực kỳ nghiêm trọng."
            )
            raw_res = self._compute_simple_ratio(
                ratio_key="debt_to_equity",
                numerator=liab,
                denominator=eq,
                num_name="Tổng nợ phải trả (300)",
                den_name="Vốn chủ sở hữu (400)",
                inputs={"liabilities": liab, "equity": eq},
                custom_warnings=d_e_warnings,
            )
            raw_res.status = RatioStatus.UNDEFINED
            results["debt_to_equity"] = raw_res
        else:
            results["debt_to_equity"] = self._compute_simple_ratio(
                ratio_key="debt_to_equity",
                numerator=liab,
                denominator=eq,
                num_name="Tổng nợ phải trả (300)",
                den_name="Vốn chủ sở hữu (400)",
                inputs={"liabilities": liab, "equity": eq},
                custom_warnings=d_e_warnings,
            )

        eq_ratio_warnings = eq_warn + ta_warn
        if eq is not None and eq < Decimal("0"):
            eq_ratio_warnings.append("Vốn chủ sở hữu âm; tỷ lệ tự tài trợ mang giá trị âm.")
        results["equity_ratio"] = self._compute_simple_ratio(
            ratio_key="equity_ratio",
            numerator=eq,
            denominator=ta,
            num_name="Vốn chủ sở hữu (400)",
            den_name="Tổng tài sản (270)",
            inputs={"equity": eq, "total_assets": ta},
            custom_warnings=eq_ratio_warnings,
        )

        return results

    def calculate_efficiency(
        self,
        bs: BalanceSheet,
        is_: IncomeStatement,
        period: str = "current",
    ) -> Dict[str, RatioResult]:
        """Tính toán các chỉ số thuộc Nhóm Hiệu Quả Hoạt Động (Efficiency Ratios).

        Sử dụng số dư bình quân = (Số đầu kỳ + Số cuối kỳ) / 2 theo chuẩn mực kế toán tài chính:
        1. Vòng quay tổng tài sản: Doanh thu thuần (10) / Tổng tài sản bình quân
        2. Vòng quay hàng tồn kho: Giá vốn hàng bán (11) / Hàng tồn kho bình quân
        3. Vòng quay các khoản phải thu: Doanh thu thuần (10) / Phải thu ngắn hạn bình quân

        Args:
            bs (BalanceSheet): Bảng cân đối kế toán (cung cấp số dư đầu kỳ và cuối kỳ).
            is_ (IncomeStatement): Báo cáo kết quả hoạt động kinh doanh.
            period (str): Kỳ kế toán cần tính ('current' hoặc 'previous').

        Returns:
            Dict[str, RatioResult]: Từ điển chứa 3 kết quả chỉ số hiệu quả hoạt động.
        """
        results: Dict[str, RatioResult] = {}

        net_rev = is_.get_value("net_revenue", period)
        cogs = is_.get_value("cost_of_goods_sold", period)

        rev_warn = self._check_item_reliability(is_, "net_revenue")
        cogs_warn = self._check_item_reliability(is_, "cost_of_goods_sold")

        avg_ta, ta_err = self.compute_average_balance(bs, "total_assets")
        ta_avg_warn = rev_warn + (self._check_item_reliability(bs, "total_assets"))
        if ta_err:
            ta_avg_warn.append(ta_err)
        results["total_asset_turnover"] = self._compute_turnover_ratio(
            ratio_key="total_asset_turnover",
            numerator=net_rev,
            denominator=avg_ta,
            num_name="Doanh thu thuần (10)",
            den_name="Tổng tài sản bình quân",
            inputs={"net_revenue": net_rev, "total_assets_avg": avg_ta},
            custom_warnings=ta_avg_warn,
        )

        avg_inv, inv_err = self.compute_average_balance(bs, "inventory")
        inv_avg_warn = cogs_warn + (self._check_item_reliability(bs, "inventory"))
        if inv_err:
            inv_avg_warn.append(inv_err)
        results["inventory_turnover"] = self._compute_turnover_ratio(
            ratio_key="inventory_turnover",
            numerator=cogs,
            denominator=avg_inv,
            num_name="Giá vốn hàng bán (11)",
            den_name="Hàng tồn kho bình quân",
            inputs={"cost_of_goods_sold": cogs, "inventory_avg": avg_inv},
            custom_warnings=inv_avg_warn,
        )

        avg_rec, rec_err = self.compute_average_balance(bs, "short_term_receivables")
        rec_avg_warn = rev_warn + (self._check_item_reliability(bs, "short_term_receivables"))
        if rec_err:
            rec_avg_warn.append(rec_err)
        results["receivables_turnover"] = self._compute_turnover_ratio(
            ratio_key="receivables_turnover",
            numerator=net_rev,
            denominator=avg_rec,
            num_name="Doanh thu thuần (10)",
            den_name="Phải thu ngắn hạn bình quân",
            inputs={"net_revenue": net_rev, "short_term_receivables_avg": avg_rec},
            custom_warnings=rec_avg_warn,
        )

        return results

    def calculate_profitability(
        self,
        bs: BalanceSheet,
        is_: IncomeStatement,
        period: str = "current",
    ) -> Dict[str, RatioResult]:
        """Tính toán các chỉ số thuộc Nhóm Khả Năng Sinh Lời (Profitability Ratios).

        Bao gồm:
        1. Biên lợi nhuận gộp (Gross Profit Margin): Lợi nhuận gộp (20) / Doanh thu thuần (10)
        2. Biên lợi nhuận hoạt động (Operating Profit Margin): LN thuần HĐKD (30) / Doanh thu thuần (10)
        3. Biên lợi nhuận ròng (Net Profit Margin): LN sau thuế (60) / Doanh thu thuần (10)
        4. Tỷ suất sinh lời trên tài sản (ROA): LN sau thuế (60) / Tổng tài sản bình quân
        5. Tỷ suất sinh lời trên vốn CSH (ROE): LN sau thuế (60) / Vốn chủ sở hữu bình quân

        Note:
            Nếu Vốn chủ sở hữu bình quân <= 0 (do âm vốn), ROE sẽ được gán trạng thái UNDEFINED
            kèm cảnh báo kinh tế đặc thù (ngăn chặn tình trạng âm chia âm ra dương làm sai lệch nhận định).

        Args:
            bs (BalanceSheet): Bảng cân đối kế toán.
            is_ (IncomeStatement): Báo cáo kết quả kinh doanh.
            period (str): Kỳ kế toán cần tính ('current' hoặc 'previous').

        Returns:
            Dict[str, RatioResult]: Từ điển chứa 5 kết quả chỉ số sinh lời.
        """
        results: Dict[str, RatioResult] = {}

        net_rev = is_.get_value("net_revenue", period)
        gp = is_.get_value("gross_profit", period)
        op = is_.get_value("operating_profit", period)
        npat = is_.get_value("net_profit_after_tax", period)

        rev_warn = self._check_item_reliability(is_, "net_revenue")
        gp_warn = self._check_item_reliability(is_, "gross_profit")
        op_warn = self._check_item_reliability(is_, "operating_profit")
        npat_warn = self._check_item_reliability(is_, "net_profit_after_tax")

        results["gross_profit_margin"] = self._compute_margin_ratio(
            ratio_key="gross_profit_margin",
            numerator=gp,
            denominator=net_rev,
            num_name="Lợi nhuận gộp (20)",
            den_name="Doanh thu thuần (10)",
            inputs={"gross_profit": gp, "net_revenue": net_rev},
            custom_warnings=gp_warn + rev_warn,
        )

        results["operating_profit_margin"] = self._compute_margin_ratio(
            ratio_key="operating_profit_margin",
            numerator=op,
            denominator=net_rev,
            num_name="Lợi nhuận thuần từ HĐKD (30)",
            den_name="Doanh thu thuần (10)",
            inputs={"operating_profit": op, "net_revenue": net_rev},
            custom_warnings=op_warn + rev_warn,
        )

        results["net_profit_margin"] = self._compute_margin_ratio(
            ratio_key="net_profit_margin",
            numerator=npat,
            denominator=net_rev,
            num_name="Lợi nhuận sau thuế (60)",
            den_name="Doanh thu thuần (10)",
            inputs={"net_profit_after_tax": npat, "net_revenue": net_rev},
            custom_warnings=npat_warn + rev_warn,
        )

        avg_ta, ta_err = self.compute_average_balance(bs, "total_assets")
        roa_warnings = npat_warn + self._check_item_reliability(bs, "total_assets")
        if ta_err:
            roa_warnings.append(ta_err)
        results["roa"] = self._compute_return_ratio(
            ratio_key="roa",
            numerator=npat,
            denominator=avg_ta,
            num_name="Lợi nhuận sau thuế (60)",
            den_name="Tổng tài sản bình quân",
            inputs={"net_profit_after_tax": npat, "total_assets_avg": avg_ta},
            custom_warnings=roa_warnings,
        )

        avg_eq, eq_err = self.compute_average_balance(bs, "equity")
        roe_warnings = npat_warn + self._check_item_reliability(bs, "equity")
        if eq_err:
            roe_warnings.append(eq_err)

        if avg_eq is not None and avg_eq <= Decimal("0"):
            if npat is not None and npat < Decimal("0"):
                roe_warnings.append(
                    "Vốn chủ sở hữu bình quân âm và Lợi nhuận sau thuế âm. "
                    "Phép chia toán học cho giá trị dương nhưng không phản ánh khả năng sinh lời, "
                    "thực chất là doanh nghiệp lỗ lũy kế vượt vốn góp; tỷ số ROE này không có ý nghĩa chuẩn."
                )
            else:
                roe_warnings.append(
                    "Vốn chủ sở hữu bình quân âm; tỷ số ROE không có ý nghĩa kinh tế thông thường "
                    "và cảnh báo doanh nghiệp bị âm vốn chủ sở hữu do lỗ lũy kế kéo dài."
                )
            raw_roe = self._compute_return_ratio(
                ratio_key="roe",
                numerator=npat,
                denominator=avg_eq,
                num_name="Lợi nhuận sau thuế (60)",
                den_name="Vốn chủ sở hữu bình quân",
                inputs={"net_profit_after_tax": npat, "equity_avg": avg_eq},
                custom_warnings=roe_warnings,
            )
            raw_roe.status = RatioStatus.UNDEFINED
            results["roe"] = raw_roe
        else:
            results["roe"] = self._compute_return_ratio(
                ratio_key="roe",
                numerator=npat,
                denominator=avg_eq,
                num_name="Lợi nhuận sau thuế (60)",
                den_name="Vốn chủ sở hữu bình quân",
                inputs={"net_profit_after_tax": npat, "equity_avg": avg_eq},
                custom_warnings=roe_warnings,
            )

        return results

    @staticmethod
    def compute_average_balance(
        bs: Optional[BalanceSheet], canonical_key: str
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """Tính toán Số dư bình quân kế toán = (Số đầu kỳ + Số cuối kỳ) / 2.

        Tuân thủ nghiêm ngặt chuẩn mực phân tích tài chính: Yêu cầu bắt buộc phải có
        cả số dư đầu kỳ và cuối kỳ. Hệ thống tuyệt đối không tự ý lấy số cuối kỳ
        thay thế cho số bình quân để đảm bảo tính khách quan và khoa học.

        Args:
            bs (Optional[BalanceSheet]): Bảng cân đối kế toán.
            canonical_key (str): Mã chỉ tiêu cần tính bình quân (VD: 'total_assets', 'inventory').

        Returns:
            Tuple[Optional[Decimal], Optional[str]]: (Giá trị bình quân Decimal, Thông điệp cảnh báo nếu thiếu số liệu).
        """
        if bs is None:
            return None, "Bảng cân đối kế toán không tồn tại."

        end_val = bs.get_value(canonical_key, period="current")
        beg_val = bs.get_value(canonical_key, period="previous")

        if end_val is None and beg_val is None:
            return None, f"Không có dữ liệu số dư đầu kỳ và cuối kỳ cho chỉ tiêu '{canonical_key}'."
        if end_val is None:
            return None, f"Thiếu số dư cuối kỳ cho chỉ tiêu '{canonical_key}' để tính bình quân."
        if beg_val is None:
            return None, (
                f"Thiếu số dư đầu kỳ cho chỉ tiêu '{canonical_key}' để tính bình quân; "
                f"hệ thống không tự ý lấy số cuối kỳ thay thế."
            )

        avg_val = (beg_val + end_val) / Decimal("2")
        return avg_val, None

    def _compute_simple_ratio(
        self,
        ratio_key: str,
        numerator: Optional[Decimal],
        denominator: Optional[Decimal],
        num_name: str,
        den_name: str,
        inputs: Dict[str, Optional[Decimal]],
        custom_warnings: List[str] = None,
    ) -> RatioResult:
        """Calculate simple A / B ratio with zero division and negativity protections."""
        meta = RATIO_METADATA[ratio_key]
        warnings = list(custom_warnings or [])

        if numerator is None or denominator is None:
            missing = []
            if numerator is None:
                missing.append(num_name)
            if denominator is None:
                missing.append(den_name)
            warnings.append(f"Chưa đủ dữ liệu để tính toán: thiếu {', '.join(missing)}.")
            return self._build_unavailable_result(ratio_key, inputs=inputs, warnings=warnings)

        if denominator == Decimal("0"):
            warnings.append(f"Mẫu số bằng 0 ({den_name} = 0); tỷ số không thể xác định.")
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=None,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value="N/A",
                status=RatioStatus.NOT_APPLICABLE,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        if denominator < Decimal("0"):
            warnings.append(f"Mẫu số mang giá trị âm ({den_name} = {denominator:,}); tỷ số không có ý nghĩa kinh tế chuẩn.")
            val = numerator / denominator
            formatted = self._format_value(val, meta["display_format"], meta["unit"])
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=val,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value=formatted,
                status=RatioStatus.UNDEFINED,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        val = numerator / denominator
        formatted = self._format_value(val, meta["display_format"], meta["unit"])

        return RatioResult(
            ratio_key=ratio_key,
            name=meta["name"],
            category=meta["category"],
            value=val,
            unit=meta["unit"],
            display_format=meta["display_format"],
            formatted_value=formatted,
            status=RatioStatus.CALCULATED,
            formula=meta["formula"],
            input_keys=meta["input_keys"],
            inputs=inputs,
            warnings=warnings,
            description=meta["description"],
        )

    def _compute_turnover_ratio(
        self,
        ratio_key: str,
        numerator: Optional[Decimal],
        denominator: Optional[Decimal],
        num_name: str,
        den_name: str,
        inputs: Dict[str, Optional[Decimal]],
        custom_warnings: List[str] = None,
    ) -> RatioResult:
        """Calculate turnover ratio (Vòng quay = Doanh thu hoặc Giá vốn / Số dư bình quân)."""
        meta = RATIO_METADATA[ratio_key]
        warnings = list(custom_warnings or [])

        if numerator is None or denominator is None:
            missing = []
            if numerator is None:
                missing.append(num_name)
            if denominator is None:
                missing.append(den_name)
            warnings.append(f"Chưa đủ dữ liệu để tính vòng quay: thiếu {', '.join(missing)}.")
            return self._build_unavailable_result(ratio_key, inputs=inputs, warnings=warnings)

        if denominator == Decimal("0"):
            warnings.append(f"Mẫu số bằng 0 ({den_name} = 0); vòng quay không thể xác định.")
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=None,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value="N/A",
                status=RatioStatus.NOT_APPLICABLE,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        if denominator < Decimal("0"):
            warnings.append(f"Số dư bình quân âm ({den_name} = {denominator:,}); chỉ số không hợp lệ.")
            val = numerator / denominator
            formatted = self._format_value(val, meta["display_format"], meta["unit"])
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=val,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value=formatted,
                status=RatioStatus.UNDEFINED,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        val = numerator / denominator
        formatted = self._format_value(val, meta["display_format"], meta["unit"])

        return RatioResult(
            ratio_key=ratio_key,
            name=meta["name"],
            category=meta["category"],
            value=val,
            unit=meta["unit"],
            display_format=meta["display_format"],
            formatted_value=formatted,
            status=RatioStatus.CALCULATED,
            formula=meta["formula"],
            input_keys=meta["input_keys"],
            inputs=inputs,
            warnings=warnings,
            description=meta["description"],
        )

    def _compute_margin_ratio(
        self,
        ratio_key: str,
        numerator: Optional[Decimal],
        denominator: Optional[Decimal],
        num_name: str,
        den_name: str,
        inputs: Dict[str, Optional[Decimal]],
        custom_warnings: List[str] = None,
    ) -> RatioResult:
        """Calculate profit margin ratio (Tỷ suất lợi nhuận = Lợi nhuận / Doanh thu thuần)."""
        meta = RATIO_METADATA[ratio_key]
        warnings = list(custom_warnings or [])

        if numerator is None or denominator is None:
            missing = []
            if numerator is None:
                missing.append(num_name)
            if denominator is None:
                missing.append(den_name)
            warnings.append(f"Chưa đủ dữ liệu để tính biên lợi nhuận: thiếu {', '.join(missing)}.")
            return self._build_unavailable_result(ratio_key, inputs=inputs, warnings=warnings)

        if denominator == Decimal("0"):
            warnings.append("Doanh thu thuần bằng 0; không thể xác định tỷ suất sinh lời trên doanh thu.")
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=None,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value="N/A",
                status=RatioStatus.NOT_APPLICABLE,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        if denominator < Decimal("0"):
            warnings.append(
                f"Doanh thu thuần âm ({denominator:,}) do các khoản giảm trừ vượt doanh thu; "
                f"tỷ suất lợi nhuận không có ý nghĩa kinh tế chuẩn."
            )
            val = numerator / denominator
            formatted = self._format_value(val, meta["display_format"], meta["unit"])
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=val,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value=formatted,
                status=RatioStatus.UNDEFINED,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        val = numerator / denominator
        formatted = self._format_value(val, meta["display_format"], meta["unit"])

        return RatioResult(
            ratio_key=ratio_key,
            name=meta["name"],
            category=meta["category"],
            value=val,
            unit=meta["unit"],
            display_format=meta["display_format"],
            formatted_value=formatted,
            status=RatioStatus.CALCULATED,
            formula=meta["formula"],
            input_keys=meta["input_keys"],
            inputs=inputs,
            warnings=warnings,
            description=meta["description"],
        )

    def _compute_return_ratio(
        self,
        ratio_key: str,
        numerator: Optional[Decimal],
        denominator: Optional[Decimal],
        num_name: str,
        den_name: str,
        inputs: Dict[str, Optional[Decimal]],
        custom_warnings: List[str] = None,
    ) -> RatioResult:
        """Calculate return ratios on average base (ROA, ROE)."""
        meta = RATIO_METADATA[ratio_key]
        warnings = list(custom_warnings or [])

        if numerator is None or denominator is None:
            missing = []
            if numerator is None:
                missing.append(num_name)
            if denominator is None:
                missing.append(den_name)
            warnings.append(f"Chưa đủ dữ liệu để tính tỷ suất: thiếu {', '.join(missing)}.")
            return self._build_unavailable_result(ratio_key, inputs=inputs, warnings=warnings)

        if denominator == Decimal("0"):
            warnings.append(f"Mẫu số bằng 0 ({den_name} = 0); không thể xác định tỷ suất sinh lời.")
            return RatioResult(
                ratio_key=ratio_key,
                name=meta["name"],
                category=meta["category"],
                value=None,
                unit=meta["unit"],
                display_format=meta["display_format"],
                formatted_value="N/A",
                status=RatioStatus.NOT_APPLICABLE,
                formula=meta["formula"],
                input_keys=meta["input_keys"],
                inputs=inputs,
                warnings=warnings,
                description=meta["description"],
            )

        val = numerator / denominator
        formatted = self._format_value(val, meta["display_format"], meta["unit"])

        status = RatioStatus.CALCULATED
        if denominator < Decimal("0"):
            status = RatioStatus.UNDEFINED

        return RatioResult(
            ratio_key=ratio_key,
            name=meta["name"],
            category=meta["category"],
            value=val,
            unit=meta["unit"],
            display_format=meta["display_format"],
            formatted_value=formatted,
            status=status,
            formula=meta["formula"],
            input_keys=meta["input_keys"],
            inputs=inputs,
            warnings=warnings,
            description=meta["description"],
        )

    def _build_unavailable_result(
        self,
        ratio_key: str,
        inputs: Dict[str, Optional[Decimal]],
        warnings: List[str],
    ) -> RatioResult:
        """Build a standard NOT_AVAILABLE ratio result object."""
        meta = RATIO_METADATA[ratio_key]
        return RatioResult(
            ratio_key=ratio_key,
            name=meta["name"],
            category=meta["category"],
            value=None,
            unit=meta["unit"],
            display_format=meta["display_format"],
            formatted_value="N/A",
            status=RatioStatus.NOT_AVAILABLE,
            formula=meta["formula"],
            input_keys=meta["input_keys"],
            inputs=inputs,
            warnings=warnings,
            description=meta["description"],
        )

    @staticmethod
    def _format_value(value: Decimal, display_format: str, unit: str) -> str:
        """Present a Decimal ratio cleanly with standard 2 decimal places."""
        if "%" in display_format:
            pct_val = (value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{pct_val:.2f}%"
        else:
            dec_val = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{dec_val:.2f} {unit}"

    @staticmethod
    def _check_item_reliability(statement: Optional[Any], canonical_key: str) -> List[str]:
        """Audit warnings and needs_review flags on the input line item."""
        warnings: List[str] = []
        if not statement or not hasattr(statement, "items"):
            return warnings
        item = statement.items.get(canonical_key)
        if item:
            if item.mapping_status == MappingStatus.NEEDS_REVIEW:
                warnings.append(
                    f"Khoản mục đầu vào '{canonical_key}' ({item.raw_label}) đang ở trạng thái cần rà soát (needs_review)."
                )
            if item.confidence_score < 0.7 and item.confidence_score > 0.0:
                warnings.append(
                    f"Khoản mục '{canonical_key}' có độ tin cậy mapping thấp ({item.confidence_score:.2f})."
                )
            for w in item.warnings:
                warnings.append(f"Cảnh báo khoản mục '{canonical_key}': {w}")
        return warnings
