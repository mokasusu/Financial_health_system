"""Modular Streamlit UI components for Financial Health Dashboard (Sprint 6).

Implements reusable, defensive rendering functions:
- Header and document provenance
- Executive KPI cards with emerald styling
- Health assessment synthesis and categorized risk warnings
- 4-Group ratio analysis tabs (Liquidity, Leverage, Efficiency, Profitability)
- Financial statement data tables and TT200 balance validation audit
- AI interpretation and deterministic fallback presentation
- Structured JSON and CSV export actions
"""
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st

from src.data.normalizer import AccountingNumberNormalizer
from src.data.schema import CheckStatus, FinancialReport, MappingStatus
from src.data.validator import FinancialValidator
from src.financial.ai_models import AIInterpretationOutput, AIRiskItem, AIStrengthItem
from src.financial.assessment_models import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    OverallHealthStatus,
    RatioAssessment,
    WarningSeverity,
)
from src.financial.ratios import (
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
)
from src.ui.export import (
    export_analysis_to_json,
    export_ratios_to_csv,
    export_warnings_to_csv,
)
from src.ui.formatters import (
    format_currency,
    format_difference,
    format_percentage,
    format_ratio_value,
)
from src.ui.styles import (
    COLOR_PRIMARY_EMERALD,
    get_overall_health_banner_html,
    get_severity_badge_html,
    get_status_badge_html,
)


def render_header(
    company_name: Optional[str],
    fiscal_year: Optional[int],
    currency: str = "VND",
    source_name: Optional[str] = None,
    extraction_method: Optional[str] = None,
) -> None:
    """Render the dashboard top banner with company and document metadata."""
    display_company = company_name or "Doanh nghiệp (Chưa xác định tên từ BCTC)"
    display_year = f"Năm tài chính: {fiscal_year}" if fiscal_year else "Năm tài chính: Chưa xác định"
    display_source = f"Nguồn: {source_name}" if source_name else "Nguồn: Tải lên trực tiếp"
    display_method = f"Phương thức: {extraction_method}" if extraction_method else "Chuẩn hóa TT200"

    header_html = f"""
    <div class="dashboard-header">
        <h1>📊 BÁO CÁO PHÂN TÍCH SỨC KHỎE TÀI CHÍNH DOANH NGHIỆP</h1>
        <p><strong>{display_company}</strong></p>
        <div style="margin-top: 0.5rem;">
            <span class="meta-tag">📅 {display_year}</span>
            <span class="meta-tag">💰 Đơn vị: {currency}</span>
            <span class="meta-tag">📄 {display_source}</span>
            <span class="meta-tag">🔍 {display_method}</span>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_top_action_bar(
    assessment: FinancialAssessment,
    ai_output: Optional[AIInterpretationOutput] = None,
    report: Optional[FinancialReport] = None,
) -> None:
    """Render top action bar with compact metadata and quick JSON/CSV download buttons."""
    c_info, c_btn1, c_btn2 = st.columns([2.5, 1, 1])
    company_name = assessment.company_name or "Doanh nghiệp"
    year_str = f"Năm {assessment.fiscal_year}" if assessment.fiscal_year else "Kỳ phân tích"
    company_tag = company_name.replace(" ", "_")
    fiscal_tag = assessment.fiscal_year or "period"

    with c_info:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; padding-top: 0.25rem;">
                <span style="font-size: 1.15rem; font-weight: 700; color: #006c49;">🏢 {company_name}</span>
                <span class="meta-tag" style="background: #e6f4ef; color: #006c49; border: 1px solid #a7f3d0;">📅 {year_str}</span>
                <span class="meta-tag" style="background: #f1f5f9; color: #475569;">💰 {assessment.currency}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_btn1:
        json_data = export_analysis_to_json(assessment, ai_output, report)
        st.download_button(
            label="📄 Tải JSON Đầy Đủ",
            data=json_data,
            file_name=f"financial_analysis_{company_tag}_{fiscal_tag}.json",
            mime="application/json",
            use_container_width=True,
        )

    with c_btn2:
        csv_ratios = export_ratios_to_csv(assessment)
        st.download_button(
            label="📊 Tải 14 Tỷ Số (CSV)",
            data=csv_ratios.encode("utf-8-sig"),
            file_name=f"financial_ratios_{company_tag}_{fiscal_tag}.csv",
            mime="text/csv",
            use_container_width=True,
        )


CANONICAL_VIETNAMESE_NAMES: Dict[str, str] = {
    # Balance Sheet (B01-DN)
    "current_assets": "A. TÀI SẢN NGẮN HẠN",
    "cash_and_equivalents": "I. Tiền và các khoản tương đương tiền",
    "short_term_investments": "II. Đầu tư tài chính ngắn hạn",
    "short_term_receivables": "III. Các khoản phải thu ngắn hạn",
    "inventory": "IV. Hàng tồn kho",
    "other_current_assets": "V. Tài sản ngắn hạn khác",
    "non_current_assets": "B. TÀI SẢN DÀI HẠN",
    "fixed_assets": "II. Tài sản cố định",
    "total_assets": "TỔNG CỘNG TÀI SẢN",
    "liabilities": "C. NỢ PHẢI TRẢ",
    "current_liabilities": "I. Nợ ngắn hạn",
    "non_current_liabilities": "II. Nợ dài hạn",
    "equity": "D. VỐN CHỦ SỞ HỮU",
    "owner_capital": "1. Vốn góp của chủ sở hữu",
    "undistributed_earnings": "11. Lợi nhuận sau thuế chưa phân phối",
    "total_resources": "TỔNG CỘNG NGUỒN VỐN",
    # Income Statement (B02-DN)
    "gross_revenue": "1. Doanh thu bán hàng và CCDV",
    "revenue_deductions": "2. Các khoản giảm trừ doanh thu",
    "net_revenue": "3. Doanh thu thuần về bán hàng và CCDV",
    "cost_of_goods_sold": "4. Giá vốn hàng bán",
    "gross_profit": "5. Lợi nhuận gộp về bán hàng và CCDV",
    "financial_income": "6. Doanh thu hoạt động tài chính",
    "financial_expenses": "7. Chi phí tài chính",
    "interest_expenses": "Trong đó: Chi phí lãi vay",
    "selling_expenses": "8. Chi phí bán hàng",
    "administrative_expenses": "9. Chi phí quản lý doanh nghiệp",
    "operating_profit": "10. Lợi nhuận thuần từ HĐKD",
    "other_income": "11. Thu nhập khác",
    "other_expenses": "12. Chi phí khác",
    "net_other_profit": "13. Lợi nhuận khác",
    "net_profit_before_tax": "14. Tổng lợi nhuận kế toán trước thuế",
    "income_tax_expense": "15. Chi phí thuế TNDN",
    "net_profit_after_tax": "16. Lợi nhuận sau thuế TNDN",
}


def format_cell_number(val: Optional[Decimal]) -> str:
    """Format decimal amount into human-readable string with comma separators."""
    if val is None:
        return ""
    try:
        int_val = int(val)
        if int_val < 0:
            return f"({abs(int_val):,})"
        return f"{int_val:,}"
    except Exception:
        return str(val)


def parse_cell_to_decimal(val: Any) -> Optional[Decimal]:
    """Robustly parse an edited table cell (numeric, string with commas/dots, negative parentheses) to Decimal."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(int(val)))
    if isinstance(val, Decimal):
        return val
    raw = str(val).strip()
    if not raw:
        return None
    if raw in {"-", "—", "–", "−"}:
        return Decimal("0")

    is_neg = False
    if raw.startswith("(") and raw.endswith(")"):
        is_neg = True
        raw = raw[1:-1].strip()
    elif raw.startswith("-") or raw.startswith("−"):
        is_neg = True
        raw = raw[1:].strip()

    parsed = AccountingNumberNormalizer.parse(raw)
    if parsed.is_valid and parsed.value is not None:
        return -parsed.value if is_neg else parsed.value

    # Fallback digit cleaner
    digits = re.sub(r"[^\d]", "", raw)
    if digits:
        d = Decimal(digits)
        return -d if is_neg else d
    return None


