"""Interactive Financial Health Dashboard Application (Sprint 6).

Streamlit entry point integrating:
- PDF / Image OCR extraction (Sprint 2)
- Statement semantic parsing, normalization & TT200 validation (Sprint 3)
- 14 Financial ratio engine (Sprint 4A)
- Financial assessment & prioritized warning engine (Sprint 4B)
- AI interpretation with deterministic fallback (Sprint 5)
- Structured JSON and CSV export (Sprint 6)
"""
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
import logging
import streamlit as st

logger = logging.getLogger(__name__)

# Load environment configuration safely
load_dotenv()

from src.data.parser import FinancialStatementParser
from src.data.schema import FinancialReport
from src.data.validator import FinancialValidator
from src.financial.ai_interpreter import AIFinancialInterpreter
from src.financial.ai_models import AIInterpretationOutput
from src.financial.assessment import FinancialHealthAssessor
from src.financial.assessment_models import FinancialAssessment
from src.financial.ratios import FinancialRatioCalculator, FinancialRatioReport
from src.ocr.models import DocumentExtractionResult
from src.ocr.pdf_extractor import PDFExtractor
import importlib
import src.ui.components
importlib.reload(src.ui.components)
from src.ui.components import (
    apply_edits_to_report,
    build_statement_dataframes,
    get_statement_column_names,
    render_ai_interpretation,
    render_core_4_kpi_cards,
    render_header,
    render_top_action_bar,
)
from src.ui.styles import apply_custom_styles


