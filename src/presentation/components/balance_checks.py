"""Thành phần giao diện đánh giá sức khỏe tài chính và ma trận 14 tỷ số (Health Assessment & Ratio Matrix).

Module này cung cấp:
- render_health_assessment: Kết xuất biểu ngữ sức khỏe tài chính tổng hợp, thống kê mức độ cảnh báo,
  nhận định theo 4 nhóm tài chính, phát hiện trọng yếu (Key Findings), và danh sách cảnh báo có căn cứ số liệu.
- render_ratio_matrix: Kết xuất bảng ma trận tổng hợp 14 chỉ số tài chính chuẩn mực kèm bộ lọc trạng thái nhanh.
"""
import pandas as pd
import streamlit as st

from src.domain.models.assessment import (
    AssessmentStatus,
    FinancialAssessment,
    WarningSeverity,
)
from src.domain.models.ratios import RatioCategory
from src.presentation.styles import (
    get_overall_health_banner_html,
    get_severity_badge_html,
)

# Hướng dẫn ngưỡng tham chiếu kinh nghiệm cho 14 chỉ số tài chính
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


def render_health_assessment(assessment: FinancialAssessment) -> None:
    """Kết xuất tổng quan sức khỏe tài chính, phân loại theo 4 nhóm và danh sách cảnh báo rủi ro.

    Args:
        assessment (FinancialAssessment): Kết quả đánh giá sức khỏe tài chính tổng thể.
    """
    # 1. Biểu ngữ tổng thể sức khỏe tài chính (Overall Status Hero Banner)
    banner_html = get_overall_health_banner_html(assessment.overall_status.value)
    st.markdown(banner_html, unsafe_allow_html=True)

    # 2. Thống kê số lượng cảnh báo theo mức độ nghiêm trọng
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

    # 3. Bố cục 2 cột: Nhận định 4 nhóm tài chính vs Phát hiện trọng yếu
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

    # 4. Danh sách cảnh báo rủi ro được ưu tiên kèm bằng chứng số liệu
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

    # 5. Hộp lưu ý phương pháp luận và giới hạn dữ liệu
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


def render_ratio_matrix(assessment: FinancialAssessment) -> None:
    """Kết xuất ma trận 14 chỉ số tài chính trong bảng dữ liệu tương tác kèm bộ lọc trạng thái.

    Args:
        assessment (FinancialAssessment): Kết quả đánh giá 14 tỷ số.
    """
    st.markdown("### 📊 Ma Trận 14 Chỉ Số Tài Chính Cốt Lõi")

    filter_choice = st.radio(
        "Bộ lọc trạng thái chỉ số:",
        options=["Tất cả (14)", "🚨 Cảnh báo (Alert)", "⚠️ Cần theo dõi (Watch)", "✅ An toàn (Adequate)"],
        horizontal=True,
    )

    status_filter_map = {
        "🚨 Cảnh báo (Alert)": [AssessmentStatus.ALERT],
        "⚠️ Cần theo dõi (Watch)": [AssessmentStatus.WATCH],
        "✅ An toàn (Adequate)": [AssessmentStatus.ADEQUATE],
    }
    allowed_statuses = status_filter_map.get(filter_choice)

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


# Bí danh tương thích ngược
render_ratio_analysis = render_ratio_matrix
