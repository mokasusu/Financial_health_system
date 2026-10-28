"""Thành phần giao diện đối soát, chỉnh sửa bảng biểu và kiểm định cân đối TT200 (Statement Tables).

Module này cung cấp:
- format_cell_number: Định dạng số nguyên hiển thị trong ô bảng kèm dấu ngoặc đơn cho số âm.
- parse_cell_to_decimal: Chuyển đổi dữ liệu ô bảng người dùng chỉnh sửa thành Decimal an toàn.
- get_statement_column_names: Xác định tên tiêu đề cột ngày/kỳ báo cáo trực quan cho Bảng CĐKT và Báo cáo KQKD.
- build_statement_dataframes: Chuyển đổi mô hình FinancialReport thành các DataFrame có thể chỉnh sửa trực tiếp.
- apply_edits_to_report: Đồng bộ các chỉnh sửa thủ công từ bảng giao diện ngược về mô hình thực thể và kiểm định lại TT200.
- render_financial_statements: Kết xuất giao diện đối soát Bảng CĐKT (B01-DN), KQKD (B02-DN) và Thẩm định cân đối TT200.
"""
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st

from src.domain.accounting.normalizer import AccountingNumberNormalizer
from src.domain.accounting.validator import FinancialValidator
from src.domain.models.bctc import CheckStatus, FinancialReport
from src.domain.models.line_item import MappingStatus
from src.presentation.formatters import format_currency, format_difference

