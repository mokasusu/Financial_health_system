"""Dịch vụ xuất khẩu dữ liệu kết quả phân tích tài chính định dạng CSV và JSON.

Module này cung cấp các phương thức chuyển đổi dữ liệu đánh giá tài chính,
danh sách 14 chỉ số, cảnh báo rủi ro, kết quả kiểm tra cân đối kế toán TT200
và nhận định từ AI thành các tệp JSON có cấu trúc phân tầng và CSV hỗ trợ hiển thị Tiếng Việt.
"""
import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
from typing import Any, Dict, List, Optional

from src.domain.models.ai import AIInterpretationOutput, AIRiskItem, AIStrengthItem
from src.domain.models.assessment import FinancialAssessment
from src.domain.models.bctc import FinancialReport


class CustomDataEncoder(json.JSONEncoder):
    """Trình mã hóa JSON tùy biến xử lý an toàn kiểu Decimal, Enum và các đối tượng tùy chỉnh."""

    def default(self, obj: Any) -> Any:
        """Chuyển đổi kiểu dữ liệu đặc biệt sang kiểu dữ liệu JSON nguyên bản.

        Args:
            obj (Any): Đối tượng cần mã hóa.

        Returns:
            Any: Giá trị float (với Decimal) hoặc chuỗi (với Enum).
        """
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, "value"):
            return obj.value
        return super().default(obj)


class ExportService:
    """Dịch vụ xuất khẩu kết quả đánh giá sức khỏe tài chính, chỉ số, cảnh báo và nhận định AI."""

    @staticmethod
    def to_json(
        assessment: FinancialAssessment,
        ai_output: Optional[AIInterpretationOutput] = None,
        report: Optional[FinancialReport] = None,
    ) -> str:
        """Tuần tự hóa toàn bộ kết quả phân tích, chỉ số và nhận định AI thành chuỗi JSON có cấu trúc.

        Args:
            assessment (FinancialAssessment): Đánh giá sức khỏe tài chính và tỷ số.
            ai_output (Optional[AIInterpretationOutput]): Kết quả diễn giải từ AI (nếu có).
            report (Optional[FinancialReport]): Báo cáo tài chính gốc kèm kết quả cân đối TT200 (nếu có).

        Returns:
            str: Chuỗi ký tự định dạng JSON thụt lề 2 khoảng trắng, mã hóa UTF-8 đầy đủ.
        """
        # Cấu trúc dữ liệu xuất khẩu tổng thể
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

        # 1. Danh sách chi tiết các chỉ số tài chính
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

        # 2. Danh sách cảnh báo rủi ro được ưu tiên
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

        # 3. Thông tin diễn giải từ AI (nếu có)
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

        # 4. Tóm tắt kết quả kiểm tra cân đối kế toán TT200 (nếu có)
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

    @staticmethod
    def ratios_to_csv(assessment: FinancialAssessment) -> str:
        """Xuất danh sách 14 chỉ số tài chính thành chuỗi CSV với tiêu đề Tiếng Việt.

        Args:
            assessment (FinancialAssessment): Kết quả đánh giá tài chính.

        Returns:
            str: Chuỗi văn bản định dạng CSV.
        """
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

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

    @staticmethod
    def warnings_to_csv(assessment: FinancialAssessment) -> str:
        """Xuất danh sách các cảnh báo rủi ro thành chuỗi CSV với tiêu đề Tiếng Việt.

        Args:
            assessment (FinancialAssessment): Kết quả đánh giá tài chính.

        Returns:
            str: Chuỗi văn bản định dạng CSV.
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


# Xuất các hàm cấp module tương thích ngược
export_analysis_to_json = ExportService.to_json
export_ratios_to_csv = ExportService.ratios_to_csv
export_warnings_to_csv = ExportService.warnings_to_csv
