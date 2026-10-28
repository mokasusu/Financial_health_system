"""Mô hình dữ liệu nhận định tài chính thông minh bằng Trí tuệ nhân tạo (AI Financial Commentary).

Module này định nghĩa các cấu trúc dữ liệu đầu vào (Prompt Context) và đầu ra (Interpretation Output)
cho AI Financial Interpreter, tập trung phân tích sâu 4 chỉ số tài chính cốt lõi:
1. Current Ratio (Khả năng thanh toán hiện hành)
2. Debt to Equity (Hệ số Nợ / Vốn chủ sở hữu)
3. ROA (Tỷ suất sinh lời trên tổng tài sản)
4. ROE (Tỷ suất sinh lời trên vốn chủ sở hữu)

Tuân thủ nguyên tắc không sử dụng nhận định soạn sẵn (Zero Canned Commentary) và hỗ trợ
tự động chuẩn hóa cấu trúc dữ liệu trả về từ các mô hình AI mã nguồn mở (Pydantic Validators).
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.models.assessment import (
    FinancialAssessment,
    FinancialWarning,
    RatioAssessment,
)


class CoreKPIData(BaseModel):
    """Cấu trúc dữ liệu đại diện cho 1 trong 4 chỉ số tài chính cốt lõi đưa vào Prompt AI.

    Attributes:
        key (str): Mã định danh chỉ số ('current_ratio', 'debt_to_equity', 'roa', 'roe').
        name (str): Tên tiếng Việt chính thức của chỉ số.
        formula (str): Công thức toán học kế toán minh bạch.
        formatted_value (str): Giá trị tính toán thực tế kèm đơn vị (VD: '1.45 lần', '18.20%').
        value (Optional[Decimal]): Giá trị số học Decimal chính xác.
        safe_benchmark (str): Ngưỡng tham chiếu thị trường để AI đối chiếu phân tích.
    """
    key: str = Field(description="Mã chỉ số e.g. current_ratio, debt_to_equity, roa, roe")
    name: str = Field(description="Tên tiếng Việt chuẩn của chỉ số")
    formula: str = Field(description="Công thức tính toán")
    formatted_value: str = Field(description="Giá trị tính toán kèm đơn vị")
    value: Optional[Decimal] = Field(default=None, description="Giá trị số thực nếu có")
    safe_benchmark: str = Field(description="Ngưỡng tham chiếu thị trường minh họa")


class FinancialRatioInput(BaseModel):
    """Biểu diễn dữ liệu của một chỉ số tài chính đơn lẻ trong ngữ cảnh AI."""
    ratio_key: str = Field(description="Mã định danh tỷ số e.g. current_ratio")
    label: str = Field(description="Tên tiếng Việt của tỷ số")
    formatted_value: str = Field(description="Giá trị hiển thị kèm đơn vị e.g. 1.45 lần, 50.40%")
    value: Optional[Decimal] = Field(default=None, description="Giá trị số thực nếu có")
    status: str = Field(default="CALCULATED", description="Trạng thái phân loại")
    explanation: str = Field(default="", description="Giải thích ngắn")
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo kỹ thuật và nghiệp vụ")


class FinancialWarningInput(BaseModel):
    """Biểu diễn dữ liệu cảnh báo rủi ro đưa vào ngữ cảnh AI."""
    code: str = Field(description="Mã cảnh báo")
    category: str = Field(description="Nhóm cảnh báo")
    severity: str = Field(description="Mức độ nghiêm trọng: critical, high, medium, low, info")
    title: str = Field(description="Tiêu đề cảnh báo ngắn gọn")
    message: str = Field(description="Nội dung cảnh báo chi tiết có căn cứ số liệu")
    evidence: str = Field(description="Căn cứ số liệu thực tế")
    recommendation: str = Field(description="Khuyến nghị")


# Danh mục định nghĩa và ngưỡng chuẩn của 4 chỉ số tài chính cốt lõi
CORE_4_KPI_DEFINITIONS = [
    {
        "key": "current_ratio",
        "name": "Khả năng thanh toán hiện hành (Current Ratio)",
        "formula": "Tài sản ngắn hạn / Nợ ngắn hạn",
        "safe_benchmark": "An toàn: ≥ 1.5 lần | Cần theo dõi: 1.0 - 1.5 lần | Nguy hiểm: < 1.0 lần",
    },
    {
        "key": "debt_to_equity",
        "name": "Hệ số Nợ / Vốn chủ sở hữu (Debt to Equity)",
        "formula": "Nợ phải trả / Vốn chủ sở hữu",
        "safe_benchmark": "An toàn: ≤ 1.0 lần | Cần theo dõi: 1.0 - 2.0 lần | Nguy hiểm: > 2.0 lần (hoặc VCSH âm)",
    },
    {
        "key": "roa",
        "name": "Tỷ suất sinh lời trên Tổng tài sản (ROA)",
        "formula": "Lợi nhuận sau thuế / Tổng tài sản",
        "safe_benchmark": "An toàn: ≥ 5.0% | Cần theo dõi: 0% - 5.0% | Nguy hiểm: < 0%",
    },
    {
        "key": "roe",
        "name": "Tỷ suất sinh lời trên Vốn chủ sở hữu (ROE)",
        "formula": "Lợi nhuận sau thuế / Vốn chủ sở hữu",
        "safe_benchmark": "An toàn: ≥ 12.0% | Cần theo dõi: 0% - 12.0% | Nguy hiểm: < 0% (hoặc VCSH âm)",
    },
]


class AIInterpretationInput(BaseModel):
    """Payload dữ liệu đầu vào cung cấp cho mô hình AI qua Prompt chuyên gia phân tích.

    Tập trung vào 4 chỉ số cốt lõi kết hợp thông tin doanh nghiệp và niên độ tài chính.
    """
    company_name: Optional[str] = Field(default=None, description="Tên doanh nghiệp")
    fiscal_year: Optional[int] = Field(default=None, description="Năm tài chính")
    as_of_date: Optional[str] = Field(default=None, description="Ngày khóa sổ/thời điểm BCTC")
    currency: str = Field(default="VND", description="Đơn vị tiền tệ")
    kpis: List[CoreKPIData] = Field(default_factory=list, description="Danh sách 4 chỉ số tài chính cốt lõi")
    
    # Các trường mở rộng duy trì tính tương thích ngược
    overall_status: Optional[str] = Field(default=None)
    category_overviews: Dict[str, str] = Field(default_factory=dict)
    key_findings: List[str] = Field(default_factory=list)
    ratios: List[FinancialRatioInput] = Field(default_factory=list)
    warnings: List[FinancialWarningInput] = Field(default_factory=list)
    data_limitations: List[str] = Field(default_factory=list)

    @classmethod
    def from_4_core_kpis(
        cls,
        assessment: FinancialAssessment,
        ratio_report: Optional[Any] = None,
    ) -> "AIInterpretationInput":
        """Khởi tạo đối tượng input cho AI chỉ dựa trên 4 chỉ số cốt lõi mà không dùng văn mẫu.

        Args:
            assessment (FinancialAssessment): Kết quả đánh giá phân loại rủi ro.
            ratio_report (Optional[Any]): Báo cáo tỷ số tài chính gốc chứa giá trị Decimal.

        Returns:
            AIInterpretationInput: Đối tượng đầu vào tinh gọn sẵn sàng dựng prompt.
        """
        kpi_list: List[CoreKPIData] = []

        for spec in CORE_4_KPI_DEFINITIONS:
            key = spec["key"]
            val_str = "N/A"
            val_num: Optional[Decimal] = None

            # 1. Ưu tiên trích xuất trực tiếp từ ratio_report
            if ratio_report is not None and hasattr(ratio_report, "get_ratio"):
                r_res = ratio_report.get_ratio(key)
                if r_res is not None:
                    if getattr(r_res, "status", None) and str(r_res.status).upper() == "UNDEFINED":
                        val_str = "VCSH ÂM (Không xác định)"
                    elif r_res.value is not None:
                        val_str = r_res.formatted_value
                        val_num = r_res.value

            # 2. Nếu chưa có, trích xuất từ assessment.ratio_assessments
            if val_str == "N/A" and assessment and assessment.ratio_assessments:
                r_ass = assessment.ratio_assessments.get(key)
                if r_ass is not None:
                    if getattr(r_ass, "status", None) and str(getattr(r_ass.status, "value", r_ass.status)).upper() == "UNDEFINED":
                        val_str = "VCSH ÂM (Không xác định)"
                    elif r_ass.value is not None:
                        val_str = r_ass.formatted_value
                        val_num = r_ass.value

            kpi_list.append(
                CoreKPIData(
                    key=key,
                    name=spec["name"],
                    formula=spec["formula"],
                    formatted_value=val_str,
                    value=val_num,
                    safe_benchmark=spec["safe_benchmark"],
                )
            )

        return cls(
            company_name=assessment.company_name,
            fiscal_year=assessment.fiscal_year,
            as_of_date=getattr(assessment, "as_of_date", None),
            currency=assessment.currency or "VND",
            kpis=kpi_list,
            data_limitations=list(assessment.limitations) if assessment.limitations else [],
        )

    @classmethod
    def from_assessment(cls, assessment: FinancialAssessment) -> "AIInterpretationInput":
        """Factory method hỗ trợ tương thích ngược, tự động trích xuất 4 chỉ số cốt lõi.

        Args:
            assessment (FinancialAssessment): Báo cáo đánh giá tài chính tổng thể.

        Returns:
            AIInterpretationInput: Đối tượng đầu vào AI.
        """
        obj = cls.from_4_core_kpis(assessment=assessment)
        obj.overall_status = getattr(assessment.overall_status, "value", str(assessment.overall_status))
        obj.category_overviews = assessment.category_overviews
        obj.key_findings = assessment.key_findings
        obj.data_limitations = assessment.limitations

        ratio_inputs: List[FinancialRatioInput] = []
        for key, r in assessment.ratio_assessments.items():
            ratio_inputs.append(
                FinancialRatioInput(
                    ratio_key=key,
                    label=r.label,
                    formatted_value=r.formatted_value,
                    value=r.value,
                    status=getattr(r.status, "value", str(r.status)),
                    explanation=r.explanation,
                    warnings=r.warnings,
                )
            )
        obj.ratios = ratio_inputs
        return obj

    def to_formatted_prompt_context(self) -> str:
        """Định dạng dữ liệu đầu vào thành văn bản Markdown chuyên nghiệp cho LLM System Prompt.

        Returns:
            str: Khối ngữ cảnh gồm thông tin doanh nghiệp, bảng số liệu 4 chỉ số và yêu cầu phân tích.
        """
        company = self.company_name or "Doanh nghiệp (Chưa xác định tên)"
        year = str(self.fiscal_year) if self.fiscal_year else "N/A"
        date_str = f"Tại ngày {self.as_of_date}" if self.as_of_date else (f"Năm {year}" if year != "N/A" else "N/A")

        lines = [
            "### 1. THÔNG TIN DOANH NGHIỆP:",
            f"- Đơn vị: {company}",
            f"- Thời điểm/Kỳ báo cáo: {date_str}",
            f"- Năm tài chính: {year}",
            f"- Đơn vị tiền tệ: {self.currency}",
            "",
            "### 2. DỮ LIỆU 4 CHỈ SỐ TÀI CHÍNH CỐT LÕI (DO PYTHON TÍNH TOÁN):",
        ]

        if self.kpis:
            for idx, kpi in enumerate(self.kpis, start=1):
                lines.extend([
                    f"{idx}. **{kpi.name}** (`{kpi.key}`):",
                    f"   - Công thức: {kpi.formula}",
                    f"   - Giá trị tính toán thực tế: **{kpi.formatted_value}**",
                    f"   - Ngưỡng tham chiếu thị trường: {kpi.safe_benchmark}",
                    "",
                ])
        elif self.ratios:
            for idx, r in enumerate(self.ratios[:4], start=1):
                lines.append(f"{idx}. **{r.label}** (`{r.ratio_key}`): {r.formatted_value}")
            lines.append("")

        lines.extend([
            "### 3. YÊU CẦU PHÂN TÍCH & NHẬN ĐỊNH TỪ CHUYÊN GIA AI:",
            "- Hãy phân tích độc lập, khách quan và chuyên sâu bản chất sức khỏe tài chính của doanh nghiệp dựa trên 4 chỉ số trên.",
            "- Đánh giá mối quan hệ tương hỗ: khả năng thanh toán ngắn hạn, đòn bẩy rủi ro tài chính và hiệu quả sinh lời (ROA/ROE).",
            "- Tuyệt đối không dùng văn mẫu có sẵn hay câu chữ sáo rỗng. Nhận định phải sắc bén và đưa ra khuyến nghị thực tế cho ban lãnh đạo.",
        ])

        return "\n".join(lines)


class AIRiskItem(BaseModel):
    """Mô hình đại diện cho một rủi ro tài chính do AI phát hiện có bằng chứng số liệu.

    Attributes:
        risk_title (str): Tiêu đề ngắn gọn của rủi ro.
        severity (str): Mức độ rủi ro ('critical', 'high', 'medium', 'low').
        evidence (str): Căn cứ số liệu hoặc chỉ số cụ thể từ BCTC.
        implication (str): Tác động tiêu cực tiềm tàng đến an toàn tài chính hoặc hoạt động kinh doanh.
        related_ratios (List[str]): Danh sách các chỉ số tài chính liên quan.
    """
    risk_title: str = Field(description="Tiêu đề rủi ro tài chính")
    severity: str = Field(default="medium", description="Mức độ rủi ro: critical, high, medium, low")
    evidence: str = Field(default="", description="Căn cứ số liệu hoặc chỉ số từ báo cáo tài chính")
    implication: str = Field(default="", description="Tác động tiềm ẩn đối với hoạt động và an toàn tài chính")
    related_ratios: List[str] = Field(default_factory=list, description="Danh sách mã ratio_key liên quan")


class AIStrengthItem(BaseModel):
    """Mô hình đại diện cho một điểm mạnh tài chính do AI phát hiện.

    Attributes:
        strength_title (str): Tiêu đề điểm mạnh tài chính.
        evidence (str): Căn cứ số liệu chứng minh từ BCTC.
        significance (str): Ý nghĩa đối với năng lực cạnh tranh hoặc khả năng tự chủ tài chính.
    """
    strength_title: str = Field(description="Điểm mạnh tài chính nổi bật")
    evidence: str = Field(default="", description="Căn cứ số liệu chứng minh từ BCTC")
    significance: str = Field(default="", description="Ý nghĩa đối với năng lực cạnh tranh hoặc an toàn vốn")


class AIInterpretationOutput(BaseModel):
    """Cấu trúc dữ liệu đầu ra JSON chuẩn hóa của chuyên gia phân tích tài chính AI.

    Chứa báo cáo điều hành tổng quan, các điểm mạnh, rủi ro, phân tích chi tiết từng chỉ số
    và các khuyến nghị hành động chiến lược thiết thực.
    """
    executive_summary: str = Field(
        description="Tóm tắt điều hành bằng tiếng Việt chuyên nghiệp về sức khỏe tài chính toàn diện dựa trên 4 chỉ số cốt lõi"
    )
    financial_strengths: List[Union[AIStrengthItem, str]] = Field(
        default_factory=list, description="Các điểm mạnh tài chính có căn cứ từ dữ liệu 4 chỉ số"
    )
    financial_risks: List[AIRiskItem] = Field(
        default_factory=list, description="Các rủi ro tài chính trọng yếu có căn cứ và đánh giá mức độ"
    )
    ratio_explanations: Dict[str, str] = Field(
        default_factory=dict,
        description="Giải thích và nhận định chuyên sâu cho từng chỉ số trong 4 chỉ số (key: current_ratio, debt_to_equity, roa, roe)",
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Khuyến nghị hành động chiến lược thiết thực cho ban điều hành"
    )
    data_limitations: List[str] = Field(
        default_factory=list,
        description="Các hạn chế và lưu ý thận trọng (tính mùa vụ, dữ liệu 1 kỳ, chưa có benchmark ngành)",
    )
    disclaimer: str = Field(
        default=(
            "Báo cáo phân tích này được thực hiện bởi trí tuệ nhân tạo (AI) dựa trên 4 chỉ số tài chính cốt lõi được trích xuất. "
            "Kết quả mang tính chất tham khảo phân tích thông tin, không cấu thành lời khuyên đầu tư, khuyến nghị cấp tín dụng "
            "hay ý kiến kiểm toán chính thức. Người đọc cần tự chịu trách nhiệm khi đưa ra các quyết định kinh doanh hoặc tài chính."
        ),
        description="Tuyên bố miễn trừ trách nhiệm pháp lý",
    )
    is_fallback: bool = Field(
        default=False,
        description="Đánh dấu nội dung được tạo bởi cơ chế dự phòng khi API gặp sự cố",
    )
    fallback_reason: Optional[str] = Field(
        default=None, description="Lý do kích hoạt fallback (ví dụ lỗi mạng, timeout, rate limit)"
    )
    model_used: Optional[str] = Field(
        default=None, description="Tên định danh model AI đã thực hiện phân tích"
    )
    usage: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata sử dụng token và thời gian phản hồi"
    )

    @model_validator(mode="before")
    @classmethod
    def _remap_kpi_deep_dive(cls, data: Any) -> Any:
        """Tự động ánh xạ khóa four_kpi_deep_dive sang ratio_explanations nếu LLM trả về tên cũ."""
        if isinstance(data, dict):
            if "four_kpi_deep_dive" in data and not data.get("ratio_explanations"):
                data["ratio_explanations"] = data["four_kpi_deep_dive"]
        return data

    @field_validator("ratio_explanations", mode="before")
    @classmethod
    def _coerce_ratio_explanations(cls, v: Any) -> Any:
        """Đảm bảo ratio_explanations luôn là một dictionary hợp lệ."""
        if isinstance(v, dict):
            return v
        return {}

    @field_validator("financial_risks", mode="before")
    @classmethod
    def _coerce_financial_risks(cls, v: Any) -> Any:
        """Chuẩn hóa dữ liệu rủi ro: Chuyển đổi các chuỗi thuần thành đối tượng AIRiskItem hoàn chỉnh."""
        if not isinstance(v, list):
            return v
        coerced: List[Any] = []
        for item in v:
            if isinstance(item, str):
                coerced.append(
                    AIRiskItem(
                        risk_title=item,
                        severity="medium",
                        evidence="Căn cứ từ số liệu 4 chỉ số tài chính",
                        implication="Cần theo dõi và rà soát biến động tài chính liên quan",
                    )
                )
            elif isinstance(item, dict):
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
