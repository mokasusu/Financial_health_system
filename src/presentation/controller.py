"""Bộ điều khiển chính tầng trình diễn Streamlit (Presentation Controller).

Module này chịu trách nhiệm:
- Điều phối toàn bộ luồng tương tác của giao diện người dùng theo máy trạng thái 3 giai đoạn:
  + Giai đoạn 1 (idle): Chờ người dùng tải tệp BCTC (PDF vector, PDF scan hoặc tệp ảnh).
  + Giai đoạn 2 (extracted): Cho phép người dùng trực tiếp rà soát và hiệu chỉnh các chỉ tiêu BCTC trên bảng dữ liệu.
  + Giai đoạn 3 (calculated): Hiển thị bảng điều khiển phân tích tổng hợp (4 KPI cốt lõi, diễn giải AI, ma trận 14 chỉ số và xuất khẩu dữ liệu).
- Lưu trữ đệm đối tượng dịch vụ đường ống (AnalysisPipelineService) qua `st.cache_resource` để tối ưu hiệu năng.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import streamlit as st

from src.application.services.pipeline_service import AnalysisPipelineService
from src.domain.models.ai import AIInterpretationOutput
from src.domain.models.assessment import FinancialAssessment
from src.domain.models.bctc import FinancialReport
from src.domain.models.ratios import FinancialRatioReport
from src.infrastructure.factories import ServiceFactory
from src.presentation.components.ai_commentary import render_ai_interpretation
from src.presentation.components.kpi_cards import render_core_4_kpi_cards
from src.presentation.components.statement_tables import (
    apply_edits_to_report,
    build_statement_dataframes,
    get_statement_column_names,
)
from src.presentation.components.top_bar import render_header, render_top_action_bar
from src.presentation.state import initialize_session_state, reset_analysis
from src.presentation.styles import apply_custom_styles

logger = logging.getLogger(__name__)


def get_available_sample_options() -> Dict[str, Path]:
    """Hàm bổ trợ kiểm tra tính tương thích: trả về danh sách các tệp dữ liệu mẫu nếu có trên ổ đĩa.

    Returns:
        Dict[str, Path]: Ánh xạ tên nhãn mẫu -> Đường dẫn tệp Path.
    """
    candidates = [
        ("Mẫu 1", Path("data/samples/conghuy_A32_2020_sample.txt")),
        ("Mẫu 2", Path("data/samples/vduydong_A32_2017_sample.txt")),
    ]
    available: Dict[str, Path] = {}
    for label, path in candidates:
        if path.is_file():
            available[label] = path
    return available


@st.cache_resource
def get_pipeline_service() -> AnalysisPipelineService:
    """Khởi tạo và lưu trữ đệm phiên bản AnalysisPipelineService giữa các lần render lại của Streamlit.

    Returns:
        AnalysisPipelineService: Dịch vụ đường ống xử lý toàn trình.
    """
    return ServiceFactory.create_pipeline_service(extract_tables=False)


def run_app() -> None:
    """Thực thi ứng dụng bảng điều khiển phân tích sức khỏe tài chính Streamlit."""
    st.set_page_config(
        page_title="Financial Health System | Đánh giá Sức khỏe Tài chính",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_custom_styles()
    initialize_session_state()

    pipeline_service = get_pipeline_service()

    # Bảng điều khiển bên trái (Sidebar Controls)
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align: center; padding: 0.5rem 0 1.25rem 0;">
                <div style="font-size: 2.2rem; margin-bottom: 0.25rem;">🏛️</div>
                <h2 style="color: #006c49; margin: 0; font-size: 1.3rem; font-weight: 700;">Financial Health System</h2>
                <p style="color: #64748b; font-size: 0.8rem; margin: 0.25rem 0 0 0;">Chuẩn Thông tư 200/2014/TT-BTC</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Tải lên Báo cáo tài chính:",
            type=["pdf", "png", "jpg", "jpeg", "txt"],
            help="Hỗ trợ BCTC Hợp nhất hoặc BCTC Riêng theo Thông tư 200/VAS dạng PDF (vector/quét), ảnh chụp rõ nét hoặc text chuẩn hóa.",
        )

        enable_ai = st.toggle(
            "Nhận định chuyên sâu AI",
            value=True,
            help="Tự động phân tích điểm mạnh, rủi ro và khuyến nghị tài chính qua AI Gateway (Gemma / OpenRouter) hoặc Fallback xác định.",
        )

        st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            run_extract = st.button("🚀 Bóc Tách BCTC", type="primary", use_container_width=True)
        with col_btn2:
            if st.button("🔄 Đặt lại", use_container_width=True):
                reset_analysis()
                st.rerun()

    # Bước 1: Kích hoạt quy trình bóc tách tài liệu
    if run_extract:
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name

            with st.spinner("Đang bóc tách OCR và nhận diện cấu trúc BCTC theo TT200..."):
                report, method_or_err = pipeline_service.extract_financial_report(
                    file_bytes=file_bytes,
                    file_name=file_name,
                    period="current",
                )

                if report is None:
                    st.error(f"❌ Không thể bóc tách tài liệu: {method_or_err}")
                else:
                    df_bs, df_is = build_statement_dataframes(report)
                    st.session_state.report = report
                    st.session_state.df_bs = df_bs
                    st.session_state.df_is = df_is
                    st.session_state.source_name = file_name
                    st.session_state.extraction_method = method_or_err
                    st.session_state.stage = "extracted"
                    st.session_state.is_analyzed = False
                    st.success("✅ Bóc tách BCTC thành công! Vui lòng rà soát và chỉnh sửa số liệu trong bảng bên dưới.")
        else:
            st.warning("⚠️ Vui lòng tải lên tệp Báo cáo tài chính (PDF hoặc ảnh) ở thanh điều khiển bên trái để bắt đầu phân tích.")

    # Bước 2: Hiển thị nội dung chính theo trạng thái phiên làm việc (Stage)
    if st.session_state.stage == "idle":
        st.markdown(
            """
            <div style="background-color: #ffffff; border: 1.5px dashed #cbd5e1; border-radius: 14px; padding: 3.5rem 2rem; text-align: center; margin-top: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.02);">
                <div style="font-size: 3.2rem; margin-bottom: 0.75rem;">📊</div>
                <h3 style="color: #006c49; margin-bottom: 0.5rem; font-size: 1.45rem; font-weight: 700;">Hệ Thống Đánh Giá Sức Khỏe Tài Chính Doanh Nghiệp</h3>
                <p style="color: #64748b; max-width: 620px; margin: 0 auto 1.75rem auto; font-size: 0.95rem; line-height: 1.6;">
                    Tự động hóa bóc tách Báo cáo tài chính theo Thông tư 200/2014/TT-BTC, đối soát kiểm định cân đối kế toán và tính toán các chỉ số tài chính trọng yếu kèm nhận định AI.
                </p>
                <div style="font-size: 0.9rem; color: #006c49; background: #e6f4ef; display: inline-block; padding: 0.6rem 1.4rem; border-radius: 9999px; font-weight: 600; border: 1px solid #a7f3d0;">
                    👈 Tải tệp BCTC (PDF hoặc ảnh) ở thanh bên trái và nhấn <strong>🚀 Bóc Tách BCTC</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif st.session_state.stage == "extracted":
        report: FinancialReport = st.session_state.report
        company_name = report.company_name or "Doanh nghiệp"
        as_of = getattr(report, "as_of_date", None) or (report.balance_sheet.as_of_date if report.balance_sheet else None)
        if as_of:
            date_badge = f"Tại ngày: {as_of}"
            if report.fiscal_year and str(report.fiscal_year) not in as_of:
                date_badge += f" (Năm {report.fiscal_year})"
        elif report.fiscal_year:
            date_badge = f"Năm tài chính: {report.fiscal_year}"
        elif getattr(report, "period", None):
            date_badge = f"Kỳ báo cáo: {report.period}"
        else:
            date_badge = "Kỳ báo cáo: Chưa xác định"

        st.markdown(
            f"""
            <div class="dashboard-header" style="padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;">
                <h2 style="color: white; margin: 0 0 0.35rem 0; font-size: 1.4rem;">📝 RÀ SOÁT & HIỆU CHỈNH SỐ LIỆU BCTC ĐÃ NHẬN DIỆN</h2>
                <div style="color: #e6f4ef; font-size: 0.9rem;">
                    🏢 <strong>{company_name}</strong> | 📅 <strong>{date_badge}</strong> | 📄 Nguồn: <strong>{st.session_state.source_name}</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.info(
            "💡 **Hướng dẫn:** Hệ thống đã tự động bóc tách các chỉ tiêu kế toán theo ngày tháng tương ứng. "
            "Bạn có thể nhấn trực tiếp vào từng ô để chỉnh sửa số liệu nếu cần trước khi tính toán."
        )

        tab_bs, tab_is = st.tabs([
            "📑 1. Bảng Cân đối Kế toán (B01-DN)",
            "📊 2. Báo cáo Kết quả Kinh doanh (B02-DN)",
        ])

        (bs_cur_col, bs_prev_col), (is_cur_col, is_prev_col) = get_statement_column_names(report)

        with tab_bs:
            edited_df_bs = st.data_editor(
                st.session_state.df_bs,
                key="editor_bs",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "canonical_key": None,
                    "Mã số": st.column_config.TextColumn("Mã số TT200", width="small"),
                    "Chỉ tiêu BCTC": st.column_config.TextColumn("Chỉ tiêu kế toán", width="large", disabled=False),
                    bs_cur_col: st.column_config.TextColumn(bs_cur_col, width="medium"),
                    bs_prev_col: st.column_config.TextColumn(bs_prev_col, width="medium"),
                },
            )

        with tab_is:
            edited_df_is = st.data_editor(
                st.session_state.df_is,
                key="editor_is",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "canonical_key": None,
                    "Mã số": st.column_config.TextColumn("Mã số TT200", width="small"),
                    "Chỉ tiêu BCTC": st.column_config.TextColumn("Chỉ tiêu kế toán", width="large", disabled=False),
                    is_cur_col: st.column_config.TextColumn(is_cur_col, width="medium"),
                    is_prev_col: st.column_config.TextColumn(is_prev_col, width="medium"),
                },
            )

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        c_btn_calc, _ = st.columns([2, 2])
        with c_btn_calc:
            if st.button("⚡ Tính Toán & Đánh Giá AI", type="primary", use_container_width=True):
                with st.spinner("Đang cập nhật số liệu, tính toán 4 chỉ số tài chính và gọi AI nhận xét..."):
                    updated_report = apply_edits_to_report(report, edited_df_bs, edited_df_is)
                    ratio_report, assessment, ai_output = pipeline_service.calculate_assessment_and_ai(
                        updated_report,
                        period="current",
                        enable_ai=enable_ai,
                    )
                    st.session_state.report = updated_report
                    st.session_state.df_bs = edited_df_bs
                    st.session_state.df_is = edited_df_is
                    st.session_state.ratio_report = ratio_report
                    st.session_state.assessment = assessment
                    st.session_state.ai_output = ai_output
                    st.session_state.is_analyzed = True
                    st.session_state.stage = "calculated"
                    st.rerun()

    elif st.session_state.stage == "calculated":
        assessment: FinancialAssessment = st.session_state.assessment
        ratio_report: FinancialRatioReport = st.session_state.ratio_report
        report: FinancialReport = st.session_state.report
        ai_output: Optional[AIInterpretationOutput] = st.session_state.ai_output

        render_header(
            company_name=assessment.company_name,
            fiscal_year=assessment.fiscal_year,
            currency=assessment.currency,
            source_name=st.session_state.source_name,
            extraction_method=st.session_state.extraction_method,
            as_of_date=getattr(assessment, "as_of_date", None) or getattr(report, "as_of_date", None),
            period=getattr(assessment, "period", None) or getattr(report, "period", None),
        )

        render_top_action_bar(assessment, ai_output, report)

        with st.expander("📝 Xem lại & Chỉnh sửa số liệu BCTC đã nhận diện (Nhấn để mở rộng)", expanded=False):
            st.caption("Bạn có thể điều chỉnh lại bất kỳ số liệu nào bên dưới và nhấn nút 'Cập nhật số liệu & Tính lại'.")
            tab_exp_bs, tab_exp_is = st.tabs([
                "📑 Bảng Cân đối Kế toán (B01-DN)",
                "📊 Báo cáo Kết quả Kinh doanh (B02-DN)",
            ])
            (bs_cur_col, bs_prev_col), (is_cur_col, is_prev_col) = get_statement_column_names(report)
            with tab_exp_bs:
                re_edited_df_bs = st.data_editor(
                    st.session_state.df_bs,
                    key="re_editor_bs",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "canonical_key": None,
                        "Mã số": st.column_config.TextColumn("Mã số TT200", width="small"),
                        "Chỉ tiêu BCTC": st.column_config.TextColumn("Chỉ tiêu kế toán", width="large", disabled=False),
                        bs_cur_col: st.column_config.TextColumn(bs_cur_col, width="medium"),
                        bs_prev_col: st.column_config.TextColumn(bs_prev_col, width="medium"),
                    },
                )
            with tab_exp_is:
                re_edited_df_is = st.data_editor(
                    st.session_state.df_is,
                    key="re_editor_is",
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "canonical_key": None,
                        "Mã số": st.column_config.TextColumn("Mã số TT200", width="small"),
                        "Chỉ tiêu BCTC": st.column_config.TextColumn("Chỉ tiêu kế toán", width="large", disabled=False),
                        is_cur_col: st.column_config.TextColumn(is_cur_col, width="medium"),
                        is_prev_col: st.column_config.TextColumn(is_prev_col, width="medium"),
                    },
                )
            if st.button("🔄 Cập nhật số liệu & Tính lại", use_container_width=True):
                with st.spinner("Đang cập nhật số liệu và tính lại..."):
                    updated_report = apply_edits_to_report(report, re_edited_df_bs, re_edited_df_is)
                    ratio_report, assessment, ai_output = pipeline_service.calculate_assessment_and_ai(
                        updated_report,
                        period="current",
                        enable_ai=enable_ai,
                    )
                    st.session_state.report = updated_report
                    st.session_state.df_bs = re_edited_df_bs
                    st.session_state.df_is = re_edited_df_is
                    st.session_state.ratio_report = ratio_report
                    st.session_state.assessment = assessment
                    st.session_state.ai_output = ai_output
                    st.rerun()

        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

        render_core_4_kpi_cards(ratio_report, assessment)

        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

        if ai_output:
            render_ai_interpretation(ai_output)
        elif st.session_state.get("ai_error"):
            st.markdown(
                f"""
                <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 1.25rem 1.4rem; margin-top: 1rem;">
                    <div style="font-weight: 700; color: #991b1b; font-size: 1rem; margin-bottom: 0.35rem;">
                        ⚠️ Không thể khởi tạo nhận định từ mô hình AI
                    </div>
                    <div style="color: #7f1d1d; font-size: 0.88rem; line-height: 1.5; margin-bottom: 0.4rem;">
                        {st.session_state.ai_error}
                    </div>
                    <div style="color: #64748b; font-size: 0.8rem;">
                        💡 Vui lòng kiểm tra lại <code>OPENROUTER_API_KEY</code>, <code>OPENROUTER_MODEL</code> và kết nối mạng trong file <code>.env</code>. Hệ thống không sử dụng các nhận xét cấu hình sẵn.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Chưa có nhận định AI. Bạn có thể bật tùy chọn 'Nhận định chuyên sâu AI' ở thanh bên trái.")
