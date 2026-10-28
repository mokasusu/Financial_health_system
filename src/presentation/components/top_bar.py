"""Thành phần giao diện biểu ngữ trên cùng và thanh thao tác nhanh (Top Bar Components).

Module này cung cấp:
- render_header: Kết xuất biểu ngữ tiêu đề trang trọng với hiệu ứng gradient Emerald Green,
  hiển thị tên công ty, niên độ kế toán, đơn vị tiền tệ, tệp tài liệu và phương thức bóc tách.
- render_top_action_bar: Kết xuất thanh thao tác nhanh ngay đầu trang với các nút bấm tải
  báo cáo JSON đầy đủ và tệp CSV 14 chỉ số tài chính được mã hóa UTF-8 BOM.
"""
from typing import Optional
import streamlit as st

from src.application.services.export_service import export_analysis_to_json, export_ratios_to_csv
from src.domain.models.ai import AIInterpretationOutput
from src.domain.models.assessment import FinancialAssessment
from src.domain.models.bctc import FinancialReport


def render_header(
    company_name: Optional[str],
    fiscal_year: Optional[int],
    currency: str = "VND",
    source_name: Optional[str] = None,
    extraction_method: Optional[str] = None,
    as_of_date: Optional[str] = None,
    period: Optional[str] = None,
) -> None:
    """Kết xuất biểu ngữ tiêu đề bảng điều khiển với siêu dữ liệu doanh nghiệp và tài liệu.

    Args:
        company_name (Optional[str]): Tên công ty được kiểm toán/báo cáo.
        fiscal_year (Optional[int]): Năm tài chính.
        currency (str): Đơn vị tiền tệ hiển thị (mặc định 'VND').
        source_name (Optional[str]): Tên tệp nguồn tài liệu tải lên.
        extraction_method (Optional[str]): Phương pháp trích xuất đã dùng.
        as_of_date (Optional[str]): Ngày lập Bảng CĐKT (DD/MM/YYYY).
        period (Optional[str]): Nhãn thời kỳ Báo cáo KQKD (ví dụ: 'Năm 2020').
    """
    display_company = company_name or "Doanh nghiệp (Chưa xác định tên từ BCTC)"

    if as_of_date:
        display_date = f"Ngày báo cáo: {as_of_date}"
        if fiscal_year and str(fiscal_year) not in as_of_date:
            display_date += f" (Năm {fiscal_year})"
    elif fiscal_year:
        display_date = f"Năm tài chính: {fiscal_year}"
    elif period:
        display_date = f"Kỳ báo cáo: {period}"
    else:
        display_date = "Kỳ báo cáo: Chưa xác định"

    display_source = f"Nguồn: {source_name}" if source_name else "Nguồn: Tải lên trực tiếp"
    display_method = f"Phương thức: {extraction_method}" if extraction_method else "Chuẩn hóa TT200"

    header_html = f"""
    <div class="dashboard-header">
        <h1>📊 BÁO CÁO PHÂN TÍCH SỨC KHỎE TÀI CHÍNH DOANH NGHIỆP</h1>
        <p><strong>{display_company}</strong></p>
        <div style="margin-top: 0.5rem;">
            <span class="meta-tag">📅 {display_date}</span>
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
    """Kết xuất thanh thao tác nhanh trên cùng với các nút tải nhanh tệp báo cáo JSON và CSV.

    Args:
        assessment (FinancialAssessment): Đánh giá tài chính và 14 tỷ số.
        ai_output (Optional[AIInterpretationOutput]): Nhận định từ AI (nếu có).
        report (Optional[FinancialReport]): Báo cáo tài chính gốc (nếu có).
    """
    c_info, c_btn1, c_btn2 = st.columns([2.5, 1, 1])
    company_name = assessment.company_name or "Doanh nghiệp"
    as_of = getattr(assessment, "as_of_date", None) or (report.as_of_date if report else None)
    if as_of:
        year_str = f"Tại ngày {as_of}"
    elif assessment.fiscal_year:
        year_str = f"Năm {assessment.fiscal_year}"
    else:
        year_str = "Kỳ phân tích"
    company_tag = company_name.replace(" ", "_")
    fiscal_tag = getattr(assessment, "as_of_date", None) or assessment.fiscal_year or "period"

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
