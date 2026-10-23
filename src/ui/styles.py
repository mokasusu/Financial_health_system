"""UI Styles and Design System for Financial Health Dashboard (Sprint 6).

Implements professional financial analytics dashboard styling:
- Primary emerald green theme (#006c49)
- Clean white cards, subtle shadows, and crisp borders
- Semantic color badges for risk and assessment statuses
- Compact, legible typography and responsive layout
"""
from typing import Optional
import streamlit as st


# Color Palette Constants
COLOR_PRIMARY_EMERALD = "#006c49"
COLOR_PRIMARY_DARK = "#004d34"
COLOR_PRIMARY_LIGHT = "#e6f4ef"

# Status Semantic Colors
STATUS_COLORS = {
    "adequate": {"bg": "#ecfdf5", "text": "#065f46", "border": "#a7f3d0", "label": "AN TOÀN"},
    "watch": {"bg": "#fffbeb", "text": "#92400e", "border": "#fde68a", "label": "THEO DÕI"},
    "alert": {"bg": "#fef2f2", "text": "#991b1b", "border": "#fecaca", "label": "CẢNH BÁO"},
    "no_benchmark": {"bg": "#eff6ff", "text": "#1e40af", "border": "#bfdbfe", "label": "CẦN BENCHMARK"},
    "not_available": {"bg": "#f1f5f9", "text": "#475569", "border": "#cbd5e1", "label": "THIẾU DỮ LIỆU"},
    "not_applicable": {"bg": "#f8fafc", "text": "#64748b", "border": "#e2e8f0", "label": "KHÔNG ÁP DỤNG"},
    "undefined": {"bg": "#faf5ff", "text": "#6b21a8", "border": "#e9d5ff", "label": "KHÔNG XÁC ĐỊNH"},
}

SEVERITY_COLORS = {
    "critical": {"bg": "#7f1d1d", "text": "#ffffff", "border": "#991b1b", "label": "NGHIÊM TRỌNG"},
    "high": {"bg": "#dc2626", "text": "#ffffff", "border": "#b91c1c", "label": "CAO"},
    "medium": {"bg": "#f59e0b", "text": "#ffffff", "border": "#d97706", "label": "TRUNG BÌNH"},
    "low": {"bg": "#3b82f6", "text": "#ffffff", "border": "#2563eb", "label": "THẤP"},
    "info": {"bg": "#64748b", "text": "#ffffff", "border": "#475569", "label": "THÔNG TIN"},
}

OVERALL_HEALTH_STYLES = {
    "insufficient_data": {
        "title": "Chưa đủ dữ liệu kết luận",
        "bg": "#f1f5f9",
        "text": "#475569",
        "border": "#cbd5e1",
        "icon": "⚠️",
    },
    "needs_attention": {
        "title": "Cần lưu ý đặc biệt",
        "bg": "#fef2f2",
        "text": "#991b1b",
        "border": "#fca5a5",
        "icon": "🚨",
    },
    "mixed": {
        "title": "Tín hiệu đan xen / Theo dõi",
        "bg": "#fffbeb",
        "text": "#92400e",
        "border": "#fde68a",
        "icon": "⚖️",
    },
    "no_major_rule_based_alerts": {
        "title": "Không có cảnh báo rủi ro trọng yếu",
        "bg": "#ecfdf5",
        "text": "#065f46",
        "border": "#6ee7b7",
        "icon": "✅",
    },
}