def get_statement_column_names(report: Optional[FinancialReport]) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """Determine period column names for Balance Sheet and Income Statement based on fiscal date/year.
    
    Returns:
        ((bs_cur_col, bs_prev_col), (is_cur_col, is_prev_col))
    """
    if report and report.fiscal_year:
        year = report.fiscal_year
        bs_cur = f"31/12/{year}"
        bs_prev = f"01/01/{year}"
        is_cur = f"Năm {year}"
        is_prev = f"Năm {year - 1}"
    else:
        bs_cur = "Kỳ này (VND)"
        bs_prev = "Kỳ trước (VND)"
        is_cur = "Kỳ này (VND)"
        is_prev = "Kỳ trước (VND)"
    return (bs_cur, bs_prev), (is_cur, is_prev)


def _extract_row_period_values(row: pd.Series) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Extract current and previous period Decimals from DataFrame row supporting both dynamic date headers and static keys."""
    if "Kỳ này (VND)" in row and "Kỳ trước (VND)" in row:
        return parse_cell_to_decimal(row.get("Kỳ này (VND)")), parse_cell_to_decimal(row.get("Kỳ trước (VND)"))

    val_cols = [c for c in row.index if c not in ("canonical_key", "Mã số", "Chỉ tiêu BCTC")]
    if len(val_cols) >= 2:
        return parse_cell_to_decimal(row.get(val_cols[0])), parse_cell_to_decimal(row.get(val_cols[1]))
    elif len(val_cols) == 1:
        return parse_cell_to_decimal(row.get(val_cols[0])), None
    return None, None


def build_statement_dataframes(report: FinancialReport) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Convert recognized Balance Sheet and Income Statement line items into editable DataFrames with date headers."""
    (bs_cur_col, bs_prev_col), (is_cur_col, is_prev_col) = get_statement_column_names(report)

    bs_rows: List[Dict[str, Any]] = []
    if report.balance_sheet and report.balance_sheet.items:
        for c_key, item in report.balance_sheet.items.items():
            label = item.raw_label or CANONICAL_VIETNAMESE_NAMES.get(c_key, c_key)
            code = item.item_code or ""
            cur_val = format_cell_number(item.current_period_value)
            prev_val = format_cell_number(item.previous_period_value)
            bs_rows.append({
                "canonical_key": c_key,
                "Mã số": code,
                "Chỉ tiêu BCTC": label,
                bs_cur_col: cur_val,
                bs_prev_col: prev_val,
            })
    df_bs = pd.DataFrame(bs_rows)

    is_rows: List[Dict[str, Any]] = []
    if report.income_statement and report.income_statement.items:
        for c_key, item in report.income_statement.items.items():
            label = item.raw_label or CANONICAL_VIETNAMESE_NAMES.get(c_key, c_key)
            code = item.item_code or ""
            cur_val = format_cell_number(item.current_period_value)
            prev_val = format_cell_number(item.previous_period_value)
            is_rows.append({
                "canonical_key": c_key,
                "Mã số": code,
                "Chỉ tiêu BCTC": label,
                is_cur_col: cur_val,
                is_prev_col: prev_val,
            })
    df_is = pd.DataFrame(is_rows)

    return df_bs, df_is


