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
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
import streamlit as st

from src.data.schema import CheckStatus, FinancialReport, MappingStatus
from src.financial.ai_models import AIInterpretationOutput, AIRiskItem, AIStrengthItem
from src.financial.assessment_models import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    OverallHealthStatus,
    RatioAssessment,
    WarningSeverity,
)
from src.financial.ratios import RatioCategory
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


def render_kpi_cards(assessment: FinancialAssessment) -> None:
    """Render executive KPI cards for core ratios (Current Ratio, Debt/Assets, NPM, ROE)."""
    col1, col2, col3, col4 = st.columns(4)

    # 1. Current Ratio
    cr_eval = assessment.get_assessment("current_ratio")
    with col1:
        cr_val = cr_eval.formatted_value if cr_eval else "N/A"
        cr_badge = get_status_badge_html(cr_eval.status.value) if cr_eval else ""
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Thanh toán hiện hành</div>
                <div class="kpi-value">{cr_val}</div>
                <div style="margin-top: 0.35rem; margin-bottom: 0.35rem;">{cr_badge}</div>
                <div class="kpi-subtext">TSNH / Nợ ngắn hạn (Ngưỡng an toàn ≥ 1.5 lần)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Debt to Assets
    dta_eval = assessment.get_assessment("debt_to_assets")
    with col2:
        dta_val = dta_eval.formatted_value if dta_eval else "N/A"
        dta_badge = get_status_badge_html(dta_eval.status.value) if dta_eval else ""
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Hệ số nợ / Tài sản</div>
                <div class="kpi-value">{dta_val}</div>
                <div style="margin-top: 0.35rem; margin-bottom: 0.35rem;">{dta_badge}</div>
                <div class="kpi-subtext">Nợ phải trả / Tổng tài sản (Vùng an toàn ≤ 50%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 3. Net Profit Margin
    npm_eval = assessment.get_assessment("net_profit_margin")
    with col3:
        npm_val = npm_eval.formatted_value if npm_eval else "N/A"
        npm_badge = get_status_badge_html(npm_eval.status.value) if npm_eval else ""
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Biên lợi nhuận ròng</div>
                <div class="kpi-value">{npm_val}</div>
                <div style="margin-top: 0.35rem; margin-bottom: 0.35rem;">{npm_badge}</div>
                <div class="kpi-subtext">LNST / Doanh thu thuần (Sinh lời ròng)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. ROE
    roe_eval = assessment.get_assessment("roe")
    with col4:
        roe_val = roe_eval.formatted_value if roe_eval else "N/A"
        roe_badge = get_status_badge_html(roe_eval.status.value) if roe_eval else ""
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Sinh lời trên VCSH (ROE)</div>
                <div class="kpi-value">{roe_val}</div>
                <div style="margin-top: 0.35rem; margin-bottom: 0.35rem;">{roe_badge}</div>
                <div class="kpi-subtext">LNST / Vốn chủ sở hữu bình quân</div>
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
                    <div class="warning-evidence"><strong>Căn cứ số liệu:</strong> {w.evidence} (Mã: <code>{w.code}</code>)</div>
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


def render_ratio_analysis(assessment: FinancialAssessment) -> None:
    """Render 14 financial ratios grouped into 4 standard categories."""
    tabs = st.tabs([
        "💧 Thanh khoản (3)",
        "⚖️ Cơ cấu nợ / Đòn bẩy (3)",
        "⚙️ Hiệu quả hoạt động (4)",
        "📈 Khả năng sinh lời (4)",
    ])

    groups = [
        (tabs[0], RatioCategory.LIQUIDITY, "Nhóm Tỷ số Khả năng Thanh toán"),
        (tabs[1], RatioCategory.LEVERAGE, "Nhóm Tỷ số Cơ cấu vốn và Đòn bẩy"),
        (tabs[2], RatioCategory.EFFICIENCY, "Nhóm Tỷ số Hiệu quả Hoạt động"),
        (tabs[3], RatioCategory.PROFITABILITY, "Nhóm Tỷ số Khả năng Sinh lời"),
    ]

    for tab, cat_enum, cat_title in groups:
        with tab:
            st.markdown(f"#### {cat_title}")
            # Collect ratios in this category
            cat_ratios: List[RatioAssessment] = [
                r for r in assessment.ratio_assessments.values()
                if (r.category == cat_enum or (hasattr(r.category, "value") and r.category.value == cat_enum.value))
            ]

            if not cat_ratios:
                st.info("Không có chỉ số nào trong nhóm này.")
                continue

            for r in cat_ratios:
                with st.expander(f"**{r.label}**: {r.formatted_value}", expanded=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.markdown(f"**Giá trị:** `{r.formatted_value}`")
                        st.markdown(f"**Trạng thái:** {get_status_badge_html(r.status.value)}", unsafe_allow_html=True)
                        if r.rule_id:
                            st.caption(f"Quy tắc: `{r.rule_id}`")
                    with c2:
                        st.markdown(f"**Ý nghĩa & Giải thích:** {r.explanation}")
                        if r.warnings:
                            st.warning(" | ".join(r.warnings))
                        if r.limitations:
                            with st.popover("Lưu ý & Hạn chế chỉ số"):
                                for lim in r.limitations:
                                    st.write(f"- {lim}")


def render_financial_statements(report: FinancialReport) -> None:
    """Render extracted/normalized financial statement items and TT200 validation audit."""
    tab_bs, tab_is, tab_val = st.tabs([
        "📑 Bảng Cân đối kế toán",
        "📊 Kết quả Hoạt động Kinh doanh",
        "🛡️ Kiểm tra Cân đối TT200",
    ])

    # Tab 1: Balance Sheet
    with tab_bs:
        if not report.balance_sheet or not report.balance_sheet.items:
            st.info("Chưa có dữ liệu Bảng Cân đối kế toán được trích xuất.")
        else:
            bs = report.balance_sheet
            rows = []
            for key, item in bs.items.items():
                rows.append({
                    "Chỉ tiêu chuẩn hóa": key,
                    "Tên gốc (OCR)": item.raw_label,
                    "Mã số": item.item_code or "",
                    "Kỳ này": format_currency(item.current_period_value, unit=""),
                    "Kỳ trước": format_currency(item.previous_period_value, unit=""),
                    "Trạng thái": item.mapping_status.value if hasattr(item.mapping_status, "value") else str(item.mapping_status),
                    "Độ tin cậy": f"{item.confidence_score:.2f}",
                })
            df_bs = pd.DataFrame(rows)
            st.dataframe(df_bs, use_container_width=True, hide_index=True)

            # Review flags callout if items marked NEEDS_REVIEW
            review_items = [item for item in bs.items.values() if item.mapping_status == MappingStatus.NEEDS_REVIEW]
            if review_items:
                st.warning(f"⚠️ Phát hiện {len(review_items)} chỉ tiêu Cần rà soát (NEEDS_REVIEW) trong Bảng CĐKT.")

    # Tab 2: Income Statement
    with tab_is:
        if not report.income_statement or not report.income_statement.items:
            st.info("Chưa có dữ liệu Báo cáo Kết quả Kinh doanh được trích xuất.")
        else:
            is_stmt = report.income_statement
            rows = []
            for key, item in is_stmt.items.items():
                rows.append({
                    "Chỉ tiêu chuẩn hóa": key,
                    "Tên gốc (OCR)": item.raw_label,
                    "Mã số": item.item_code or "",
                    "Kỳ này": format_currency(item.current_period_value, unit=""),
                    "Kỳ trước": format_currency(item.previous_period_value, unit=""),
                    "Trạng thái": item.mapping_status.value if hasattr(item.mapping_status, "value") else str(item.mapping_status),
                    "Độ tin cậy": f"{item.confidence_score:.2f}",
                })
            df_is = pd.DataFrame(rows)
            st.dataframe(df_is, use_container_width=True, hide_index=True)

    # Tab 3: TT200 Accounting Validation Checks
    with tab_val:
        if not report.validation_results:
            st.info("Chưa thực hiện kiểm tra tính cân đối kế toán TT200.")
        else:
            vr = report.validation_results
            if vr.is_valid:
                st.success(f"✅ Báo cáo tài chính đạt chuẩn cân đối kế toán TT200 ({vr.passed_checks}/{vr.total_checks} kiểm tra đạt).")
            else:
                st.error(f"❌ Phát hiện {vr.failed_checks} lỗi mất cân đối trọng yếu cần kiểm tra lại.")

            val_rows = []
            for c in vr.checks:
                status_str = c.status.value.upper() if hasattr(c.status, "value") else str(c.status).upper()
                val_rows.append({
                    "Mã kiểm tra": c.check_id,
                    "Phương trình kế toán": c.name,
                    "Kết quả": status_str,
                    "Chênh lệch": format_difference(c.difference, c.tolerance),
                    "Ghi chú": c.message,
                })
            df_val = pd.DataFrame(val_rows)
            st.dataframe(df_val, use_container_width=True, hide_index=True)


def render_ai_interpretation(ai_output: Optional[AIInterpretationOutput]) -> None:
    """Render structured AI interpretation distinguishing AI model from deterministic fallback."""
    if ai_output is None:
        st.info("💡 Chưa chạy phân tích AI. Nhấn nút 'Chạy Phân Tích với AI' tại thanh điều khiển bên trái để kích hoạt.")
        return

    # 1. Badge & Model Provenance
    if ai_output.is_fallback:
        st.markdown(
            f"""
            <div style="margin-bottom: 1rem;">
                <span class="ai-fallback-badge">⚙️ DETERMINISTIC FALLBACK (RULE ENGINE)</span>
                <span style="font-size: 0.85rem; color: #64748b; margin-left: 0.5rem;">
                    Lý do: {ai_output.fallback_reason or "Chưa cấu hình OpenRouter API Key hoặc phản hồi API gián đoạn"}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        model_name = ai_output.model_used or "OpenRouter AI"
        st.markdown(
            f"""
            <div style="margin-bottom: 1rem;">
                <span class="ai-badge">🤖 AI INTERPRETATION</span>
                <span style="font-size: 0.85rem; color: #065f46; margin-left: 0.5rem; font-weight: 500;">
                    Mô hình: <code>{model_name}</code> (Grounding kiểm chứng 100% số liệu Python)
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Executive Summary
    st.markdown(
        f"""
        <div class="fhs-card" style="border-left: 4px solid #006c49;">
            <div class="fhs-card-header">📋 Tóm tắt Điều hành (Executive Summary)</div>
            <div style="font-size: 0.95rem; line-height: 1.6; color: #1e293b;">
                {ai_output.executive_summary}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Two columns: Strengths vs Risks
    col_str, col_risk = st.columns(2)

    with col_str:
        st.markdown(
            """
            <div class="fhs-card">
                <div class="fhs-card-header" style="color: #065f46;">💪 Điểm mạnh Tài chính Nổi bật</div>
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
                            <strong style="color: #065f46;">{s.strength_title}</strong><br>
                            <span style="font-size: 0.85rem; color: #475569;">Căn cứ: {s.evidence}</span><br>
                            <span style="font-size: 0.85rem; color: #006c49;">Ý nghĩa: {s.significance}</span>
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
            <div class="fhs-card">
                <div class="fhs-card-header" style="color: #991b1b;">⚡ Rủi ro Trọng yếu Cần Lưu ý</div>
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
                            <div style="display: flex; justify-content: space-between;">
                                <strong style="color: #991b1b;">{r.risk_title}</strong>
                                {sev_badge}
                            </div>
                            <span style="font-size: 0.85rem; color: #475569;">Căn cứ: {r.evidence}</span><br>
                            <span style="font-size: 0.85rem; color: #64748b;">Tác động: {r.implication}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif isinstance(r, dict):
                    st.markdown(f"- **{r.get('risk_title', 'Rủi ro')}**: {r.get('evidence', '')}")
        st.markdown("</div>", unsafe_allow_html=True)

    # 4. Strategic Recommendations
    if ai_output.recommendations:
        st.markdown(
            """
            <div class="fhs-card">
                <div class="fhs-card-header">💡 Khuyến nghị Hành động Thiết thực</div>
            """,
            unsafe_allow_html=True,
        )
        for rec in ai_output.recommendations:
            st.markdown(f"- {rec}")
        st.markdown("</div>", unsafe_allow_html=True)

    # 5. Limitations & Legal Disclaimer
    if ai_output.data_limitations:
        with st.expander("🔍 Hạn chế của Dữ liệu & Lưu ý Thận trọng"):
            for lim in ai_output.data_limitations:
                st.write(f"- {lim}")

    st.markdown(
        f"""
        <div class="disclaimer-box">
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
