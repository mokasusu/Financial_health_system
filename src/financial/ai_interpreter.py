"""AI Financial Interpretation Orchestrator (Sprint 5).

Builds Vietnamese financial prompts, manages OpenRouter LLM interactions,
extracts and validates Pydantic structured output, enforces numerical grounding,
and provides deterministic rule-based fallback when the API is unavailable.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.financial.ai_models import (
    AIInterpretationInput,
    AIInterpretationOutput,
    AIRiskItem,
    AIStrengthItem,
)
from src.financial.assessment_models import (
    AssessmentStatus,
    FinancialAssessment,
    WarningSeverity,
)
from src.financial.openrouter_client import (
    ConfigurationError,
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
    ResponseValidationError,
)
from src.financial.ratios import RATIO_METADATA

logger = logging.getLogger(__name__)

# Valid canonical ratio keys from Sprint 4A
CANONICAL_RATIO_KEYS = set(RATIO_METADATA.keys())

# System prompt designed for analytical AI via OpenRouter (Gemma 4 / LLM)
VIETNAMESE_SYSTEM_PROMPT = """Bạn là Chuyên gia Cao cấp về Phân tích Báo cáo Tài chính Doanh nghiệp (Senior Financial Analyst AI).
Nhiệm vụ của bạn là tiếp nhận dữ liệu 4 chỉ số tài chính cốt lõi đã được hệ thống Python tính toán chính xác, sau đó lập luận và đưa ra nhận định chuyên sâu, khách quan bằng Tiếng Việt chuẩn mực.

CÁC NGUYÊN TẮC CỐT LÕI (BẮT BUỘC TUÂN THỦ):
1. BẢO TOÀN SỐ LIỆU: Số liệu tỷ số do Python tính toán là Chân lý Duy nhất (Ground Truth). TUYỆT ĐỐI KHÔNG tự tính lại, không sửa đổi số liệu, không mâu thuẫn với kết quả của Python.
2. CĂN CỨ VÀ BẰNG CHỨNG: Mọi nhận định về rủi ro và điểm mạnh phải liên kết trực tiếp với 4 chỉ số tài chính cốt lõi được cung cấp (Thanh toán hiện hành, Đòn bẩy Nợ/VCSH, ROA, ROE).
3. ĐÁNH GIÁ CHUYÊN SÂU & ĐỘC LẬP:
   - Tự lập luận dựa trên bản chất kinh tế tài chính, không dùng câu từ khuôn mẫu sáo rỗng.
   - Phân tích mối quan hệ hữu cơ: Khả năng thanh toán (Current Ratio) bảo đảm sự sống còn ngắn hạn; Đòn bẩy nợ (Debt to Equity) phản ánh rủi ro cấu trúc vốn; ROA và ROE phản ánh năng lực sinh lời từ tài sản và vốn chủ sở hữu.
   - Nếu vốn chủ sở hữu âm hoặc chỉ số không xác định, giải thích rõ mức độ nguy hiểm nghiêm trọng đến khả năng hoạt động liên tục.
4. PHÒNG VỆ THẬN TRỌNG:
   - Các ngưỡng đánh giá là ngưỡng sàng lọc minh họa, không phải chuẩn mực kế toán pháp lý tuyệt đối.
   - Không kết luận chắc chắn về "phá sản", "gian lận" chỉ từ số liệu đơn kỳ; luôn nêu rõ các giới hạn về mùa vụ và cần đối chiếu thêm thuyết minh chi tiết.
5. ĐỊNH DẠNG ĐẦU RA: Phải trả về DUY NHẤT một khối JSON hợp lệ theo đúng cấu trúc yêu cầu dưới đây, không kèm văn bản giải thích bên ngoài JSON.
6. YÊU CẦU CÔ ĐỌNG & TRỌNG TÂM:
   - Nhận định ngắn gọn, súc tích (1-2 câu cho mỗi mục, đi thẳng vào số liệu).
   - Tối đa 2 điểm mạnh, tối đa 2 rủi ro, tối đa 2 khuyến nghị để không bị tràn giới hạn token.
   - BẮT BUỘC đóng trọn vẹn tất cả dấu ngoặc kép và ngoặc nhọn của JSON.

