"""Data formatting utilities for Financial Health Dashboard (Sprint 6).

Provides defensive and locale-appropriate formatting for:
- Vietnam Dong (VND) and custom currency units
- Percentage, multiples, and turnover ratios
- Validation differences and tolerances
- Graceful handling of None, Decimal, zero values, and NaN/Infinity
"""
from decimal import Decimal, InvalidOperation
from typing import Optional, Union


def format_currency(
    value: Optional[Union[Decimal, float, int, str]],
    unit: str = "VND",
    default: str = "N/A",
) -> str:
    """Format an accounting monetary figure with thousands separators.

    Args:
        value: Monetary value in Decimal, float, int, or string.
        unit: Currency unit label (e.g. 'VND', 'nghìn VND').
        default: Fallback text when value is None or invalid.

    Returns:
        Formatted string, e.g. '145,230,000 VND' or 'N/A'.
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

    # If number is an integer or has negligible fractional part
    if dec_val == dec_val.to_integral():
        formatted_num = f"{int(dec_val):,}"
    else:
        # Round to 2 decimal places
        formatted_num = f"{dec_val:,.2f}"

    return f"{formatted_num} {unit}".strip()


def format_percentage(
    value: Optional[Union[Decimal, float, str]],
    decimals: int = 2,
    default: str = "N/A",
) -> str:
    """Format a ratio value as a percentage.

    Args:
        value: Decimal or float value (e.g. 0.154 for 15.4% or 15.4 if pre-scaled).
        decimals: Number of decimal places.
        default: Fallback text when value is None.

    Returns:
        Formatted percentage string, e.g. '15.40%'.
    """
    if value is None:
        return default

    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

    # In our ratio engine, percentage ratios like NPM, ROE, debt_to_assets
    # are stored as fractions (e.g. 0.054 for 5.4%) or pre-formatted.
    pct_val = dec_val * Decimal("100")
    fmt = f"{{:.{decimals}f}}%"
    return fmt.format(pct_val)


def format_ratio_value(
    value: Optional[Union[Decimal, float, str]],
    unit: str = "lần",
    decimals: int = 2,
    default: str = "N/A",
) -> str:
    """Format a financial ratio with its corresponding unit.

    Args:
        value: Exact Decimal or numeric value.
        unit: Ratio unit ('lần', '%', 'vòng', 'ngày').
        decimals: Decimal precision.
        default: Fallback text when None.

    Returns:
        Formatted ratio string, e.g. '1.45 lần' or '12.50%'.
    """
    if value is None:
        return default

    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

    if unit == "%":
        # Check if already in 0-1 range vs 0-100 range
        pct_val = dec_val * Decimal("100") if abs(dec_val) <= Decimal("5.0") else dec_val
        return f"{pct_val:.{decimals}f}%"

    return f"{dec_val:.{decimals}f} {unit}".strip()


def format_difference(
    difference: Optional[Decimal],
    tolerance: Optional[Decimal] = None,
    default: str = "Không xác định",
) -> str:
    """Format an accounting check difference with tolerance context.

    Args:
        difference: Absolute or signed difference between equation sides.
        tolerance: Maximum acceptable tolerance.
        default: Fallback text.

    Returns:
        Human-readable difference string.
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
