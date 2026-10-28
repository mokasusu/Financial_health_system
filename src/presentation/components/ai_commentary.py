"""Thành phần giao diện nhận định và diễn giải tài chính từ AI (AI Commentary Component).

Module này kết xuất các phân tích chuyên sâu của AI:
1. Thông báo cơ chế dự phòng (Fallback Notice) hoặc phiên bản mô hình ngôn ngữ thực thi.
2. Tóm tắt điều hành (Executive Summary) đánh giá khái quát tình hình tài chính.
3. Phân tích chuyên sâu 4 chỉ số tài chính cốt lõi (Current Ratio, D/E, ROA, ROE).
4. Điểm mạnh tài chính (Strengths) và Rủi ro trọng yếu (Risks) kèm bằng chứng số liệu và tác động.
5. Khuyến nghị hành động chiến lược (Strategic Recommendations).
6. Hạn chế dữ liệu và Tuyên bố miễn trừ trách nhiệm (Disclaimer).
"""
from typing import Optional
import streamlit as st

from src.domain.models.ai import AIInterpretationOutput, AIRiskItem, AIStrengthItem
from src.presentation.styles import get_severity_badge_html


def render_ai_interpretation(ai_output: Optional[AIInterpretationOutput]) -> None:
    """Kết xuất cấu trúc nhận định tài chính chuyên sâu từ AI neo theo 4 chỉ số cốt lõi.

    Args:
        ai_output (Optional[AIInterpretationOutput]): Dữ liệu đầu ra diễn giải từ AI hoặc None.
    """
    if ai_output is None:
        st.info("💡 Chưa có nhận định AI. Vui lòng bật tùy chọn 'Nhận định chuyên sâu AI' để kích hoạt.")
        return

    # 1. Thông báo chuyển sang Fallback hoặc Hiển thị tên Model AI
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

    # 2. Tóm tắt Điều hành (Executive Summary)
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

    # 3. Phân tích chi tiết 4 chỉ số cốt lõi từ AI
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

    # 4. Hai cột đối chiếu: Điểm mạnh tài chính vs Rủi ro trọng yếu
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

    # 5. Khuyến nghị hành động chiến lược
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

    # 6. Hạn chế của dữ liệu & Tuyên bố miễn trừ trách nhiệm
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
