"""Thành phần giao diện khu vực xuất khẩu dữ liệu phân tích (Export Panel Component).

Module này cung cấp hàm render_export_section hiển thị các nút tải xuống tiện lợi:
1. Tệp JSON đầy đủ cấu trúc gồm siêu dữ liệu, 14 chỉ số, cảnh báo rủi ro, kết quả cân đối TT200 và nhận định AI.
2. Tệp CSV 14 chỉ số tài chính (hỗ trợ hiển thị Tiếng Việt trên Excel với mã hóa UTF-8 BOM).
3. Tệp CSV danh sách cảnh báo rủi ro và khuyến nghị quản trị doanh nghiệp.
"""
from typing import Optional
import streamlit as st

from src.application.services.export_service import (
    export_analysis_to_json,
    export_ratios_to_csv,
    export_warnings_to_csv,
)
from src.domain.models.ai import AIInterpretationOutput
from src.domain.models.assessment import FinancialAssessment
from src.domain.models.bctc import FinancialReport


def render_export_section(
    assessment: FinancialAssessment,
    ai_output: Optional[AIInterpretationOutput] = None,
    report: Optional[FinancialReport] = None,
) -> None:
    """Kết xuất khu vực tải tệp xuất khẩu dữ liệu phân tích sang định dạng JSON và CSV.

    Args:
        assessment (FinancialAssessment): Kết quả đánh giá sức khỏe tài chính và 14 chỉ số.
        ai_output (Optional[AIInterpretationOutput]): Dữ liệu diễn giải từ AI (tùy chọn).
        report (Optional[FinancialReport]): Báo cáo tài chính gốc kèm kiểm tra cân đối TT200 (tùy chọn).
    """
    st.markdown("### 📥 Xuất Kết quả Phân tích")
    c1, c2, c3 = st.columns(3)

    # 1. Xuất khẩu tệp JSON đầy đủ cấu trúc
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

    # 2. Xuất khẩu tệp CSV 14 chỉ số tài chính
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

    # 3. Xuất khẩu tệp CSV danh sách cảnh báo rủi ro
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
