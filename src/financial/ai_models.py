"""Data models for AI-powered financial interpretation (Sprint 5).

Defines structured input and output schemas for OpenRouter AI interpretation,
maintaining Decimal precision, strict provenance, and Pydantic validation.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator

from src.financial.assessment_models import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    RatioAssessment,
    WarningSeverity,
)


# =============================================================================
# INPUT MODELS (Structured data prepared for AI prompt)
# =============================================================================

class FinancialRatioInput(BaseModel):
    """Input representation of an individual financial ratio for AI context."""
    ratio_key: str = Field(description="Mã định danh tỷ số e.g. current_ratio")
    label: str = Field(description="Tên tiếng Việt của tỷ số")
    formatted_value: str = Field(description="Giá trị hiển thị kèm đơn vị e.g. 1.45 lần, 50.40%")
    value: Optional[Decimal] = Field(default=None, description="Giá trị số thực nếu có")
    status: str = Field(description="Trạng thái phân loại: ADEQUATE, WATCH, ALERT, v.v.")
    explanation: str = Field(description="Giải thích quy tắc rule-based từ Sprint 4")
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo kỹ thuật và nghiệp vụ")


class FinancialWarningInput(BaseModel):
    """Input representation of a prioritized financial warning for AI context."""
    code: str = Field(description="Mã cảnh báo e.g. LIQUIDITY_CURRENT_RATIO_WATCH")
    category: str = Field(description="Nhóm cảnh báo: liquidity, leverage, v.v.")
    severity: str = Field(description="Mức độ nghiêm trọng: critical, high, medium, low, info")
    title: str = Field(description="Tiêu đề cảnh báo ngắn gọn")
    message: str = Field(description="Nội dung cảnh báo chi tiết có căn cứ số liệu")
    evidence: str = Field(description="Căn cứ số liệu thực tế đã kích hoạt cảnh báo")
    recommendation: str = Field(description="Khuyến nghị rà soát từ rule engine")


class AIInterpretationInput(BaseModel):
    """Comprehensive input payload fed to the AI model prompt."""
    company_name: Optional[str] = Field(default=None, description="Tên doanh nghiệp")
    fiscal_year: Optional[int] = Field(default=None, description="Năm tài chính")
    currency: str = Field(default="VND", description="Đơn vị tiền tệ")
    overall_status: str = Field(description="Trạng thái sức khỏe tài chính rule-based")
    category_overviews: Dict[str, str] = Field(
        default_factory=dict, description="Nhận định theo 4 nhóm: liquidity, leverage, efficiency, profitability"
    )
    key_findings: List[str] = Field(default_factory=list, description="Phát hiện trọng yếu từ Sprint 4")
    ratios: List[FinancialRatioInput] = Field(default_factory=list, description="Danh sách 14 chỉ số tài chính")
    warnings: List[FinancialWarningInput] = Field(default_factory=list, description="Danh sách cảnh báo đã lọc trùng")
    data_limitations: List[str] = Field(default_factory=list, description="Giới hạn dữ liệu và tuyên bố miễn trừ")

    @classmethod
    def from_assessment(cls, assessment: FinancialAssessment) -> "AIInterpretationInput":
        """Factory method to construct AIInterpretationInput from Sprint 4 FinancialAssessment."""
        ratio_inputs: List[FinancialRatioInput] = []
        for key, r in assessment.ratio_assessments.items():
            ratio_inputs.append(
                FinancialRatioInput(
                    ratio_key=key,
                    label=r.label,
                    formatted_value=r.formatted_value,
                    value=r.value,
                    status=r.status.value,
                    explanation=r.explanation,
                    warnings=r.warnings,
                )
            )

        warning_inputs: List[FinancialWarningInput] = []
        for w in assessment.warnings:
            warning_inputs.append(
                FinancialWarningInput(
                    code=w.code,
                    category=w.category.value,
                    severity=w.severity.value,
                    title=w.title,
                    message=w.message,
                    evidence=w.evidence,
                    recommendation=w.recommendation,
                )
            )

        return cls(
            company_name=assessment.company_name,
            fiscal_year=assessment.fiscal_year,
            currency=assessment.currency,
            overall_status=assessment.overall_status.value,
            category_overviews=assessment.category_overviews,
            key_findings=assessment.key_findings,
            ratios=ratio_inputs,
            warnings=warning_inputs,
            data_limitations=assessment.limitations,
        )

    def to_formatted_prompt_context(self) -> str:
        """Format input into a clean, highly readable Markdown block for LLM prompt context."""
        company = self.company_name or "Doanh nghiệp (Chưa xác định tên)"
        year = str(self.fiscal_year) if self.fiscal_year else "N/A"

        lines = [
            f"### THÔNG TIN TỔNG QUAN",
            f"- Đơn vị: {company}",
            f"- Năm tài chính: {year}",
            f"- Đơn vị tiền tệ: {self.currency}",
            f"- Trạng thái sức khỏe tài chính rule-based: {self.overall_status}",
            "",
            f"### NHẬN ĐỊNH THEO NHÓM CHỈ SỐ",
        ]
        for cat, desc in self.category_overviews.items():
            lines.append(f"- **{cat.upper()}**: {desc}")

        if self.key_findings:
            lines.append("\n### PHÁT HIỆN TRỌNG YẾU (RULE ENGINE):")
            for f in self.key_findings:
                lines.append(f"- {f}")

        lines.append("\n### 14 CHỈ SỐ TÀI CHÍNH CHI TIẾT:")
        for r in self.ratios:
            lines.append(
                f"- **{r.label}** (`{r.ratio_key}`): {r.formatted_value} | Phân loại: {r.status} | {r.explanation}"
            )

        lines.append(f"\n### DANH SÁCH CẢNH BÁO RỦI RO ({len(self.warnings)} cảnh báo):")
        if not self.warnings:
            lines.append("- Không kích hoạt cảnh báo rủi ro nào theo bộ quy tắc hiện tại.")
        else:
            for w in self.warnings:
                lines.append(
                    f"- [{w.severity.upper()}] `{w.code}` ({w.category}): {w.title}. Căn cứ: {w.evidence}. Khuyến nghị: {w.recommendation}"
                )

        if self.data_limitations:
            lines.append("\n### GIỚI HẠN DỮ LIỆU:")
            for lim in self.data_limitations:
                lines.append(f"- {lim}")

        return "\n".join(lines)


# =============================================================================
# OUTPUT MODELS (Structured AI response validated with Pydantic)
# =============================================================================

class AIRiskItem(BaseModel):
    """Structured risk item identified by the AI model with evidence link."""
    risk_title: str = Field(description="Tiêu đề rủi ro tài chính")
    severity: str = Field(default="medium", description="Mức độ rủi ro: critical, high, medium, low")
    evidence: str = Field(default="", description="Căn cứ số liệu hoặc chỉ số từ báo cáo tài chính")
    implication: str = Field(default="", description="Tác động tiềm ẩn đối với hoạt động và an toàn tài chính")
    related_ratios: List[str] = Field(default_factory=list, description="Danh sách mã ratio_key liên quan")


class AIStrengthItem(BaseModel):
    """Structured strength item identified by the AI model with evidence link."""
    strength_title: str = Field(description="Điểm mạnh tài chính nổi bật")
    evidence: str = Field(default="", description="Căn cứ số liệu chứng minh từ BCTC")
    significance: str = Field(default="", description="Ý nghĩa đối với năng lực cạnh tranh hoặc an toàn vốn")


class AIInterpretationOutput(BaseModel):
    """Structured output schema returned by the AI Financial Interpreter."""
    executive_summary: str = Field(
        description="Tóm tắt điều hành bằng tiếng Việt chuyên nghiệp về sức khỏe tài chính toàn diện"
    )
    financial_strengths: List[Union[AIStrengthItem, str]] = Field(
        default_factory=list, description="Các điểm mạnh tài chính có căn cứ từ dữ liệu"
    )
    financial_risks: List[AIRiskItem] = Field(
        default_factory=list, description="Các rủi ro tài chính trọng yếu có căn cứ và đánh giá mức độ"
    )
    ratio_explanations: Dict[str, str] = Field(
        default_factory=dict,
        description="Giải thích chi tiết ngữ cảnh kinh tế cho các tỷ số tài chính (key là ratio_key)",
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Khuyến nghị hành động tiếp theo thiết thực, tương xứng với bằng chứng"
    )
    data_limitations: List[str] = Field(
        default_factory=list,
        description="Các hạn chế và lưu ý thận trọng (tính mùa vụ, dữ liệu 1 kỳ, chưa có benchmark ngành)",
    )
    disclaimer: str = Field(
        default=(
            "Báo cáo phân tích này được hỗ trợ tạo bởi trí tuệ nhân tạo (AI) dựa trên số liệu báo cáo tài chính được trích xuất. "
            "Kết quả mang tính chất tham khảo phân tích thông tin, không cấu thành lời khuyên đầu tư, khuyến nghị cấp tín dụng "
            "hay ý kiến kiểm toán chính thức. Người đọc cần tự chịu trách nhiệm khi đưa ra các quyết định kinh doanh hoặc tài chính."
        ),
        description="Tuyên bố miễn trừ trách nhiệm pháp lý",
    )
    is_fallback: bool = Field(
        default=False,
        description="Đánh dấu nội dung được tạo bởi cơ chế deterministic fallback khi API gặp sự cố",
    )
    fallback_reason: Optional[str] = Field(
        default=None, description="Lý do kích hoạt fallback (ví dụ lỗi mạng, timeout, rate limit)"
    )
    model_used: Optional[str] = Field(
        default=None, description="Tên định danh model AI đã thực hiện phân tích (e.g. google/gemma-4-31b-it:free)"
    )
    usage: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata sử dụng token và thời gian phản hồi"
    )

    @field_validator("financial_risks", mode="before")
    @classmethod
    def _coerce_financial_risks(cls, v: Any) -> Any:
        """Handle LLM variability: Convert plain string risks into AIRiskItem objects cleanly."""
        if not isinstance(v, list):
            return v
        coerced: List[Any] = []
        for item in v:
            if isinstance(item, str):
                coerced.append(
                    AIRiskItem(
                        risk_title=item,
                        severity="medium",
                        evidence="Căn cứ từ số liệu BCTC và cảnh báo của hệ thống",
                        implication="Cần theo dõi và rà soát biến động tài chính liên quan",
                    )
                )
            elif isinstance(item, dict):
                # Ensure all required fields exist or have defaults
                title = item.get("risk_title") or item.get("title") or item.get("name") or "Rủi ro tài chính"
                coerced.append(
                    AIRiskItem(
                        risk_title=title,
                        severity=item.get("severity", "medium"),
                        evidence=item.get("evidence", ""),
                        implication=item.get("implication", item.get("message", "")),
                        related_ratios=item.get("related_ratios", []),
                    )
                )
            else:
                coerced.append(item)
        return coerced