def apply_edits_to_report(
    report: FinancialReport,
    edited_df_bs: Optional[pd.DataFrame],
    edited_df_is: Optional[pd.DataFrame],
) -> FinancialReport:
    """Apply manual edits from DataFrames back into the FinancialReport model and re-validate TT200."""
    if report.balance_sheet and edited_df_bs is not None and not edited_df_bs.empty:
        for _, row in edited_df_bs.iterrows():
            c_key = row.get("canonical_key")
            if c_key and c_key in report.balance_sheet.items:
                item = report.balance_sheet.items[c_key]
                new_code = str(row.get("Mã số", "")).strip()
                if new_code:
                    item.item_code = new_code
                new_label = str(row.get("Chỉ tiêu BCTC", "")).strip()
                if new_label:
                    item.raw_label = new_label
                    item.normalized_label = new_label
                cur_val, prev_val = _extract_row_period_values(row)
                item.current_period_value = cur_val
                item.previous_period_value = prev_val
                item.mapping_status = MappingStatus.MAPPED

    if report.income_statement and edited_df_is is not None and not edited_df_is.empty:
        for _, row in edited_df_is.iterrows():
            c_key = row.get("canonical_key")
            if c_key and c_key in report.income_statement.items:
                item = report.income_statement.items[c_key]
                new_code = str(row.get("Mã số", "")).strip()
                if new_code:
                    item.item_code = new_code
                new_label = str(row.get("Chỉ tiêu BCTC", "")).strip()
                if new_label:
                    item.raw_label = new_label
                    item.normalized_label = new_label
                cur_val, prev_val = _extract_row_period_values(row)
                item.current_period_value = cur_val
                item.previous_period_value = prev_val
                item.mapping_status = MappingStatus.MAPPED

    # Re-validate accounting equations with updated numbers
    validator = FinancialValidator()
    report.validation_results = validator.validate(report)
    return report



def _get_badge_text_color(bg: str) -> str:
    """Return matching high-contrast text color for badge background."""
    colors = {
        "#ecfdf5": "#065f46",
        "#fffbeb": "#92400e",
        "#fef2f2": "#991b1b",
        "#f1f5f9": "#475569",
    }
    return colors.get(bg, "#1e293b")


