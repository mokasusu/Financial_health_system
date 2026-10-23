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
from typing import Optional, Tuple
from dotenv import load_dotenv
import streamlit as st

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
from src.ui.components import (
    render_ai_interpretation,
    render_export_section,
    render_financial_statements,
    render_header,
    render_health_assessment,
    render_kpi_cards,
    render_ratio_analysis,
)
from src.ui.styles import apply_custom_styles


# Page Configuration
st.set_page_state = getattr(st, "set_page_state", None)
st.set_page_config(
    page_title="Financial Health System | Đánh giá Sức khỏe Tài chính",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply emerald design system styles
apply_custom_styles()

# Built-in Sample Paths
SAMPLES_DIR = Path("data/samples")
SAMPLE_OPTIONS = {
    "Không dùng mẫu (Tải file của bạn lên)": None,
    "Mẫu 1: CTCP 32 (Năm 2020) - BCTC Kiểm toán TT200": SAMPLES_DIR / "conghuy_A32_2020_sample.txt",
    "Mẫu 2: CTCP 32 (Năm 2017) - BCTC Đầy đủ": SAMPLES_DIR / "vduydong_A32_2017_sample.txt",
}


def initialize_session_state() -> None:
    """Initialize session state variables to cache execution outputs across reruns."""
    if "report" not in st.session_state:
        st.session_state.report = None
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


def reset_analysis() -> None:
    """Clear cached pipeline results safely."""
    st.session_state.report = None
    st.session_state.ratio_report = None
    st.session_state.assessment = None
    st.session_state.ai_output = None
    st.session_state.source_name = None
    st.session_state.extraction_method = None
    st.session_state.is_analyzed = False


def execute_pipeline(
    file_bytes: Optional[bytes],
    file_name: str,
    period: str = "current",
    enable_ai: bool = True,
) -> Tuple[Optional[FinancialReport], Optional[FinancialAssessment], Optional[AIInterpretationOutput], Optional[str]]:
    """Execute end-to-end financial analysis pipeline through existing Python engines."""
    # Step 1: Document Extraction
    extraction_method = "Trích xuất văn bản"
    parser = FinancialStatementParser()

    if file_name.lower().endswith(".txt"):
        # Direct parsing for standard text samples
        extraction_method = "Văn bản mẫu có cấu trúc"
        text_content = file_bytes.decode("utf-8", errors="replace") if file_bytes else ""
        if not text_content.strip():
            return None, None, None, "Tệp văn bản tải lên rỗng."
        report = parser.parse(text_content, source_name=file_name)
    else:
        # PDF or standalone image via OCR/PDF extraction
        extractor = PDFExtractor(extract_tables=False)
        try:
            extraction_result: DocumentExtractionResult = extractor.extract(
                file_input=file_bytes or b"", source_name=file_name
            )
        except Exception as exc:
            return None, None, None, f"Lỗi trong quá trình trích xuất tài liệu: {exc}"

        if not extraction_result.success:
            err_msg = " | ".join(extraction_result.errors) if extraction_result.errors else "Không trích xuất được nội dung"
            return None, None, None, f"Trích xuất thất bại: {err_msg}"

        if not extraction_result.full_text.strip():
            return None, None, None, "Không tìm thấy nội dung văn bản trong tài liệu tải lên."

        extraction_method = "PDF / OCR Hybrid"
        report = parser.parse(extraction_result, source_name=file_name)

    # Step 2: Validate Accounting Equations (TT200)
    validator = FinancialValidator()
    validation_summary = validator.validate(report, period=period)
    report.validation_results = validation_summary

    # Check if any financial line items exist
    has_bs_items = bool(report.balance_sheet and report.balance_sheet.items)
    has_is_items = bool(report.income_statement and report.income_statement.items)
    if not has_bs_items and not has_is_items:
        return report, None, None, "Không nhận diện được các chỉ tiêu Bảng Cân đối kế toán hoặc Kết quả kinh doanh."

    # Step 3: Calculate 14 Financial Ratios
    calculator = FinancialRatioCalculator()
    ratio_report: FinancialRatioReport = calculator.calculate_all(report, period=period)

    # Step 4: Health Assessment & Prioritized Risk Warnings
    assessor = FinancialHealthAssessor()
    assessment: FinancialAssessment = assessor.assess(ratio_report)

    # Step 5: AI Interpretation (or Deterministic Fallback)
    ai_output = None
    if enable_ai:
        try:
            interpreter = AIFinancialInterpreter()
            ai_output = interpreter.interpret(assessment, allow_fallback=True)
        except Exception as exc:
            # Fallback to local rule engine if API key is missing or OpenRouter fails
            from src.financial.openrouter_client import OpenRouterClient, OpenRouterConfig
            dummy_config = OpenRouterConfig(api_key="fallback-placeholder", model="google/gemma-4-31b-it:free")
            dummy_client = OpenRouterClient(config=dummy_config)
            fallback_interpreter = AIFinancialInterpreter(client=dummy_client)
            ai_output = fallback_interpreter.generate_deterministic_fallback(
                assessment=assessment,
                error_reason=f"OpenRouter API chưa sẵn sàng hoặc chưa cấu hình: {exc}",
            )

    return report, assessment, ai_output, extraction_method


# Initialize state
initialize_session_state()

# =============================================================================
# SIDEBAR CONTROLS
# =============================================================================
with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; padding: 0.5rem 0 1rem 0;">
            <div style="font-size: 2rem;">🏛️</div>
            <h2 style="color: #006c49; margin: 0; font-size: 1.35rem;">Financial Health System</h2>
            <p style="color: #64748b; font-size: 0.8rem; margin: 0;">Đánh giá sức khỏe tài chính DN Việt Nam</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.subheader("1. Nguồn Dữ Liệu")

    # Sample selector
    selected_sample_label = st.selectbox(
        "Dùng mẫu BCTC có sẵn:",
        options=list(SAMPLE_OPTIONS.keys()),
        index=1,  # Default to Sample 1 (CTCP 32 năm 2020) for instant out-of-the-box readiness!
    )
    selected_sample_path = SAMPLE_OPTIONS[selected_sample_label]

    # File uploader
    uploaded_file = st.file_uploader(
        "Hoặc tải lên BCTC (PDF, Ảnh hoặc TXT):",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        help="Hỗ trợ báo cáo tài chính định dạng PDF, ảnh chụp rõ nét hoặc file text chuẩn hóa.",
    )

    st.markdown("---")
    st.subheader("2. Cấu Hình Phân Tích")

    # Reporting period selection
    period_option = st.selectbox(
        "Kỳ báo cáo:",
        options=["current", "previous"],
        format_func=lambda x: "Kỳ hiện hành (Current Period)" if x == "current" else "Kỳ trước (Previous Period)",
    )

    # AI interpretation control
    enable_ai = st.toggle("Bật nhận định AI (OpenRouter)", value=True)

    # OpenRouter status indicator
    has_api_key = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    if has_api_key:
        model_name = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
        st.caption(f"🟢 OpenRouter API đã sẵn sàng (`{model_name}`).")
    else:
        st.caption("🟡 Chưa cấu hình `OPENROUTER_API_KEY`. Hệ thống sẽ tự động dùng Deterministic Fallback.")

    st.markdown("---")

    # Action buttons
    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        run_analysis = st.button("🚀 Phân Tích", type="primary", use_container_width=True)
    with col_btn2:
        if st.button("🔄 Đặt lại", use_container_width=True):
            reset_analysis()
            st.rerun()


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================
if run_analysis:
    file_bytes: Optional[bytes] = None
    file_name: str = ""

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name
    elif selected_sample_path is not None and selected_sample_path.is_file():
        file_bytes = selected_sample_path.read_bytes()
        file_name = selected_sample_path.name
    else:
        st.error("Vui lòng chọn một mẫu BCTC có sẵn hoặc tải tệp lên từ máy tính.")

    if file_bytes:
        with st.spinner("Đang xử lý trích xuất, kiểm định kế toán và đánh giá tài chính..."):
            report, assessment, ai_output, method_or_err = execute_pipeline(
                file_bytes=file_bytes,
                file_name=file_name,
                period=period_option,
                enable_ai=enable_ai,
            )

            if assessment is None:
                st.error(f"❌ Không thể hoàn tất phân tích: {method_or_err}")
            else:
                # Save to session state
                st.session_state.report = report
                st.session_state.assessment = assessment
                st.session_state.ai_output = ai_output
                st.session_state.source_name = file_name
                st.session_state.extraction_method = method_or_err
                st.session_state.is_analyzed = True
                st.success("✅ Phân tích báo cáo tài chính thành công!")


# =============================================================================
# MAIN DASHBOARD PRESENTATION
# =============================================================================
if not st.session_state.is_analyzed or st.session_state.assessment is None:
    # Empty welcome hero state
    st.markdown(
        """
        <div style="background-color: #ffffff; border: 1.5px dashed #cbd5e1; border-radius: 12px; padding: 3rem 2rem; text-align: center; margin-top: 1rem;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">📈</div>
            <h3 style="color: #006c49; margin-bottom: 0.5rem;">Sẵn sàng Phân tích Sức khỏe Tài chính Doanh nghiệp</h3>
            <p style="color: #64748b; max-width: 650px; margin: 0 auto 1.5rem auto; font-size: 0.95rem; line-height: 1.6;">
                Hệ thống tích hợp đường ống phân tích BCTC chuẩn mực TT200/2014/TT-BTC:
                Trích xuất OCR &rarr; Chuẩn hóa &rarr; Kiểm tra cân đối kế toán &rarr;
                Tính toán 14 tỷ số tài chính chính xác &rarr; Đánh giá cảnh báo rủi ro &rarr; Nhận định AI chuyên sâu.
            </p>
            <div style="font-size: 0.875rem; color: #475569;">
                👈 Chọn <strong>Mẫu BCTC có sẵn</strong> hoặc tải tệp BCTC của bạn lên tại thanh điều khiển bên trái, sau đó nhấn <strong>Phân Tích</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    # 1. Header Banner
    assessment: FinancialAssessment = st.session_state.assessment
    report: Optional[FinancialReport] = st.session_state.report
    ai_output: Optional[AIInterpretationOutput] = st.session_state.ai_output

    render_header(
        company_name=assessment.company_name,
        fiscal_year=assessment.fiscal_year,
        currency=assessment.currency,
        source_name=st.session_state.source_name,
        extraction_method=st.session_state.extraction_method,
    )

    # 2. Executive KPI Cards
    render_kpi_cards(assessment)

    st.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)

    # 3. Main Analytical Tabs
    main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs([
        "🏥 Sức khỏe & Cảnh báo",
        "📊 14 Tỷ số Tài chính",
        "🤖 Nhận định Chuyên sâu AI",
        "📑 Số liệu BCTC & Kiểm định TT200",
        "📥 Xuất Báo cáo",
    ])

    with main_tab1:
        render_health_assessment(assessment)

    with main_tab2:
        render_ratio_analysis(assessment)

    with main_tab3:
        render_ai_interpretation(ai_output)

    with main_tab4:
        if report:
            render_financial_statements(report)
        else:
            st.info("Không có dữ liệu báo cáo tài chính gốc.")

    with main_tab5:
        render_export_section(assessment, ai_output, report)