# Page Configuration
st.set_page_config(
    page_title="Financial Health System | Đánh giá Sức khỏe Tài chính",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply emerald design system styles
apply_custom_styles()


def get_available_sample_options() -> Dict[str, Path]:
    """Helper for testing compatibility: returns available samples if file exists on disk."""
    candidates = [
        ("Mẫu 1", Path("data/samples/conghuy_A32_2020_sample.txt")),
        ("Mẫu 2", Path("data/samples/vduydong_A32_2017_sample.txt")),
    ]
    available: Dict[str, Path] = {}
    for label, path in candidates:
        if path.is_file():
            available[label] = path
    return available


def initialize_session_state() -> None:
    """Initialize session state variables to cache execution outputs across reruns."""
    if "stage" not in st.session_state:
        st.session_state.stage = "idle"  # 'idle' -> 'extracted' -> 'calculated'
    if "report" not in st.session_state:
        st.session_state.report = None
    if "df_bs" not in st.session_state:
        st.session_state.df_bs = None
    if "df_is" not in st.session_state:
        st.session_state.df_is = None
    if "ratio_report" not in st.session_state:
        st.session_state.ratio_report = None
    if "assessment" not in st.session_state:
        st.session_state.assessment = None
    if "ai_output" not in st.session_state:
        st.session_state.ai_output = None
    if "source_name" not in st.session_state:
        st.session_state.source_name = None
    if "extraction_method" not in st.session_state:
        st.session_state.extraction_method = None
    if "is_analyzed" not in st.session_state:
        st.session_state.is_analyzed = False
    if "ai_error" not in st.session_state:
        st.session_state.ai_error = None


def reset_analysis() -> None:
    """Clear cached pipeline results safely."""
    st.session_state.stage = "idle"
    st.session_state.report = None
    st.session_state.df_bs = None
    st.session_state.df_is = None
    st.session_state.ratio_report = None
    st.session_state.assessment = None
    st.session_state.ai_output = None
    st.session_state.source_name = None
    st.session_state.extraction_method = None
    st.session_state.is_analyzed = False
    st.session_state.ai_error = None


@st.cache_resource
def get_pdf_extractor() -> PDFExtractor:
    """Cache PDFExtractor instance across Streamlit reruns to eliminate model reloading."""
    return PDFExtractor(extract_tables=False)


def extract_financial_report(
    file_bytes: Optional[bytes],
    file_name: str,
    period: str = "current",
) -> Tuple[Optional[FinancialReport], Optional[str]]:
    """Step 1: Extract document text/OCR, parse statements, and run initial TT200 validation."""
    extraction_method = "Trích xuất văn bản"
    parser = FinancialStatementParser()

    if file_name.lower().endswith(".txt"):
        extraction_method = "Văn bản mẫu có cấu trúc"
        text_content = file_bytes.decode("utf-8", errors="replace") if file_bytes else ""
        if not text_content.strip():
            return None, "Tệp văn bản tải lên rỗng."
        report = parser.parse(text_content, source_name=file_name)
    else:
        extractor = get_pdf_extractor()
        try:
            extraction_result: DocumentExtractionResult = extractor.extract(
                file_input=file_bytes or b"", source_name=file_name
            )
        except Exception as exc:
            return None, f"Lỗi trong quá trình trích xuất tài liệu: {exc}"

        if not extraction_result.success:
            err_msg = " | ".join(extraction_result.errors) if extraction_result.errors else "Không trích xuất được nội dung"
            return None, f"Trích xuất thất bại: {err_msg}"

        if not extraction_result.full_text.strip():
            return None, "Không tìm thấy nội dung văn bản trong tài liệu tải lên."

        extraction_method = "PDF / OCR Hybrid"
        report = parser.parse(extraction_result, source_name=file_name)

    # Initial accounting equation check
    validator = FinancialValidator()
    validation_summary = validator.validate(report, period=period)
    report.validation_results = validation_summary

    has_bs_items = bool(report.balance_sheet and report.balance_sheet.items)
    has_is_items = bool(report.income_statement and report.income_statement.items)
    if not has_bs_items and not has_is_items:
        return report, "Không nhận diện được các chỉ tiêu Bảng Cân đối kế toán hoặc Kết quả kinh doanh."

    return report, extraction_method


def calculate_assessment_and_ai(
    report: FinancialReport,
    period: str = "current",
    enable_ai: bool = True,
) -> Tuple[FinancialRatioReport, FinancialAssessment, Optional[AIInterpretationOutput]]:
    """Step 2: Calculate financial ratios, assess health status, and generate AI interpretation."""
    calculator = FinancialRatioCalculator()
    ratio_report: FinancialRatioReport = calculator.calculate_all(report, period=period)

    assessor = FinancialHealthAssessor()
    assessment: FinancialAssessment = assessor.assess(ratio_report)

    ai_output = None
    st.session_state.ai_error = None

    if enable_ai:
        try:
            load_dotenv(override=True)
            interpreter = AIFinancialInterpreter()
            ai_output = interpreter.interpret(
                assessment=assessment,
                ratio_report=ratio_report,
                allow_fallback=True,
            )
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("Lỗi nhận định AI qua OpenRouter: %s", err_msg)
            st.session_state.ai_error = err_msg
            ai_output = None

    return ratio_report, assessment, ai_output


def execute_pipeline(
    file_bytes: Optional[bytes],
    file_name: str,
    period: str = "current",
    enable_ai: bool = True,
) -> Tuple[Optional[FinancialReport], Optional[FinancialAssessment], Optional[AIInterpretationOutput], Optional[str]]:
    """Execute end-to-end financial analysis pipeline (combines Step 1 and Step 2)."""
    report, method_or_err = extract_financial_report(file_bytes, file_name, period=period)
    if report is None:
        return None, None, None, method_or_err

    has_bs_items = bool(report.balance_sheet and report.balance_sheet.items)
    has_is_items = bool(report.income_statement and report.income_statement.items)
    if not has_bs_items and not has_is_items:
        return report, None, None, method_or_err

    ratio_report, assessment, ai_output = calculate_assessment_and_ai(
        report, period=period, enable_ai=enable_ai
    )
    return report, assessment, ai_output, method_or_err


# Initialize state
initialize_session_state()

# =============================================================================
# SIDEBAR CONTROLS
# =============================================================================
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

    # Primary file uploader
    uploaded_file = st.file_uploader(
        "Tải lên Báo cáo tài chính:",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        help="Hỗ trợ BCTC Hợp nhất hoặc BCTC Riêng theo Thông tư 200/VAS dạng PDF (vector/quét), ảnh chụp rõ nét hoặc text chuẩn hóa.",
    )

    # AI interpretation control
    enable_ai = st.toggle(
        "Nhận định chuyên sâu AI",
        value=True,
        help="Tự động phân tích điểm mạnh, rủi ro và khuyến nghị tài chính qua AI Gateway (Gemma / OpenRouter) hoặc Fallback xác định.",
    )

    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

    # Action buttons
    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        run_extract = st.button("🚀 Bóc Tách BCTC", type="primary", use_container_width=True)
    with col_btn2:
        if st.button("🔄 Đặt lại", use_container_width=True):
            reset_analysis()
            st.rerun()


# =============================================================================
# PIPELINE STEP 1: EXTRACTION TRIGGER
# =============================================================================
if run_extract:
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name

        with st.spinner("Đang bóc tách OCR và nhận diện cấu trúc BCTC theo TT200..."):
            report, method_or_err = extract_financial_report(
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


# =============================================================================
# MAIN DASHBOARD PRESENTATION
# =============================================================================
if st.session_state.stage == "idle":
    # 0. Hero Welcome View
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
    # 1. Step 1 View: Interactive Statement Data Editor
    report: FinancialReport = st.session_state.report
    company_name = report.company_name or "Doanh nghiệp"
    fiscal_year = report.fiscal_year or "Chưa xác định"

    st.markdown(
        f"""
        <div class="dashboard-header" style="padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;">
            <h2 style="color: white; margin: 0 0 0.35rem 0; font-size: 1.4rem;">📝 RÀ SOÁT & HIỆU CHỈNH SỐ LIỆU BCTC ĐÃ NHẬN DIỆN</h2>
            <div style="color: #e6f4ef; font-size: 0.9rem;">
                🏢 <strong>{company_name}</strong> | 📅 Năm tài chính: <strong>{fiscal_year}</strong> | 📄 Nguồn: <strong>{st.session_state.source_name}</strong>
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
                ratio_report, assessment, ai_output = calculate_assessment_and_ai(
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
    # 2. Step 2 View: 4 Core KPI Cards + AI Commentary
    assessment: FinancialAssessment = st.session_state.assessment
    ratio_report: FinancialRatioReport = st.session_state.ratio_report
    report: FinancialReport = st.session_state.report
    ai_output: Optional[AIInterpretationOutput] = st.session_state.ai_output

    # Top Header Banner
    render_header(
        company_name=assessment.company_name,
        fiscal_year=assessment.fiscal_year,
        currency=assessment.currency,
        source_name=st.session_state.source_name,
        extraction_method=st.session_state.extraction_method,
    )

    # Top Action Bar: Fast export buttons + company metadata
    render_top_action_bar(assessment, ai_output, report)

    # Collapsible Expander to inspect & re-edit recognized financial statement numbers anytime
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
                ratio_report, assessment, ai_output = calculate_assessment_and_ai(
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

    # 4 Core KPI Cards (Clean white card container, numbers highlighted in Green/Yellow/Red)
    render_core_4_kpi_cards(ratio_report, assessment)

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    # AI Commentary directly beneath the 4 KPI cards
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