# Ánh xạ tên tiếng Việt chuẩn mực cho các chỉ tiêu tài chính
CANONICAL_VIETNAMESE_NAMES: Dict[str, str] = {
    # Bảng Cân đối kế toán (Mẫu B 01 - DN)
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
    # Báo cáo Kết quả hoạt động kinh doanh (Mẫu B 02 - DN)
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
    """Định dạng số tiền hiển thị trong ô bảng có phân cách hàng nghìn và ngoặc đơn cho số âm.

    Args:
        val (Optional[Decimal]): Giá trị Decimal hoặc None.

    Returns:
        str: Chuỗi số đã định dạng (ví dụ: '150,000,000' hoặc '(25,000,000)').
    """
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
    """Chuyển đổi linh hoạt dữ liệu người dùng nhập trong ô bảng thành đối tượng Decimal chuẩn xác.

    Hỗ trợ xử lý:
    - Ký tự gạch ngang ("-", "—") đại diện cho giá trị 0.
    - Số âm đặt trong dấu ngoặc đơn dạng kế toán: (123,456) -> Decimal('-123456').
    - Chuỗi có dấu phẩy hoặc chấm phân cách hàng nghìn.

    Args:
        val (Any): Dữ liệu ô nhập vào.

    Returns:
        Optional[Decimal]: Giá trị Decimal hoặc None nếu để trống hoặc không hợp lệ.
    """
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

    digits = re.sub(r"[^\d]", "", raw)
    if digits:
        d = Decimal(digits)
        return -d if is_neg else d
    return None


def get_statement_column_names(report: Optional[FinancialReport]) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """Xác định tên tiêu đề hiển thị cho 2 cột kỳ báo cáo của Bảng CĐKT và Báo cáo KQKD.

    Args:
        report (Optional[FinancialReport]): Mô hình báo cáo tài chính đã bóc tách.

    Returns:
        Tuple[Tuple[str, str], Tuple[str, str]]:
            ((Tên cột CĐKT kỳ này, Tên cột CĐKT kỳ trước), (Tên cột KQKD kỳ này, Tên cột KQKD kỳ trước)).
    """
    if not report:
        return ("Kỳ này (VND)", "Kỳ trước (VND)"), ("Kỳ này (VND)", "Kỳ trước (VND)")

    bs_cur = None
    bs_prev = None

    if report.balance_sheet:
        cur_raw = getattr(report.balance_sheet, "current_period_name", None)
        prev_raw = getattr(report.balance_sheet, "previous_period_name", None)
        if cur_raw and prev_raw:
            as_of = report.balance_sheet.as_of_date or getattr(report, "as_of_date", None)
            if "cuối" in cur_raw.lower() and as_of:
                bs_cur = f"{as_of} ({cur_raw})"
                year = report.fiscal_year
                if year:
                    bs_prev = f"01/01/{year} ({prev_raw})"
                else:
                    bs_prev = prev_raw
            else:
                bs_cur = cur_raw
                bs_prev = prev_raw

    if not bs_cur:
        as_of = (report.balance_sheet.as_of_date if report.balance_sheet else None) or getattr(report, "as_of_date", None)
        year = report.fiscal_year
        if as_of:
            bs_cur = as_of
            if year:
                bs_prev = f"01/01/{year}"
            else:
                bs_prev = "Kỳ trước (VND)"
        elif year:
            bs_cur = f"31/12/{year}"
            bs_prev = f"01/01/{year}"
        else:
            bs_cur = "Kỳ này (VND)"
            bs_prev = "Kỳ trước (VND)"

    is_cur = None
    is_prev = None

    if report.income_statement:
        cur_raw = getattr(report.income_statement, "current_period_name", None)
        prev_raw = getattr(report.income_statement, "previous_period_name", None)
        if cur_raw and prev_raw:
            is_cur = cur_raw
            is_prev = prev_raw

    if not is_cur:
        period = (report.income_statement.period if report.income_statement else None) or getattr(report, "period", None)
        year = report.fiscal_year
        if period and "năm" in period.lower() and year:
            is_cur = f"Năm {year}"
            is_prev = f"Năm {year - 1}"
        elif period:
            is_cur = period
            is_prev = f"{period} (Kỳ trước)"
        elif year:
            is_cur = f"Năm {year}"
            is_prev = f"Năm {year - 1}"
        else:
            is_cur = "Kỳ này (VND)"
            is_prev = "Kỳ trước (VND)"

    return (bs_cur, bs_prev), (is_cur, is_prev)


def _extract_row_period_values(row: pd.Series) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Trích xuất giá trị số Decimal kỳ này và kỳ trước từ một hàng của DataFrame.

    Args:
        row (pd.Series): Dòng dữ liệu từ DataFrame.

    Returns:
        Tuple[Optional[Decimal], Optional[Decimal]]: (Số tiền kỳ này, Số tiền kỳ trước).
    """
    if "Kỳ này (VND)" in row and "Kỳ trước (VND)" in row:
        return parse_cell_to_decimal(row.get("Kỳ này (VND)")), parse_cell_to_decimal(row.get("Kỳ trước (VND)"))

    val_cols = [c for c in row.index if c not in ("canonical_key", "Mã số", "Chỉ tiêu BCTC")]
    if len(val_cols) >= 2:
        return parse_cell_to_decimal(row.get(val_cols[0])), parse_cell_to_decimal(row.get(val_cols[1]))
    elif len(val_cols) == 1:
        return parse_cell_to_decimal(row.get(val_cols[0])), None
    return None, None


def build_statement_dataframes(report: FinancialReport) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Chuyển đổi dữ liệu các chỉ tiêu BCTC đã ánh xạ thành 2 DataFrame có thể chỉnh sửa trực tiếp.

    Args:
        report (FinancialReport): Mô hình báo cáo tài chính.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (DataFrame Bảng CĐKT, DataFrame Báo cáo KQKD).
    """
    (bs_cur_col, bs_prev_col), (is_cur_col, is_prev_col) = get_statement_column_names(report)

    # 1. Xây dựng DataFrame Bảng CĐKT
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

    # 2. Xây dựng DataFrame Báo cáo KQKD
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
    """Đồng bộ các chỉnh sửa thủ công của người dùng trên bảng ngược về FinancialReport và kiểm định lại TT200.

    Args:
        report (FinancialReport): Báo cáo tài chính hiện tại.
        edited_df_bs (Optional[pd.DataFrame]): DataFrame Bảng CĐKT sau khi người dùng sửa.
        edited_df_is (Optional[pd.DataFrame]): DataFrame Báo cáo KQKD sau khi người dùng sửa.

    Returns:
        FinancialReport: Báo cáo tài chính đã cập nhật số liệu mới và kết quả kiểm định cân đối mới.
    """
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

    # Tái kiểm định các hằng đẳng thức kế toán Thông tư 200 với số liệu mới
    validator = FinancialValidator()
    report.validation_results = validator.validate(report)
    return report


def render_financial_statements(report: FinancialReport) -> None:
    """Kết xuất giao diện tab đối soát dữ liệu chỉ tiêu tài chính và thẩm định cân đối TT200.

    Args:
        report (FinancialReport): Báo cáo tài chính đã chuẩn hóa.
    """
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
