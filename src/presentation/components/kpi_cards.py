"""Thành phần giao diện thẻ chỉ số tài chính cốt lõi (Core 4 KPI Cards).

Module này kết xuất 4 thẻ chỉ số tài chính trọng yếu nhất trên đầu trang bảng điều khiển:
1. Khả năng thanh toán hiện hành (Current Ratio) - Đệm an toàn thanh khoản ngắn hạn.
2. Hệ số Nợ / Vốn chủ sở hữu (Debt to Equity) - Áp lực đòn bẩy và cơ cấu nguồn vốn.
3. Tỷ suất sinh lời trên Tổng tài sản (ROA) - Hiệu quả khai thác tài sản sinh lời.
4. Tỷ suất sinh lời trên Vốn chủ sở hữu (ROE) - Mức sinh lời cho cổ đông và chủ sở hữu.
"""
from decimal import Decimal
from typing import Optional, Tuple
import streamlit as st

from src.domain.models.assessment import FinancialAssessment
from src.domain.models.ratios import FinancialRatioReport, RatioResult, RatioStatus


def _get_badge_text_color(bg: str) -> str:
    """Trả về mã màu chữ có độ tương phản cao tương ứng với màu nền của huy hiệu.

    Args:
        bg (str): Mã màu hex của nền huy hiệu.

    Returns:
        str: Mã màu hex của chữ (ví dụ: '#065f46' cho nền xanh nhạt).
    """
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
    """Xác định các thông số hiển thị trực quan cho một thẻ KPI tài chính.

    Bao gồm chuỗi giá trị số đã định dạng, màu chữ giá trị, nhãn huy hiệu trạng thái,
    màu nền và màu viền của huy hiệu dựa theo các ngưỡng tài chính kinh nghiệm.

    Args:
        ratio_key (str): Khóa chỉ số ("current_ratio", "debt_to_equity", "roa", "roe").
        ratio_res (Optional[RatioResult]): Kết quả tính toán chỉ số tài chính.

    Returns:
        Tuple[str, str, str, str, str]: (Giá trị hiển thị, Màu chữ, Nhãn trạng thái, Màu nền huy hiệu, Màu viền huy hiệu).
    """
    if (
        ratio_res is None
        or ratio_res.value is None
        or ratio_res.status in (RatioStatus.NOT_AVAILABLE, RatioStatus.NOT_APPLICABLE)
    ):
        return ("N/A", "#64748b", "THIẾU DỮ LIỆU", "#f1f5f9", "#cbd5e1")

    val = ratio_res.value

    # Đánh giá Thanh toán hiện hành (Current Ratio)
    if ratio_key == "current_ratio":
        if val >= Decimal("1.5"):
            return (f"{val:.2f} lần", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val >= Decimal("1.0"):
            return (f"{val:.2f} lần", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2f} lần", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    # Đánh giá Hệ số Nợ / Vốn CSH (Debt to Equity)
    elif ratio_key == "debt_to_equity":
        if ratio_res.status == RatioStatus.UNDEFINED or val < Decimal("0"):
            return ("VCSH ÂM", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")
        if val <= Decimal("1.0"):
            return (f"{val:.2f} lần", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val <= Decimal("2.0"):
            return (f"{val:.2f} lần", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2f} lần", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    # Đánh giá ROA
    elif ratio_key == "roa":
        if val >= Decimal("0.05"):
            return (f"{val:.2%}", "#16a34a", "AN TOÀN", "#ecfdf5", "#a7f3d0")
        elif val >= Decimal("0.0"):
            return (f"{val:.2%}", "#d97706", "CẢNH BÁO", "#fffbeb", "#fde68a")
        else:
            return (f"{val:.2%}", "#dc2626", "NGUY HIỂM", "#fef2f2", "#fecaca")

    # Đánh giá ROE
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
    """Kết xuất 4 thẻ KPI tài chính cốt lõi trên bố cục lưới 4 cột ngang.

    Args:
        ratio_report (FinancialRatioReport): Báo cáo tỷ số tài chính đã tính toán.
        assessment (Optional[FinancialAssessment]): Đánh giá tài chính nghiệp vụ (tùy chọn).
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
            "Tỷ suất sinh lời / Tài sản (ROA)",
            "LN sau thuế / Tổng tài sản bình quân (Chuẩn: ≥ 5.0%)",
        ),
        (
            col4,
            "roe",
            "Tỷ suất sinh lời / Vốn CSH (ROE)",
            "LN sau thuế / Vốn CSH bình quân (Chuẩn: ≥ 12.0%)",
        ),
    ]

    for col, key, title, subtext in configs:
        r_item = ratio_report.get_ratio(key)
        val_str, text_color, badge_lbl, badge_bg, badge_border = _evaluate_kpi_visual(key, r_item)

        with col:
            card_html = f"""
            <div class="kpi-card" style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); min-height: 160px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.85rem; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.025em;">
                            {title}
                        </span>
                        <span style="background-color: {badge_bg}; color: {_get_badge_text_color(badge_bg)}; border: 1px solid {badge_border}; font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 9999px;">
                            {badge_lbl}
                        </span>
                    </div>
                    <div style="font-size: 1.85rem; font-weight: 800; color: {text_color}; line-height: 1.1; margin: 0.35rem 0;">
                        {val_str}
                    </div>
                </div>
                <div style="font-size: 0.725rem; color: #64748b; line-height: 1.35; margin-top: 0.5rem; border-top: 1px dashed #e2e8f0; padding-top: 0.4rem;">
                    {subtext}
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