CẤU TRÚC JSON YÊU CẦU:
{
  "executive_summary": "Tóm tắt điều hành súc tích (1-2 đoạn ngắn) đánh giá sức khỏe tài chính tổng thể từ 4 chỉ số cốt lõi",
  "ratio_explanations": {
    "current_ratio": "Nhận định 1-2 câu về thanh toán hiện hành và đệm thanh khoản ngắn hạn",
    "debt_to_equity": "Nhận định 1-2 câu về hệ số Nợ / Vốn CSH, cơ cấu nợ và áp lực đòn bẩy",
    "roa": "Nhận định 1-2 câu về hiệu quả sinh lời trên tổng tài sản (ROA)",
    "roe": "Nhận định 1-2 câu về tỷ suất sinh lời trên vốn chủ sở hữu (ROE)"
  },
  "financial_strengths": [
    {
      "strength_title": "Tên điểm mạnh",
      "evidence": "Căn cứ số liệu",
      "significance": "Ý nghĩa tài chính"
    }
  ],
  "financial_risks": [
    {
      "risk_title": "Tên rủi ro",
      "severity": "critical | high | medium | low",
      "evidence": "Căn cứ số liệu",
      "implication": "Tác động tiềm ẩn",
      "related_ratios": ["current_ratio", "debt_to_equity", "roa", "roe"]
    }
  ],
  "recommendations": [
    "Khuyến nghị hành động chiến lược thiết thực cho ban điều hành"
  ],
  "data_limitations": [
    "Lưu ý phân tích ngắn gọn"
  ],
  "disclaimer": "Tuyên bố miễn trừ trách nhiệm phân tích tài chính"
}
"""


class AIFinancialInterpreter:
    """Orchestrator for AI-powered financial interpretation using OpenRouter."""

    def __init__(
        self,
        client: Optional[OpenRouterClient] = None,
        config: Optional[OpenRouterConfig] = None,
    ):
        """Initialize interpreter with OpenRouter client or configuration.

        Args:
            client: Pre-configured OpenRouterClient instance.
            config: Optional OpenRouterConfig. If neither is provided, loaded from env.
        """
        if client:
            self.client = client
        elif config:
            self.client = OpenRouterClient(config=config)
        else:
            self.client = OpenRouterClient()

    def build_prompts(
        self,
        assessment: FinancialAssessment,
        ratio_report: Optional[Any] = None,
    ) -> Tuple[str, str]:
        """Construct system and user prompts grounded strictly in the 4 core financial ratios.

        Args:
            assessment: FinancialAssessment from Sprint 4B.
            ratio_report: Optional FinancialRatioReport for direct ratio values.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        ai_input = AIInterpretationInput.from_4_core_kpis(
            assessment=assessment, ratio_report=ratio_report
        )
        system_prompt = VIETNAMESE_SYSTEM_PROMPT
        user_prompt = (
            "Dưới đây là 4 chỉ số tài chính cốt lõi của doanh nghiệp do hệ thống Python tính toán. "
            "Hãy đóng vai trò Chuyên gia Phân tích Tài chính Cao cấp, phân tích chuyên sâu và trả về JSON theo đúng định dạng:\n\n"
            f"{ai_input.to_formatted_prompt_context()}"
        )
        return system_prompt, user_prompt

    def interpret(
        self,
        assessment: FinancialAssessment,
        ratio_report: Optional[Any] = None,
        allow_fallback: bool = False,
        temperature: float = 0.2,
    ) -> AIInterpretationOutput:
        """Execute AI interpretation with validation and optional fallback.

        Args:
            assessment: FinancialAssessment instance.
            ratio_report: Optional FinancialRatioReport.
            allow_fallback: If True, returns a deterministic fallback when API fails.
            temperature: Sampling temperature for AI generation (default: 0.2).

        Returns:
            Validated AIInterpretationOutput.
        """
        system_prompt, user_prompt = self.build_prompts(assessment, ratio_report=ratio_report)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # Send chat completion request to OpenRouter
            response = self.client.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=4000,
                response_format=None,
            )

            raw_content = response.get("content", "")
            model_used = response.get("model", self.client.config.model)
            usage = response.get("usage", {})

            # Parse and validate JSON from response
            output = self._parse_and_validate_response(
                raw_content=raw_content,
                model_used=model_used,
                usage=usage,
            )

            # Defensive post-validation against hallucinations
            output = self._sanitize_against_hallucinations(output, assessment)
            return output

        except (OpenRouterError, Exception) as err:
            logger.warning(
                "Lỗi khi thực hiện AI interpretation qua OpenRouter (%s): %s",
                type(err).__name__,
                err,
            )
            if allow_fallback:
                logger.info("Kích hoạt cơ chế deterministic fallback...")
                return self.generate_deterministic_fallback(
                    assessment=assessment,
                    error_reason=f"OpenRouter API Unavailable ({type(err).__name__}: {err})",
                )
            raise

    # =========================================================================
    # Response Parsing & JSON Extraction
    # =========================================================================

    def _parse_and_validate_response(
        self,
        raw_content: str,
        model_used: str,
        usage: Dict[str, Any],
    ) -> AIInterpretationOutput:
        """Extract JSON from raw LLM output and validate against Pydantic schema."""
        json_dict = self._extract_json_dict(raw_content)

        # Ensure minimum required fields exist even if response was partially truncated
        if not json_dict.get("executive_summary"):
            json_dict["executive_summary"] = "Báo cáo phân tích sức khỏe tài chính dựa trên 4 chỉ số cốt lõi."
        if not json_dict.get("disclaimer"):
            json_dict["disclaimer"] = (
                "Báo cáo phân tích này được thực hiện bởi trí tuệ nhân tạo (AI) dựa trên 4 chỉ số tài chính cốt lõi. "
                "Kết quả mang tính chất tham khảo phân tích thông tin."
            )

        try:
            output = AIInterpretationOutput.model_validate(json_dict)
            output.model_used = model_used
            output.usage = usage
            output.is_fallback = False
            return output
        except Exception as val_err:
            raise ResponseValidationError(
                f"Phản hồi từ model không thỏa mãn Pydantic schema: {val_err}"
            )

    @classmethod
    def _extract_json_dict(cls, raw_content: str) -> Dict[str, Any]:
        """Robustly extract a JSON dictionary from raw model text.

        Handles pure JSON, markdown fenced code blocks (```json ... ```),
        text with prefix/suffix, and automatically repairs truncated JSON responses.
        """
        content = raw_content.strip()

        # Case 1: Check for Markdown code fences
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Case 2: Direct JSON parse
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Case 3: Find outermost curly braces
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            substring = content[start : end + 1]
            try:
                data = json.loads(substring)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Case 4: Resilient repair for truncated or incomplete JSON responses
        repaired = cls._repair_truncated_json(content)
        if repaired and isinstance(repaired, dict):
            logger.info("Đã phục hồi thành công cấu trúc JSON bị ngắt quãng từ LLM.")
            return repaired

        raise ResponseValidationError(
            f"Không thể tìm thấy hoặc bóc tách JSON hợp lệ từ phản hồi của model: {content[:200]}"
        )

    @classmethod
    def _repair_truncated_json(cls, raw: str) -> Optional[Dict[str, Any]]:
        """Attempt to repair and parse a truncated or incomplete JSON string from LLMs."""
        s = raw.strip()
        # Strip markdown fences if open
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        # Find first opening brace
        start = s.find("{")
        if start == -1:
            return None
        candidate = s[start:]

        # 1. Direct parse attempt
        try:
            res = json.loads(candidate)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 2. Track open quotes, brackets, and braces
        in_string = False
        escape = False
        stack: List[str] = []
        clean_chars: List[str] = []
        for ch in candidate:
            if escape:
                escape = False
                clean_chars.append(ch)
                continue
            if ch == "\\":
                escape = True
                clean_chars.append(ch)
                continue
            if ch == '"':
                in_string = not in_string
                clean_chars.append(ch)
                continue
            if not in_string:
                if ch == "{":
                    stack.append("}")
                elif ch == "[":
                    stack.append("]")
                elif ch in ("}", "]"):
                    if stack and stack[-1] == ch:
                        stack.pop()
            clean_chars.append(ch)

        repaired = "".join(clean_chars)
        if in_string:
            repaired += '"'

        # Remove trailing dangling comma or colon
        repaired = re.sub(r",\s*$", "", repaired)
        repaired = re.sub(r":\s*$", ': ""', repaired)

        # Close open structures in LIFO order
        for closing in reversed(stack):
            repaired += closing

        try:
            res = json.loads(repaired)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 3. Progressive rollback to last complete key-value pair
        cur = repaired
        for _ in range(15):
            last_comma = cur.rfind(",")
            if last_comma == -1:
                break
            cur = cur[:last_comma]
            open_b = cur.count("{") - cur.count("}")
            open_sq = cur.count("[") - cur.count("]")
            trial = cur + ("]" * max(0, open_sq)) + ("}" * max(0, open_b))
            try:
                res = json.loads(trial)
                if isinstance(res, dict) and res:
                    return res
            except Exception:
                continue

        return None

    # =========================================================================
    # Defensive Hallucination Sanitizer
    # =========================================================================

    def _sanitize_against_hallucinations(
        self,
        output: AIInterpretationOutput,
        assessment: FinancialAssessment,
    ) -> AIInterpretationOutput:
        """Cross-check output against Sprint 4 ground truth to filter hallucinations."""
        # 1. Filter out hallucinated ratio keys in ratio_explanations
        sanitized_explanations: Dict[str, str] = {}
        for key, exp in output.ratio_explanations.items():
            if key in CANONICAL_RATIO_KEYS:
                sanitized_explanations[key] = exp
            else:
                logger.warning("Bỏ qua ratio_key không có thật do LLM tự suy diễn: %s", key)
        output.ratio_explanations = sanitized_explanations

        # 2. Guard against negative equity / UNDEFINED ratio misinterpretation
        dta = assessment.get_assessment("debt_to_assets")
        dte = assessment.get_assessment("debt_to_equity")
        roe = assessment.get_assessment("roe")

        if dte and dte.status == AssessmentStatus.UNDEFINED:
            # Check if any strength improperly praises equity or solvency
            filtered_strengths = []
            for s in output.financial_strengths:
                title = s.strength_title if isinstance(s, AIStrengthItem) else str(s)
                if "vốn chủ sở hữu" in title.lower() and ("tốt" in title.lower() or "dồi dào" in title.lower()):
                    logger.warning("Loại bỏ điểm mạnh mâu thuẫn với tình trạng âm vốn CSH: %s", title)
                    continue
                filtered_strengths.append(s)
            output.financial_strengths = filtered_strengths

        return output

    # =========================================================================
    # Deterministic Rule-Based Fallback
    # =========================================================================

    def generate_deterministic_fallback(
        self,
        assessment: FinancialAssessment,
        error_reason: str,
    ) -> AIInterpretationOutput:
        """Generate a structured, explainable fallback interpretation from Sprint 4 rules.

        This guarantees that even when OpenRouter or network connections are down,
        the system returns an evidence-based report clearly labelled as fallback.
        """
        company = assessment.company_name or "Doanh nghiệp"
        year = f"năm {assessment.fiscal_year}" if assessment.fiscal_year else ""

        # Executive summary from category overviews
        summary_paragraphs = [
            f"Báo cáo tổng hợp sức khỏe tài chính của {company} {year} "
            f"được xây dựng dựa trên kết quả tính toán định lượng và bộ quy tắc sàng lọc tài chính.",
            f"Trạng thái tổng thể ghi nhận: {assessment.overall_status.value.upper()}. "
            + " ".join(assessment.key_findings),
        ]
        exec_summary = "\n\n".join(summary_paragraphs)

        # Financial Strengths (from adequate ratios)
        strengths: List[Union[AIStrengthItem, str]] = []
        for key, r in assessment.ratio_assessments.items():
            if r.status == AssessmentStatus.ADEQUATE and r.value is not None:
                strengths.append(
                    AIStrengthItem(
                        strength_title=f"{r.label} đạt ngưỡng an toàn ({r.formatted_value})",
                        evidence=f"{key} = {r.formatted_value}",
                        significance=r.explanation,
                    )
                )

        # If profitability is positive, add as strength
        npm = assessment.get_assessment("net_profit_margin")
        if npm and npm.value and npm.value > 0:
            strengths.append(
                AIStrengthItem(
                    strength_title="Hoạt động kinh doanh có lãi ròng trong kỳ",
                    evidence=f"Net Profit Margin = {npm.formatted_value}",
                    significance="Doanh nghiệp duy trì biên sinh lời sau thuế dương.",
                )
            )

        if not strengths:
            strengths.append(
                AIStrengthItem(
                    strength_title="Ghi nhận số liệu tài chính đầy đủ",
                    evidence=f"Đã tính toán {assessment.calculated_count}/14 chỉ số",
                    significance="Tạo cơ sở dữ liệu để theo dõi biến động các kỳ tiếp theo.",
                )
            )

        # Financial Risks (from warnings and alerts)
        risks: List[AIRiskItem] = []
        for w in assessment.warnings:
            risks.append(
                AIRiskItem(
                    risk_title=w.title,
                    severity=w.severity.value,
                    evidence=w.evidence,
                    implication=w.message,
                    related_ratios=w.related_ratios,
                )
            )

        # Ratio explanations (from Sprint 4 assessment)
        ratio_explanations: Dict[str, str] = {
            key: r.explanation for key, r in assessment.ratio_assessments.items()
        }

        # Recommendations (from warnings)
        recommendations: List[str] = []
        for w in assessment.warnings:
            if w.recommendation and w.recommendation not in recommendations:
                recommendations.append(w.recommendation)

        if not recommendations:
            recommendations.append(
                "Tiếp tục duy trì giám sát định kỳ các chỉ số thanh khoản và cơ cấu vốn qua các quý tiếp theo."
            )

        # Limitations
        limitations = list(assessment.limitations)
        limitations.append(
            f"Lưu ý: Nội dung này được tạo tự động bởi bộ quy tắc dự phòng (Deterministic Fallback) "
            f"do không thể kết nối tới mô hình AI: {error_reason}."
        )

        return AIInterpretationOutput(
            executive_summary=exec_summary,
            financial_strengths=strengths,
            financial_risks=risks,
            ratio_explanations=ratio_explanations,
            recommendations=recommendations,
            data_limitations=limitations,
            is_fallback=True,
            fallback_reason=error_reason,
            model_used="deterministic_rule_engine_v1.0",
        )