CUSTOM_CSS = """
<style>
/* Main Page Font & Baseline */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Emerald green primary accents for Streamlit controls */
:root {
    --primary-color: #006c49;
    --primary-hover: #00563a;
}

/* Main title styling */
h1, h2, h3, h4 {
    color: #0f172a;
    font-weight: 600;
}

/* Dashboard Header Card */
.dashboard-header {
    background: linear-gradient(135deg, #006c49 0%, #004d34 100%);
    color: #ffffff;
    padding: 1.5rem 1.75rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 12px rgba(0, 108, 73, 0.15);
}

.dashboard-header h1 {
    color: #ffffff !important;
    margin: 0 0 0.5rem 0;
    font-size: 1.65rem;
    font-weight: 700;
}

.dashboard-header p {
    color: #e6f4ef !important;
    margin: 0;
    font-size: 0.95rem;
}

.dashboard-header .meta-tag {
    display: inline-block;
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    margin-right: 0.5rem;
    margin-top: 0.5rem;
}

/* White Card Containers */
.fhs-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.fhs-card-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-bottom: 1px solid #f1f5f9;
    padding-bottom: 0.5rem;
}

/* KPI Stat Cards */
.kpi-card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.1rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    height: 100%;
}

.kpi-card:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.08);
}

.kpi-label {
    font-size: 0.825rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 0.4rem;
}

.kpi-value {
    font-size: 1.85rem;
    font-weight: 700;
    color: #006c49;
    line-height: 1.2;
    margin-bottom: 0.35rem;
}

.kpi-subtext {
    font-size: 0.8rem;
    color: #64748b;
}

/* Badges */
.status-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.025em;
    border-width: 1px;
    border-style: solid;
}

.severity-badge {
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Warning & Alert Callouts */
.warning-item {
    border-left: 4px solid #f59e0b;
    background-color: #fffbeb;
    padding: 0.85rem 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.75rem;
}

.warning-item.critical, .warning-item.high {
    border-left-color: #dc2626;
    background-color: #fef2f2;
}

.warning-item.medium {
    border-left-color: #f59e0b;
    background-color: #fffbeb;
}

.warning-item.low {
    border-left-color: #3b82f6;
    background-color: #eff6ff;
}

.warning-item.info {
    border-left-color: #64748b;
    background-color: #f8fafc;
}

.warning-title {
    font-weight: 600;
    color: #0f172a;
    font-size: 0.95rem;
    margin-bottom: 0.25rem;
}

.warning-evidence {
    font-size: 0.85rem;
    color: #475569;
    margin-bottom: 0.25rem;
}

.warning-rec {
    font-size: 0.85rem;
    color: #006c49;
    font-weight: 500;
}

/* AI Interpretation Box */
.ai-box {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}

.ai-badge {
    display: inline-block;
    background-color: #006c49;
    color: #ffffff;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}

.ai-fallback-badge {
    display: inline-block;
    background-color: #d97706;
    color: #ffffff;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}

/* Disclaimer text */
.disclaimer-box {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 1rem;
    font-style: italic;
}
</style>
"""


def apply_custom_styles() -> None:
    """Inject custom CSS rules into the Streamlit app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def get_status_badge_html(status: str, custom_text: Optional[str] = None) -> str:
    """Return an HTML chip for an individual ratio AssessmentStatus."""
    norm_status = status.lower() if status else "undefined"
    style = STATUS_COLORS.get(norm_status, STATUS_COLORS["undefined"])
    label = custom_text or style["label"]
    return (
        f'<span class="status-badge" style="background-color: {style["bg"]}; '
        f'color: {style["text"]}; border-color: {style["border"]};">'
        f'{label}</span>'
    )


def get_severity_badge_html(severity: str) -> str:
    """Return an HTML badge for a warning severity priority."""
    norm_sev = severity.lower() if severity else "info"
    style = SEVERITY_COLORS.get(norm_sev, SEVERITY_COLORS["info"])
    return (
        f'<span class="severity-badge" style="background-color: {style["bg"]}; '
        f'color: {style["text"]}; border-color: {style["border"]};">'
        f'{style["label"]}</span>'
    )


def get_overall_health_banner_html(overall_status_val: str) -> str:
    """Return a prominent HTML hero box for the synthesized financial health status."""
    norm_val = overall_status_val.lower() if overall_status_val else "insufficient_data"
    style = OVERALL_HEALTH_STYLES.get(norm_val, OVERALL_HEALTH_STYLES["insufficient_data"])
    return (
        f'<div style="background-color: {style["bg"]}; border: 1.5px solid {style["border"]}; '
        f'border-radius: 10px; padding: 1.1rem 1.3rem; margin-bottom: 1.25rem;">'
        f'<div style="font-size: 1.15rem; font-weight: 700; color: {style["text"]}; '
        f'display: flex; align-items: center; gap: 0.5rem;">'
        f'<span>{style["icon"]}</span><span>{style["title"]}</span>'
        f'</div>'
        f'<div style="font-size: 0.875rem; color: #475569; margin-top: 0.35rem;">'
        f'Đánh giá rule-based từ 14 chỉ số tài chính theo các ngưỡng sàng lọc minh họa.'
        f'</div>'
        f'</div>'
    )
