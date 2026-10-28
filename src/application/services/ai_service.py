"""Dịch vụ diễn giải tài chính bằng AI với prompt neo số liệu và cơ chế dự phòng tất định.

Module này đóng vai trò dịch vụ ứng dụng (Application Service) trung gian giữa miền nghiệp vụ
và mô hình ngôn ngữ lớn (LLM qua OpenRouter hoặc IAIClient bất kỳ). Module thực hiện:
- Xây dựng prompt neo chặt chẽ vào 4 chỉ số tài chính cốt lõi (Current Ratio, D/E, ROA, ROE).
- Thực thi gọi API với cơ chế thử lại (exponential backoff) và kiểm soát định dạng JSON nghiêm ngặt.
- Bóc tách, sửa lỗi JSON bị ngắt quãng (Resilient JSON Repair) và xác thực qua Pydantic schema.
- Phòng vệ chống ảo giác (Defensive Sanitization) loại trừ các chỉ số không có thật.
- Cơ chế dự phòng tất định (Deterministic Rule-based Fallback) khi mất kết nối mạng hoặc lỗi API.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.application.interfaces.ai import IAIClient
from src.domain.models.ai import (
    AIInterpretationInput,
    AIInterpretationOutput,
    AIRiskItem,
    AIStrengthItem,
)
from src.domain.models.assessment import (
    AssessmentStatus,
    FinancialAssessment,
    WarningSeverity,
)
from src.domain.ratios.engine import RATIO_METADATA
from src.infrastructure.ai.client import (
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
    ResponseValidationError,
)

logger = logging.getLogger(__name__)

# Tập hợp các khóa chỉ số tài chính chuẩn tắc hợp lệ để chống hallucination
CANONICAL_RATIO_KEYS = set(RATIO_METADATA.keys())

# System prompt chuẩn mực thiết kế cho AI phân tích tài chính cao cấp qua OpenRouter
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


class AIInterpretationService:
    """Điều phối diễn giải báo cáo tài chính bằng AI qua OpenRouter hoặc triển khai IAIClient bất kỳ.

    Attributes:
        client (Union[IAIClient, OpenRouterClient]): Máy khách giao tiếp API AI.
    """

    def __init__(
        self,
        client: Optional[Union[IAIClient, OpenRouterClient]] = None,
        config: Optional[OpenRouterConfig] = None,
    ) -> None:
        """Khởi tạo dịch vụ diễn giải AI với client hoặc cấu hình kết nối.

        Args:
            client (Optional[Union[IAIClient, OpenRouterClient]]): Client tuân thủ giao thức IAIClient.
            config (Optional[OpenRouterConfig]): Cấu hình OpenRouter tùy biến nếu chưa có client.
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
        """Xây dựng system prompt và user prompt được neo chặt chẽ vào 4 chỉ số tài chính cốt lõi.

        Args:
            assessment (FinancialAssessment): Kết quả đánh giá sức khỏe tài chính.
            ratio_report (Optional[Any]): Báo cáo tỷ số tài chính (tùy chọn).

        Returns:
            Tuple[str, str]: (System Prompt định nghĩa vai trò và nguyên tắc, User Prompt kèm ngữ cảnh số liệu).
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
        """Thực thi gọi mô hình AI để diễn giải tài chính, kèm xác thực và cơ chế dự phòng.

        Args:
            assessment (FinancialAssessment): Kết quả đánh giá tài chính định lượng.
            ratio_report (Optional[Any]): Báo cáo tỷ số tài chính.
            allow_fallback (bool): Cho phép tự động chuyển sang cơ chế dự phòng tất định nếu lỗi.
            temperature (float): Độ sáng tạo của mô hình (mặc định 0.2 để giữ tính ổn định).

        Returns:
            AIInterpretationOutput: Dữ liệu phân tích gồm tóm tắt, điểm mạnh, rủi ro, khuyến nghị.

        Raises:
            OpenRouterError: Khi gọi API thất bại và allow_fallback=False.
            ResponseValidationError: Khi phản hồi không đúng định dạng JSON hoặc schema và allow_fallback=False.
        """
        system_prompt, user_prompt = self.build_prompts(assessment, ratio_report=ratio_report)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # Gửi yêu cầu hoàn thành đoạn chat tới máy khách AI
            response = self.client.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=4000,
                response_format=None,
            )

            raw_content = response.get("content", "")
            default_model = getattr(getattr(self.client, "config", None), "model", "openrouter")
            model_used = response.get("model", default_model)
            usage = response.get("usage", {})

            # Bóc tách và xác thực cấu trúc JSON từ nội dung trả về
            output = self._parse_and_validate_response(
                raw_content=raw_content,
                model_used=model_used,
                usage=usage,
            )

            # Phòng vệ loại bỏ hiện tượng ảo giác (hallucination)
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

    def _parse_and_validate_response(
        self,
        raw_content: str,
        model_used: str,
        usage: Dict[str, Any],
    ) -> AIInterpretationOutput:
        """Bóc tách chuỗi JSON thô từ mô hình và xác thực theo Pydantic schema.

        Args:
            raw_content (str): Nội dung văn bản thô từ LLM.
            model_used (str): Tên mô hình đã thực thi.
            usage (Dict[str, Any]): Thống kê số lượng token tiêu thụ.

        Returns:
            AIInterpretationOutput: Mô hình Pydantic hợp lệ.

        Raises:
            ResponseValidationError: Khi dữ liệu không thỏa mãn cấu trúc yêu cầu.
        """
        json_dict = self._extract_json_dict(raw_content)

        # Đảm bảo các trường bắt buộc tối thiểu tồn tại kể cả khi phản hồi bị cắt bớt
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
        """Trích xuất từ điển JSON từ văn bản phản hồi thô bằng nhiều phương án dự phòng.

        Thứ tự thử nghiệm:
        1. Khối mã Markdown ```json ... ```.
        2. Phân tích trực tiếp toàn bộ chuỗi (json.loads).
        3. Cắt chuỗi từ dấu { đầu tiên đến dấu } cuối cùng.
        4. Thuật toán tự động sửa lỗi và đóng ngoặc JSON bị ngắt quãng (_repair_truncated_json).

        Args:
            raw_content (str): Chuỗi phản hồi thô từ mô hình.

        Returns:
            Dict[str, Any]: Đối tượng từ điển JSON trích xuất thành công.

        Raises:
            ResponseValidationError: Khi không thể trích xuất được bất kỳ khối JSON hợp lệ nào.
        """
        content = raw_content.strip()

        # Trường hợp 1: Kiểm tra khối định dạng mã Markdown
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # Trường hợp 2: Thử phân tích JSON trực tiếp
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Trường hợp 3: Tìm cặp dấu ngoặc nhọn bao ngoài cùng
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

        # Trường hợp 4: Cơ chế phục hồi JSON bị ngắt quãng do tràn token
        repaired = cls._repair_truncated_json(content)
        if repaired and isinstance(repaired, dict):
            logger.info("Đã phục hồi thành công cấu trúc JSON bị ngắt quãng từ LLM.")
            return repaired

        raise ResponseValidationError(
            f"Không thể tìm thấy hoặc bóc tách JSON hợp lệ từ phản hồi của model: {content[:200]}"
        )

    @classmethod
    def _repair_truncated_json(cls, raw: str) -> Optional[Dict[str, Any]]:
        """Phục hồi và sửa lỗi cú pháp cho chuỗi JSON bị ngắt quãng khi chạm trần token.

        Thuật toán:
        1. Xác định vị trí mở ngoặc nhọn đầu tiên.
        2. Dò quét qua từng ký tự, theo dõi trạng thái chuỗi ký tự (trong/ngoài dấu ngoặc kép)
           và sử dụng ngăn xếp (stack) để ghi nhận các dấu đóng ngoặc tương ứng (}, ]).
        3. Tự động đóng dấu ngoặc kép dở dang, xóa dấu phẩy thừa và đóng các dấu ngoặc nhọn/vuông còn thiếu.
        4. Thử lùi dần về dấu phẩy gần nhất nếu cấu trúc lồng nhau bị đứt gãy.

        Args:
            raw (str): Chuỗi JSON bị cắt dở dang.

        Returns:
            Optional[Dict[str, Any]]: Từ điển JSON đã được vá hoàn chỉnh hoặc None nếu không thể cứu vãn.
        """
        s = raw.strip()
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        start = s.find("{")
        if start == -1:
            return None
        candidate = s[start:]

        # 1. Thử phân tích trực tiếp ứng viên
        try:
            res = json.loads(candidate)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 2. Theo dõi trạng thái đóng mở chuỗi và ngăn xếp ngoặc
        in_string: bool = False
        escape: bool = False
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

        repaired = re.sub(r",\s*$", "", repaired)
        repaired = re.sub(r":\s*$", ': ""', repaired)

        for closing in reversed(stack):
            repaired += closing

        try:
            res = json.loads(repaired)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 3. Lùi dần từng bước về cặp khóa-giá trị hoàn chỉnh gần nhất
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

    def _sanitize_against_hallucinations(
        self,
        output: AIInterpretationOutput,
        assessment: FinancialAssessment,
    ) -> AIInterpretationOutput:
        """Kiểm tra đối chiếu với số liệu gốc (Ground Truth) để lọc bỏ hiện tượng ảo giác.

        Hàm thực hiện 2 cơ chế kiểm soát:
        1. Loại bỏ các giải thích chỉ số có khóa lạ không nằm trong danh mục tỷ số chuẩn mực.
        2. Nếu Vốn chủ sở hữu âm (hệ số D/E = UNDEFINED), loại bỏ các điểm mạnh ngợi khen
           "vốn chủ sở hữu tốt / dồi dào" do mô hình tự huyễn hoặc.

        Args:
            output (AIInterpretationOutput): Đầu ra diễn giải của mô hình.
            assessment (FinancialAssessment): Kết quả đánh giá gốc làm căn cứ kiểm chứng.

        Returns:
            AIInterpretationOutput: Đối tượng phân tích đã được làm sạch và đảm bảo an toàn nghiệp vụ.
        """
        sanitized_explanations: Dict[str, str] = {}
        for key, exp in output.ratio_explanations.items():
            if key in CANONICAL_RATIO_KEYS:
                sanitized_explanations[key] = exp
            else:
                logger.warning("Bỏ qua ratio_key không có thật do LLM tự suy diễn: %s", key)
        output.ratio_explanations = sanitized_explanations

        # Kiểm tra mâu thuẫn vốn chủ sở hữu âm
        dte = assessment.get_assessment("debt_to_equity")
        if dte and dte.status == AssessmentStatus.UNDEFINED:
            filtered_strengths = []
            for s in output.financial_strengths:
                title = s.strength_title if isinstance(s, AIStrengthItem) else str(s)
                if "vốn chủ sở hữu" in title.lower() and ("tốt" in title.lower() or "dồi dào" in title.lower()):
                    logger.warning("Loại bỏ điểm mạnh mâu thuẫn với tình trạng âm vốn CSH: %s", title)
                    continue
                filtered_strengths.append(s)
            output.financial_strengths = filtered_strengths

        return output

    def generate_deterministic_fallback(
        self,
        assessment: FinancialAssessment,
        error_reason: str,
    ) -> AIInterpretationOutput:
        """Tạo báo cáo diễn giải cấu trúc có thể giải trình được bằng động cơ quy tắc dự phòng.

        Cơ chế này hoàn toàn độc lập với LLM bên ngoài, chuyển đổi trực tiếp các kết quả đánh giá,
        cảnh báo rủi ro và khuyến nghị quản trị từ FinancialAssessment thành mô hình đầu ra chuẩn.

        Args:
            assessment (FinancialAssessment): Đánh giá sức khỏe tài chính định lượng.
            error_reason (str): Lý do kích hoạt cơ chế dự phòng (ví dụ: mất kết nối API).

        Returns:
            AIInterpretationOutput: Bản diễn giải dự phòng với cờ is_fallback=True.
        """
        company = assessment.company_name or "Doanh nghiệp"
        year = f"năm {assessment.fiscal_year}" if assessment.fiscal_year else ""

        summary_paragraphs = [
            f"Báo cáo tổng hợp sức khỏe tài chính của {company} {year} "
            f"được xây dựng dựa trên kết quả tính toán định lượng và bộ quy tắc sàng lọc tài chính.",
            f"Trạng thái tổng thể ghi nhận: {assessment.overall_status.value.upper()}. "
            + " ".join(assessment.key_findings),
        ]
        exec_summary = "\n\n".join(summary_paragraphs)

        # Trích xuất các điểm mạnh từ các chỉ số đạt mức an toàn
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

        # Chuyển đổi cảnh báo thành các mục rủi ro tài chính
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

        ratio_explanations: Dict[str, str] = {
            key: r.explanation for key, r in assessment.ratio_assessments.items()
        }

        # Thu thập các khuyến nghị hành động
        recommendations: List[str] = []
        for w in assessment.warnings:
            if w.recommendation and w.recommendation not in recommendations:
                recommendations.append(w.recommendation)

        if not recommendations:
            recommendations.append(
                "Tiếp tục duy trì giám sát định kỳ các chỉ số thanh khoản và cơ cấu vốn qua các quý tiếp theo."
            )

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


# Bí danh tương thích ngược
AIFinancialInterpreter = AIInterpretationService
