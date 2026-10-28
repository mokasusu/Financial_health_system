"""Gói các thành phần giao diện người dùng (Presentation Components).

Cung cấp các khối hiển thị và tương tác người dùng chuyên biệt cho Streamlit:
- top_bar: render_header, render_top_action_bar.
- kpi_cards: render_core_4_kpi_cards, _evaluate_kpi_visual.
- balance_checks: render_health_assessment, render_ratio_matrix, render_ratio_analysis.
- statement_tables: render_financial_statements, build_statement_dataframes, apply_edits_to_report.
- ai_commentary: render_ai_interpretation.
- export_panel: render_export_section.
"""
from src.presentation.components.top_bar import render_header, render_top_action_bar
from src.presentation.components.kpi_cards import (
    render_core_4_kpi_cards,
    _evaluate_kpi_visual,
    _get_badge_text_color,
)
from src.presentation.components.balance_checks import (
    render_health_assessment,
    render_ratio_matrix,
    render_ratio_analysis,
    RATIO_BENCHMARKS,
)
from src.presentation.components.statement_tables import (
    CANONICAL_VIETNAMESE_NAMES,
    apply_edits_to_report,
    build_statement_dataframes,
    format_cell_number,
    get_statement_column_names,
    parse_cell_to_decimal,
    render_financial_statements,
    _extract_row_period_values,
)
from src.presentation.components.ai_commentary import render_ai_interpretation
from src.presentation.components.export_panel import render_export_section

__all__ = [
    "render_header",
    "render_top_action_bar",
    "render_core_4_kpi_cards",
    "_evaluate_kpi_visual",
    "_get_badge_text_color",
    "render_health_assessment",
    "render_ratio_matrix",
    "render_ratio_analysis",
    "RATIO_BENCHMARKS",
    "CANONICAL_VIETNAMESE_NAMES",
    "apply_edits_to_report",
    "build_statement_dataframes",
    "format_cell_number",
    "get_statement_column_names",
    "parse_cell_to_decimal",
    "render_financial_statements",
    "_extract_row_period_values",
    "render_ai_interpretation",
    "render_export_section",
]
