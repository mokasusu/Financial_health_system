"""Export utilities for financial analysis results in CSV and JSON formats (Sprint 6).

Preserves exact numerical values, metadata provenance, warning details, and AI insights.
Defensively serializes Decimal objects, Enums, and None values.
"""
import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.data.schema import FinancialReport
from src.financial.ai_models import AIInterpretationOutput, AIRiskItem, AIStrengthItem
from src.financial.assessment_models import FinancialAssessment


class CustomDataEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal, Enums, and custom objects safely."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, "value"):  # Handles Enum instances cleanly
            return obj.value
        return super().default(obj)


def export_analysis_to_json(
    assessment: FinancialAssessment,
    ai_output: Optional[AIInterpretationOutput] = None,
    report: Optional[FinancialReport] = None,
) -> str:
    """Serialize full financial assessment, ratios, and AI insights into structured JSON.

    Args:
        assessment: FinancialAssessment from Sprint 4B.
        ai_output: Optional AIInterpretationOutput from Sprint 5.
        report: Optional FinancialReport from Sprint 3.

    Returns:
        Formatted UTF-8 JSON string.
    """
    export_payload: Dict[str, Any] = {
        "metadata": {
            "company_name": assessment.company_name or "Chưa xác định",
            "fiscal_year": assessment.fiscal_year,
            "as_of_date": getattr(assessment, "as_of_date", None) or (report.as_of_date if report else None),
            "period": getattr(assessment, "period", None) or (report.period if report else None),
            "currency": assessment.currency,
            "rule_set_version": assessment.rule_set_version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "overall_health": {
            "status": assessment.overall_status.value,
            "total_ratios_evaluated": assessment.total_ratios_evaluated,
            "calculated_count": assessment.calculated_count,
            "alert_count": assessment.alert_count,
            "watch_count": assessment.watch_count,
            "category_overviews": assessment.category_overviews,
            "key_findings": assessment.key_findings,
            "limitations": assessment.limitations,
        },
        "ratios": [],
        "warnings": [],
    }

    # 1. Ratios array
    for r_key, r_eval in assessment.ratio_assessments.items():
        export_payload["ratios"].append({
            "ratio_key": r_key,
            "label": r_eval.label,
            "category": r_eval.category.value if hasattr(r_eval.category, "value") else str(r_eval.category),
            "value": float(r_eval.value) if r_eval.value is not None else None,
            "formatted_value": r_eval.formatted_value,
            "status": r_eval.status.value if hasattr(r_eval.status, "value") else str(r_eval.status),
            "explanation": r_eval.explanation,
            "rule_id": r_eval.rule_id,
            "warnings": r_eval.warnings,
            "limitations": r_eval.limitations,
        })

    # 2. Warnings array
    for w in assessment.warnings:
        export_payload["warnings"].append({
            "code": w.code,
            "category": w.category.value if hasattr(w.category, "value") else str(w.category),
            "severity": w.severity.value if hasattr(w.severity, "value") else str(w.severity),
            "title": w.title,
            "message": w.message,
            "evidence": w.evidence,
            "recommendation": w.recommendation,
            "related_ratios": w.related_ratios,
        })

    # 3. AI Interpretation (if present)
    if ai_output is not None:
        ai_strengths_clean: List[Dict[str, str]] = []
        for s in ai_output.financial_strengths:
            if isinstance(s, AIStrengthItem):
                ai_strengths_clean.append({
                    "title": s.strength_title,
                    "evidence": s.evidence,
                    "significance": s.significance,
                })
            elif isinstance(s, str):
                ai_strengths_clean.append({"title": s, "evidence": "", "significance": ""})

        ai_risks_clean: List[Dict[str, Any]] = []
        for r in ai_output.financial_risks:
            if isinstance(r, AIRiskItem):
                ai_risks_clean.append({
                    "title": r.risk_title,
                    "severity": r.severity,
                    "evidence": r.evidence,
                    "implication": r.implication,
                    "related_ratios": r.related_ratios,
                })
            elif isinstance(r, dict):
                ai_risks_clean.append(r)

        export_payload["ai_interpretation"] = {
            "is_fallback": ai_output.is_fallback,
            "fallback_reason": ai_output.fallback_reason,
            "model_used": ai_output.model_used,
            "executive_summary": ai_output.executive_summary,
            "financial_strengths": ai_strengths_clean,
            "financial_risks": ai_risks_clean,
            "recommendations": ai_output.recommendations,
            "data_limitations": ai_output.data_limitations,
            "disclaimer": ai_output.disclaimer,
        }

    # 4. Statement Validation summary (if available in report)
    if report and report.validation_results:
        vr = report.validation_results
        export_payload["statement_validation"] = {
            "is_valid": vr.is_valid,
            "total_checks": vr.total_checks,
            "passed_checks": vr.passed_checks,
            "warning_checks": vr.warning_checks,
            "failed_checks": vr.failed_checks,
            "not_checkable_checks": vr.not_checkable_checks,
            "summary": vr.summary,
        }

    return json.dumps(export_payload, cls=CustomDataEncoder, indent=2, ensure_ascii=False)


def export_ratios_to_csv(assessment: FinancialAssessment) -> str:
    """Export 14 evaluated financial ratios into a CSV string.

    Args:
        assessment: FinancialAssessment from Sprint 4B.

    Returns:
        CSV string with UTF-8 encoding.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # CSV Header
    writer.writerow([
        "Mã chỉ số",
        "Tên chỉ số",
        "Nhóm chỉ số",
        "Giá trị số",
        "Giá trị hiển thị",
        "Trạng thái đánh giá",
        "Mã quy tắc áp dụng",
        "Giải thích chi tiết",
        "Cảnh báo liên quan",
    ])

    for key, eval_item in assessment.ratio_assessments.items():
        cat_val = eval_item.category.value if hasattr(eval_item.category, "value") else str(eval_item.category)
        status_val = eval_item.status.value if hasattr(eval_item.status, "value") else str(eval_item.status)
        num_val = str(eval_item.value) if eval_item.value is not None else ""
        warnings_str = " | ".join(eval_item.warnings) if eval_item.warnings else ""

        writer.writerow([
            key,
            eval_item.label,
            cat_val,
            num_val,
            eval_item.formatted_value,
            status_val,
            eval_item.rule_id or "",
            eval_item.explanation,
            warnings_str,
        ])

    return output.getvalue()


def export_warnings_to_csv(assessment: FinancialAssessment) -> str:
    """Export prioritized risk warnings into a CSV string.

    Args:
        assessment: FinancialAssessment from Sprint 4B.

    Returns:
        CSV string with UTF-8 encoding.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    writer.writerow([
        "Mã cảnh báo",
        "Nhóm rủi ro",
        "Mức độ nghiêm trọng",
        "Tiêu đề",
        "Bằng chứng số liệu",
        "Nội dung phân tích",
        "Khuyến nghị",
        "Chỉ số liên quan",
    ])

    for w in assessment.warnings:
        cat_val = w.category.value if hasattr(w.category, "value") else str(w.category)
        sev_val = w.severity.value if hasattr(w.severity, "value") else str(w.severity)
        related = ", ".join(w.related_ratios) if w.related_ratios else ""

        writer.writerow([
            w.code,
            cat_val,
            sev_val,
            w.title,
            w.evidence,
            w.message,
            w.recommendation,
            related,
        ])

    return output.getvalue()
