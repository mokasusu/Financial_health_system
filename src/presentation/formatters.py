"""Tiện ích định dạng dữ liệu cho Bảng điều khiển Sức khỏe Tài chính (Dashboard Formatters).

Module này cung cấp các hàm hỗ trợ định dạng số tiền kế toán có phân cách hàng nghìn,
tỷ lệ phần trăm, giá trị tỷ số kèm đơn vị đo lường, và chênh lệch số học trong các phép
kiểm tra cân đối Thông tư 200.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional, Union


def format_currency(
    value: Optional[Union[Decimal, float, int, str]],
    unit: str = "VND",
    default: str = "N/A",
) -> str:
    """Định dạng số tiền kế toán với dấu phẩy phân cách hàng nghìn và đơn vị tiền tệ.

    Args:
        value (Optional[Union[Decimal, float, int, str]]): Giá trị số tiền cần định dạng.
        unit (str): Nhãn đơn vị tiền tệ (ví dụ: 'VND', 'nghìn VND', 'USD').
        default (str): Chuỗi mặc định trả về nếu giá trị là None hoặc không hợp lệ.

    Returns:
        str: Chuỗi số tiền đã định dạng (ví dụ: '145,230,000 VND' hoặc 'N/A').
    """
    if value is None:
        return default

    try:
        if isinstance(value, str):
            dec_val = Decimal(value.strip().replace(",", ""))
        else:
            dec_val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

    if dec_val == dec_val.to_integral():
        formatted_num = f"{int(dec_val):,}"
    else:
        formatted_num = f"{dec_val:,.2f}"

    return f"{formatted_num} {unit}".strip()


def format_percentage(
    value: Optional[Union[Decimal, float, str]],
    decimals: int = 2,
    default: str = "N/A",
) -> str:
    """Định dạng giá trị tỷ suất sang dạng phần trăm với số chữ số thập phân chỉ định.

    Args:
        value (Optional[Union[Decimal, float, str]]): Giá trị thập phân (ví dụ: 0.154 tương ứng 15.4%).
        decimals (int): Số chữ số thập phân sau dấu phẩy (mặc định 2).
        default (str): Chuỗi mặc định khi giá trị là None.

    Returns:
        str: Chuỗi phần trăm (ví dụ: '15.40%').
    """
    if value is None:
        return default

    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

    pct_val = dec_val * Decimal("100")
    fmt = f"{{:.{decimals}f}}%"
    return fmt.format(pct_val)


def format_ratio_value(
    value: Optional[Union[Decimal, float, str]],
    unit: str = "lần",
    decimals: int = 2,
    default: str = "N/A",
) -> str:
    """Định dạng tỷ số tài chính kèm theo đơn vị đo lường tương ứng.

    Args:
        value (Optional[Union[Decimal, float, str]]): Giá trị số tỷ số.
        unit (str): Đơn vị tỷ số ('lần', '%', 'vòng', 'ngày').
        decimals (int): Độ chính xác số thập phân.
        default (str): Chuỗi trả về khi giá trị là None.

    Returns:
        str: Chuỗi tỷ số định dạng (ví dụ: '1.45 lần' hoặc '12.50%').
    """
    if value is None:
        return default

    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

    if unit == "%":
        pct_val = dec_val * Decimal("100") if abs(dec_val) <= Decimal("5.0") else dec_val
        return f"{pct_val:.{decimals}f}%"

    return f"{dec_val:.{decimals}f} {unit}".strip()


def format_difference(
    difference: Optional[Decimal],
    tolerance: Optional[Decimal] = None,
    default: str = "Không xác định",
) -> str:
    """Định dạng giá trị chênh lệch kiểm tra cân đối kế toán kèm ngữ cảnh dung sai cho phép.

    Args:
        difference (Optional[Decimal]): Độ chênh lệch số học tuyệt đối giữa hai vế phương trình.
        tolerance (Optional[Decimal]): Mức dung sai chấp nhận được tối đa.
        default (str): Chuỗi mặc định khi chênh lệch là None.

    Returns:
        str: Chuỗi mô tả trạng thái cân đối (ví dụ: 'Cân đối tuyệt đối (0 VND)' hoặc 'Chênh lệch: 1,000 VND').
    """
    if difference is None:
        return default

    if difference == Decimal("0"):
        return "Cân đối tuyệt đối (0 VND)"

    formatted_diff = format_currency(difference, unit="VND")
    if tolerance is not None:
        formatted_tol = format_currency(tolerance, unit="VND")
        return f"Chênh lệch: {formatted_diff} (Dung sai: {formatted_tol})"
    return f"Chênh lệch: {formatted_diff}"