def _evaluate_kpi_visual(
    ratio_key: str, ratio_res: Optional[RatioResult]
) -> Tuple[str, str, str, str, str]:
    """Determine formatted value, value text color, badge label, badge background, and badge border.

    Returns:
        (val_str, text_color, badge_text, badge_bg, badge_border)
    """
    if (
        ratio_res is None
        or ratio_res.value is None
        or ratio_res.status in (RatioStatus.NOT_AVAILABLE, RatioStatus.NOT_APPLICABLE)
    ):
        return ("N/A", "#64748b", "THIẾU DỮ LIỆU", "#f1f5f9", "#cbd5e1")

    val = ratio_res.value

    if ratio_key == "current_ratio":
        if val >= Decimal("1.5"):
            return (f"{val:.2f} lần", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val >= Decimal("1.0"):
            return (f"{val:.2f} lần", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2f} lần", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    elif ratio_key == "debt_to_equity":
        if ratio_res.status == RatioStatus.UNDEFINED or val < Decimal("0"):
            return ("VCSH ÂM", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")
        if val <= Decimal("1.0"):
            return (f"{val:.2f} lần", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val <= Decimal("2.0"):
            return (f"{val:.2f} lần", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2f} lần", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    elif ratio_key == "roa":
        if val >= Decimal("0.05"):
            return (f"{val:.2%}", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val >= Decimal("0.0"):
            return (f"{val:.2%}", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2%}", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    elif ratio_key == "roe":
        if ratio_res.status == RatioStatus.UNDEFINED or val < Decimal("0"):
            if ratio_res.status == RatioStatus.UNDEFINED:
                return ("VCSH ÂM", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")
            return (f"{val:.2%}", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")
        if val >= Decimal("0.12"):
            return (f"{val:.2%}", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val >= Decimal("0.0"):
            return (f"{val:.2%}", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2%}", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    return (ratio_res.formatted_value, "#64748b", "THEO DÕI", "#f1f5f9", "#cbd5e1")


def render_core_4_kpi_cards(
    ratio_report: FinancialRatioReport,
    assessment: Optional[FinancialAssessment] = None,
) -> None:
    """Render 4 core KPI cards: Current Ratio, Debt/Equity, ROA, ROE.

    The cards have a clean white background (#ffffff), while the numerical values
    are highlighted in Green (#16a34a), Yellow/Amber (#d97706), or Red (#dc2626)
    corresponding to Safe / Warning / Danger levels.
    """
    col1, col2, col3, col4 = st.columns(4)

    configs = [
        (
            col1,
            "current_ratio",
            "Thanh toán hiện hành",
            "TSNH / Nợ ngắn hạn (Chuẩn an toàn: ≥ 1.5 lần)",
        ),
        (
            col2,
            "debt_to_equity",
            "Hệ số Nợ / Vốn CSH",
            "Nợ phải trả / Vốn CSH (Vùng an toàn: ≤ 1.0 lần)",
        ),
        (
            col3,
            "roa",
            "Sinh lời trên Tài sản (ROA)",
            "LNST / Tổng tài sản (Chuẩn an toàn: ≥ 5.0%)",
        ),
        (
            col4,
            "roe",
            "Sinh lời trên Vốn CSH (ROE)",
            "LNST / Vốn CSH (Chuẩn an toàn: ≥ 12.0%)",
        ),
    ]

    for col, key, title, subtext in configs:
        res = ratio_report.get_ratio(key)
        val_str, num_color, badge_text, badge_bg, badge_border = _evaluate_kpi_visual(key, res)
        badge_txt_col = _get_badge_text_color(badge_bg)

        with col:
            st.markdown(
                f"""
                <div class="kpi-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem 1.15rem; box-shadow: 0 2px 6px rgba(0,0,0,0.04); height: 100%;">
                    <div style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; font-weight: 700; margin-bottom: 0.4rem;">
                        {title}
                    </div>
                    <div style="font-size: 2.15rem; font-weight: 800; color: {num_color}; line-height: 1.15; margin-bottom: 0.45rem;">
                        {val_str}
                    </div>
                    <div style="margin-bottom: 0.5rem;">
                        <span style="display: inline-block; padding: 0.22rem 0.6rem; border-radius: 9999px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em; background-color: {badge_bg}; color: {badge_txt_col}; border: 1px solid {badge_border};">
                            {badge_text}
                        </span>
                    </div>
                    <div style="font-size: 0.78rem; color: #64748b; line-height: 1.35;">
                        {subtext}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )



def render_health_assessment(assessment: FinancialAssessment) -> None:
    """Render overall financial health synthesis and prioritized risk warnings."""
    # 1. Overall Status Hero Banner
    banner_html = get_overall_health_banner_html(assessment.overall_status.value)
    st.markdown(banner_html, unsafe_allow_html=True)

    # 2. Warning Summary Chips
    crit_count = sum(1 for w in assessment.warnings if w.severity == WarningSeverity.CRITICAL)
    high_count = sum(1 for w in assessment.warnings if w.severity == WarningSeverity.HIGH)
    med_count = sum(1 for w in assessment.warnings if w.severity == WarningSeverity.MEDIUM)
    low_count = sum(1 for w in assessment.warnings if w.severity == WarningSeverity.LOW)
    total_warnings = len(assessment.warnings)

    st.markdown(
        f"""
        <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem;">
            <span style="font-size: 0.9rem; font-weight: 600; color: #334155; align-self: center;">
                Tổng số cảnh báo phát hiện ({total_warnings}):
            </span>
            <span class="severity-badge" style="background-color: #7f1d1d; color: white;">
                Nghiêm trọng: {crit_count}
            </span>
            <span class="severity-badge" style="background-color: #dc2626; color: white;">
                Cao: {high_count}
            </span>
            <span class="severity-badge" style="background-color: #f59e0b; color: white;">
                Trung bình: {med_count}
            </span>
            <span class="severity-badge" style="background-color: #3b82f6; color: white;">
                Theo dõi / Thấp: {low_count}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Two-column layout: Category Overviews vs Key Findings
    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown(
            """
            <div class="fhs-card">
                <div class="fhs-card-header">📌 Nhận định theo 4 nhóm tài chính</div>
            """,
            unsafe_allow_html=True,
        )
        for cat_key, desc in assessment.category_overviews.items():
            cat_label = {
                "liquidity": "Thanh khoản",
                "leverage": "Cơ cấu vốn / Đòn bẩy",
                "efficiency": "Hiệu quả hoạt động",
                "profitability": "Khả năng sinh lời",
            }.get(cat_key, cat_key.capitalize())
            st.markdown(f"- **{cat_label}**: {desc}")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown(
            """
            <div class="fhs-card">
                <div class="fhs-card-header">🔍 Phát hiện trọng yếu (Key Findings)</div>
            """,
            unsafe_allow_html=True,
        )
        if assessment.key_findings:
            for finding in assessment.key_findings:
                st.markdown(f"- {finding}")
        else:
            st.info("Chưa có phát hiện trọng yếu nào được ghi nhận.")
        st.markdown("</div>", unsafe_allow_html=True)

    # 4. Prioritized Actionable Risk Warnings
    st.subheader("⚠️ Danh sách Cảnh báo Rủi ro có Căn cứ Số liệu")
    if not assessment.warnings:
        st.success("✅ Không phát hiện tín hiệu rủi ro vượt ngưỡng cảnh báo theo bộ quy tắc hiện tại.")
    else:
        for w in assessment.warnings:
            sev_class = w.severity.value.lower()
            badge_html = get_severity_badge_html(w.severity.value)
            st.markdown(
                f"""
                <div class="warning-item {sev_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                        <span class="warning-title">{w.title}</span>
                        {badge_html}
                    </div>
                    <div class="warning-evidence"><strong>Căn cứ số liệu:</strong> {w.evidence}</div>
                    <div style="font-size: 0.875rem; color: #1e293b; margin-bottom: 0.35rem;">{w.message}</div>
                    <div class="warning-rec">💡 <strong>Khuyến nghị:</strong> {w.recommendation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 5. Screening Thresholds & Limitations Notice
    st.markdown(
        """
        <div class="disclaimer-box">
            ℹ️ <strong>Lưu ý phương pháp luận:</strong> Các phân loại trạng thái (ADEQUATE, WATCH, ALERT)
            được xác định dựa trên bộ quy tắc và ngưỡng sàng lọc minh họa ban đầu (Rule-based).
            Đây không phải chuẩn mực kế toán pháp lý hay chuẩn ngành cố định cho mọi quy mô doanh nghiệp.
        </div>
        """,
        unsafe_allow_html=True,
    )


RATIO_BENCHMARKS = {
    "current_ratio": "≥ 1.5 lần (An toàn) | < 1.0 lần (Cảnh báo)",
    "quick_ratio": "≥ 1.0 lần (An toàn) | < 0.5 lần (Cảnh báo)",
    "cash_ratio": "≥ 0.2 lần (An toàn) | < 0.1 lần (Cảnh báo)",
    "debt_to_assets": "≤ 50.0% (An toàn) | > 70.0% (Cảnh báo)",
    "debt_to_equity": "≤ 1.0 lần (An toàn) | > 2.0 lần (Cảnh báo)",
    "equity_ratio": "≥ 50.0% (An toàn) | < 30.0% (Cảnh báo)",
    "total_asset_turnover": "Tùy đặc thù ngành",
    "inventory_turnover": "Tùy đặc thù ngành",
    "receivables_turnover": "Tùy đặc thù ngành",
    "days_sales_outstanding": "Tùy đặc thù ngành",
    "gross_profit_margin": "> 0.0% (Dương) | ≤ 0.0% (Cảnh báo)",
    "operating_profit_margin": "> 0.0% (Dương) | ≤ 0.0% (Cảnh báo)",
    "net_profit_margin": "> 0.0% (Dương) | ≤ 0.0% (Cảnh báo)",
    "roe": "> 0.0% (Dương) | ≤ 0.0% (Cảnh báo)",
}


def render_ratio_matrix(assessment: FinancialAssessment) -> None:
    """Render 14 financial ratios in a consolidated matrix table with quick status filtering."""
    st.markdown("### 📊 Ma Trận 14 Chỉ Số Tài Chính Cốt Lõi")

    # 1. Quick status filter
    filter_choice = st.radio(
        "Bộ lọc trạng thái chỉ số:",
        options=["Tất cả (14)", "🚨 Cảnh báo (Alert)", "⚠️ Cần theo dõi (Watch)", "✅ An toàn (Adequate)"],
        horizontal=True,
    )

    # Filter mapping
    status_filter_map = {
        "🚨 Cảnh báo (Alert)": [AssessmentStatus.ALERT],
        "⚠️ Cần theo dõi (Watch)": [AssessmentStatus.WATCH],
        "✅ An toàn (Adequate)": [AssessmentStatus.ADEQUATE],
    }
    allowed_statuses = status_filter_map.get(filter_choice)

    # 2. Build rows grouped by category
    category_order = [
        (RatioCategory.LIQUIDITY, "1. Khả năng thanh toán (Liquidity)"),
        (RatioCategory.LEVERAGE, "2. Cơ cấu vốn & Đòn bẩy (Leverage)"),
        (RatioCategory.EFFICIENCY, "3. Hiệu quả hoạt động (Efficiency)"),
        (RatioCategory.PROFITABILITY, "4. Khả năng sinh lời (Profitability)"),
    ]

    rows = []
    for cat_enum, cat_label in category_order:
        cat_ratios = [
            r for r in assessment.ratio_assessments.values()
            if (r.category == cat_enum or (hasattr(r.category, "value") and r.category.value == cat_enum.value))
        ]
        for r in cat_ratios:
            if allowed_statuses and r.status not in allowed_statuses:
                continue

            # Map status icon & text
            status_text = {
                AssessmentStatus.ADEQUATE: "✅ An toàn",
                AssessmentStatus.WATCH: "⚠️ Cần theo dõi",
                AssessmentStatus.CALCULATED_NO_BENCHMARK: "ℹ️ Cần benchmark",
                AssessmentStatus.NOT_AVAILABLE: "⚪ Thiếu số liệu",
                AssessmentStatus.NOT_APPLICABLE: "⚪ Không áp dụng",
                AssessmentStatus.UNDEFINED: "🟣 Bất thường",
            }.get(r.status, str(r.status.value if hasattr(r.status, "value") else r.status).upper())

            benchmark_guide = RATIO_BENCHMARKS.get(r.ratio_key, "Đối chiếu ngành")

            rows.append({
                "Nhóm": cat_label.split(". ")[1],
                "Chỉ số": r.label,
                "Giá trị": r.formatted_value,
                "Trạng thái": status_text,
                "Ngưỡng tham chiếu": benchmark_guide,
                "Ý nghĩa & Đánh giá": r.explanation,
            })

    if not rows:
        st.info(f"Không có chỉ số nào thuộc trạng thái: **{filter_choice}**")
    else:
        df_matrix = pd.DataFrame(rows)
        st.dataframe(
            df_matrix,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Nhóm": st.column_config.TextColumn("Nhóm chỉ số", width="medium"),
                "Chỉ số": st.column_config.TextColumn("Chỉ số", width="medium"),
                "Giá trị": st.column_config.TextColumn("Giá trị", width="small"),
                "Trạng thái": st.column_config.TextColumn("Trạng thái", width="small"),
                "Ngưỡng tham chiếu": st.column_config.TextColumn("Ngưỡng tham chiếu", width="medium"),
                "Ý nghĩa & Đánh giá": st.column_config.TextColumn("Ý nghĩa kinh tế", width="large"),
            },
        )


# Backward-compatibility alias
render_ratio_analysis = render_ratio_matrix


def render_financial_statements(report: FinancialReport) -> None:
    """Render extracted/normalized financial statement items and TT200 validation audit."""
    st.markdown("### 📑 Đối Soát Dữ Liệu Kế Toán & Kiểm Định TT200")

    stmt_choice = st.radio(
        "Chọn báo cáo đối soát:",
        options=[
            "📑 Bảng Cân đối kế toán (B01-DN)",
            "📊 Kết quả Hoạt động Kinh doanh (B02-DN)",
            "🛡️ Thẩm định Cân đối Kế toán (TT200)",
        ],
        horizontal=True,
    )

    # 1. Balance Sheet
    if stmt_choice == "📑 Bảng Cân đối kế toán (B01-DN)":
        if not report.balance_sheet or not report.balance_sheet.items:
            st.info("Chưa có dữ liệu Bảng Cân đối kế toán được trích xuất.")
        else:
            bs = report.balance_sheet
            (col_curr, col_prev), _ = get_statement_column_names(report)
            rows = []
            for key, item in bs.items.items():
                is_review = item.mapping_status == MappingStatus.NEEDS_REVIEW
                note_str = "⚠️ Cần rà soát" if is_review else "Chuẩn TT200"
                rows.append({
                    "Mã số": item.item_code or "",
                    "Chỉ tiêu chuẩn hóa": key,
                    "Tên gốc (OCR)": item.raw_label,
                    col_curr: format_currency(item.current_period_value, unit=""),
                    col_prev: format_currency(item.previous_period_value, unit=""),
                    "Ghi chú kiểm toán": note_str,
                })
            df_bs = pd.DataFrame(rows)
            st.dataframe(df_bs, use_container_width=True, hide_index=True)

            review_items = [item for item in bs.items.values() if item.mapping_status == MappingStatus.NEEDS_REVIEW]
            if review_items:
                st.warning(f"⚠️ Phát hiện {len(review_items)} chỉ tiêu Cần rà soát (NEEDS_REVIEW) trong Bảng CĐKT.")

    # 2. Income Statement
    elif stmt_choice == "📊 Kết quả Hoạt động Kinh doanh (B02-DN)":
        if not report.income_statement or not report.income_statement.items:
            st.info("Chưa có dữ liệu Báo cáo Kết quả Kinh doanh được trích xuất.")
        else:
            is_stmt = report.income_statement
            _, (col_curr, col_prev) = get_statement_column_names(report)
            rows = []
            for key, item in is_stmt.items.items():
                is_review = item.mapping_status == MappingStatus.NEEDS_REVIEW
                note_str = "⚠️ Cần rà soát" if is_review else "Chuẩn TT200"
                rows.append({
                    "Mã số": item.item_code or "",
                    "Chỉ tiêu chuẩn hóa": key,
                    "Tên gốc (OCR)": item.raw_label,
                    col_curr: format_currency(item.current_period_value, unit=""),
                    col_prev: format_currency(item.previous_period_value, unit=""),
                    "Ghi chú kiểm toán": note_str,
                })
            df_is = pd.DataFrame(rows)
            st.dataframe(df_is, use_container_width=True, hide_index=True)

    # 3. TT200 Validation
    else:
        if not report.validation_results:
            st.info("Chưa thực hiện kiểm tra tính cân đối kế toán TT200.")
        else:
            vr = report.validation_results
            if vr.is_valid:
                st.success(f"✅ Báo cáo tài chính đạt chuẩn cân đối kế toán TT200 ({vr.passed_checks}/{vr.total_checks} phép kiểm toán đạt chuẩn).")
            else:
                st.error(f"❌ Phát hiện {vr.failed_checks} lỗi mất cân đối trọng yếu cần kiểm tra lại.")

            val_rows = []
            for c in vr.checks:
                is_pass = c.status in (CheckStatus.PASSED, "passed", "PASS")
                status_icon = "✅ ĐẠT" if is_pass else "❌ LỆCH"
                val_rows.append({
                    "Phương trình kế toán TT200": c.name,
                    "Kết quả": status_icon,
                    "Độ lệch": format_difference(c.difference, c.tolerance),
                    "Chi tiết kiểm toán": c.message,
                })
            df_val = pd.DataFrame(val_rows)
            st.dataframe(df_val, use_container_width=True, hide_index=True)


def render_ai_interpretation(ai_output: Optional[AIInterpretationOutput]) -> None:
    """Render structured AI interpretation focusing strictly on the 4 core financial ratios."""
    if ai_output is None:
        st.info("💡 Chưa có nhận định AI. Vui lòng bật tùy chọn 'Nhận định chuyên sâu AI' để kích hoạt.")
        return

    # 1. Fallback Notice vs Model Provenance
    if ai_output.is_fallback:
        st.markdown(
            f"""
            <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 1.15rem 1.4rem; margin-bottom: 1.25rem;">
                <div style="font-weight: 700; color: #92400e; font-size: 0.95rem; margin-bottom: 0.35rem;">
                    ⚠️ Không thể kết nối mô hình AI để tạo nhận định tự động
                </div>
                <div style="color: #78350f; font-size: 0.88rem; line-height: 1.5; margin-bottom: 0.35rem;">
                    {ai_output.fallback_reason or "Chưa cấu hình OpenRouter API Key hoặc phản hồi API gián đoạn."}
                </div>
                <div style="color: #b45309; font-size: 0.8rem;">
                    💡 Vui lòng kiểm tra lại <code>OPENROUTER_API_KEY</code> trong file <code>.env</code>. Hệ thống không sử dụng nhận xét cấu hình sẵn.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    model_name = ai_output.model_used or "OpenRouter AI"
    st.markdown(
        f"""
        <div style="margin-bottom: 1.25rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <div>
                <span class="ai-badge" style="display: inline-block; padding: 0.35rem 0.85rem; border-radius: 9999px; font-size: 0.82rem; font-weight: 700; background-color: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;">
                    🤖 NHẬN ĐỊNH TÀI CHÍNH TỪ AI
                </span>
                <span style="font-size: 0.88rem; color: #065f46; margin-left: 0.6rem; font-weight: 600;">
                    Mô hình: <code>{model_name}</code> (Phân tích chuyên sâu 4 chỉ số tài chính cốt lõi)
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Executive Summary
    st.markdown(
        f"""
        <div class="fhs-card" style="border-left: 4px solid #006c49; margin-bottom: 1.25rem; background-color: #ffffff; border-radius: 12px; padding: 1.25rem 1.4rem; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
            <div class="fhs-card-header" style="font-size: 1.05rem; font-weight: 700; color: #006c49; margin-bottom: 0.6rem;">
                📋 Tóm tắt Điều hành (Executive Summary)
            </div>
            <div style="font-size: 0.95rem; line-height: 1.65; color: #1e293b;">
                {ai_output.executive_summary}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. 4 Core KPI Deep Dive by AI
    if ai_output.ratio_explanations:
        st.markdown(
            """
            <div style="margin: 1.25rem 0 0.75rem 0; font-size: 1.05rem; font-weight: 700; color: #0f172a;">
                🔍 Phân Tích Chuyên Sâu 4 Chỉ Số Cốt Lõi (AI Insights)
            </div>
            """,
            unsafe_allow_html=True,
        )

        kpi_deep_dive_configs = [
            (
                "current_ratio",
                "💧 Thanh toán hiện hành (Current Ratio)",
                "#0369a1",
                "#f0f9ff",
                "#bae6fd",
            ),
            (
                "debt_to_equity",
                "⚖️ Hệ số Nợ / Vốn CSH (Debt to Equity)",
                "#b45309",
                "#fffbeb",
                "#fde68a",
            ),
            (
                "roa",
                "📈 Hiệu quả Sinh lời trên Tài sản (ROA)",
                "#15803d",
                "#f0fdf4",
                "#bbf7d0",
            ),
            (
                "roe",
                "💎 Sinh lời trên Vốn Chủ sở hữu (ROE)",
                "#7c3aed",
                "#faf5ff",
                "#e9d5ff",
            ),
        ]

        c_kpi1, c_kpi2 = st.columns(2)
        half = len(kpi_deep_dive_configs) // 2

        with c_kpi1:
            for key, title, header_col, bg_col, border_col in kpi_deep_dive_configs[:half]:
                explanation = ai_output.ratio_explanations.get(key)
                if explanation:
                    st.markdown(
                        f"""
                        <div style="background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 10px; padding: 1rem 1.15rem; margin-bottom: 1rem;">
                            <div style="font-weight: 700; color: {header_col}; font-size: 0.92rem; margin-bottom: 0.35rem;">
                                {title}
                            </div>
                            <div style="font-size: 0.88rem; line-height: 1.55; color: #1e293b;">
                                {explanation}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with c_kpi2:
            for key, title, header_col, bg_col, border_col in kpi_deep_dive_configs[half:]:
                explanation = ai_output.ratio_explanations.get(key)
                if explanation:
                    st.markdown(
                        f"""
                        <div style="background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 10px; padding: 1rem 1.15rem; margin-bottom: 1rem;">
                            <div style="font-weight: 700; color: {header_col}; font-size: 0.92rem; margin-bottom: 0.35rem;">
                                {title}
                            </div>
                            <div style="font-size: 0.88rem; line-height: 1.55; color: #1e293b;">
                                {explanation}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # 4. Two columns: Strengths vs Risks
    col_str, col_risk = st.columns(2)

    with col_str:
        st.markdown(
            """
            <div class="fhs-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.15rem 1.25rem; margin-bottom: 1rem;">
                <div class="fhs-card-header" style="color: #065f46; font-weight: 700; font-size: 1rem; margin-bottom: 0.75rem;">
                    💪 Điểm Mạnh Tài Chính Nổi Bật
                </div>
            """,
            unsafe_allow_html=True,
        )
        if not ai_output.financial_strengths:
            st.write("Không ghi nhận điểm mạnh nổi bật theo dữ liệu hiện tại.")
        else:
            for s in ai_output.financial_strengths:
                if isinstance(s, AIStrengthItem):
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #065f46; font-size: 0.92rem;">{s.strength_title}</strong><br>
                            <span style="font-size: 0.85rem; color: #475569;"><strong>Căn cứ:</strong> {s.evidence}</span><br>
                            <span style="font-size: 0.85rem; color: #006c49;"><strong>Ý nghĩa:</strong> {s.significance}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif isinstance(s, str):
                    st.markdown(f"- **{s}**")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_risk:
        st.markdown(
            """
            <div class="fhs-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.15rem 1.25rem; margin-bottom: 1rem;">
                <div class="fhs-card-header" style="color: #991b1b; font-weight: 700; font-size: 1rem; margin-bottom: 0.75rem;">
                    ⚡ Rủi Ro Trọng Yếu Cần Lưu Ý
                </div>
            """,
            unsafe_allow_html=True,
        )
        if not ai_output.financial_risks:
            st.write("Không phát hiện rủi ro trọng yếu.")
        else:
            for r in ai_output.financial_risks:
                if isinstance(r, AIRiskItem):
                    sev_badge = get_severity_badge_html(r.severity)
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px dashed #e2e8f0;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                                <strong style="color: #991b1b; font-size: 0.92rem;">{r.risk_title}</strong>
                                {sev_badge}
                            </div>
                            <span style="font-size: 0.85rem; color: #475569;"><strong>Căn cứ:</strong> {r.evidence}</span><br>
                            <span style="font-size: 0.85rem; color: #64748b;"><strong>Tác động:</strong> {r.implication}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif isinstance(r, dict):
                    st.markdown(f"- **{r.get('risk_title', 'Rủi ro')}**: {r.get('evidence', '')}")
        st.markdown("</div>", unsafe_allow_html=True)

    # 5. Strategic Recommendations
    if ai_output.recommendations:
        st.markdown(
            """
            <div class="fhs-card" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.15rem 1.25rem; margin-bottom: 1rem;">
                <div class="fhs-card-header" style="color: #1e293b; font-weight: 700; font-size: 1rem; margin-bottom: 0.75rem;">
                    💡 Khuyến Nghị Hành Động Chiến Lược
                </div>
            """,
            unsafe_allow_html=True,
        )
        for rec in ai_output.recommendations:
            st.markdown(f"- {rec}")
        st.markdown("</div>", unsafe_allow_html=True)

    # 6. Limitations & Disclaimer
    if ai_output.data_limitations:
        with st.expander("🔍 Hạn chế của Dữ liệu & Lưu ý Thận trọng"):
            for lim in ai_output.data_limitations:
                st.write(f"- {lim}")

    st.markdown(
        f"""
        <div class="disclaimer-box" style="margin-top: 1rem;">
            🛡️ <strong>Tuyên bố miễn trừ trách nhiệm:</strong> {ai_output.disclaimer}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_export_section(
    assessment: FinancialAssessment,
    ai_output: Optional[AIInterpretationOutput] = None,
    report: Optional[FinancialReport] = None,
) -> None:
    """Render export download buttons for structured JSON and CSV datasets."""
    st.markdown("### 📥 Xuất Kết quả Phân tích")
    c1, c2, c3 = st.columns(3)

    # 1. JSON Export
    json_data = export_analysis_to_json(assessment, ai_output, report)
    company_tag = (assessment.company_name or "company").replace(" ", "_")
    fiscal_tag = assessment.fiscal_year or "period"
    json_filename = f"financial_analysis_{company_tag}_{fiscal_tag}.json"

    with c1:
        st.download_button(
            label="📄 Tải Báo cáo JSON Đầy đủ",
            data=json_data,
            file_name=json_filename,
            mime="application/json",
            use_container_width=True,
        )

    # 2. CSV Ratios
    csv_ratios = export_ratios_to_csv(assessment)
    csv_ratios_filename = f"financial_ratios_{company_tag}_{fiscal_tag}.csv"
    with c2:
        st.download_button(
            label="📊 Tải 14 Tỷ số (CSV)",
            data=csv_ratios.encode("utf-8-sig"),
            file_name=csv_ratios_filename,
            mime="text/csv",
            use_container_width=True,
        )

    # 3. CSV Warnings
    csv_warnings = export_warnings_to_csv(assessment)
    csv_warnings_filename = f"financial_warnings_{company_tag}_{fiscal_tag}.csv"
    with c3:
        st.download_button(
            label="⚠️ Tải Danh sách Cảnh báo (CSV)",
            data=csv_warnings.encode("utf-8-sig"),
            file_name=csv_warnings_filename,
            mime="text/csv",
            use_container_width=True,
        )
