"""Unit tests for AIFinancialInterpreter and AI models (Sprint 5).

All unit tests use mocked HTTP clients and deterministic fixtures.
No real OpenRouter API calls or paid credentials are required.
"""
from decimal import Decimal
import json
from unittest.mock import MagicMock

import pytest

from src.application.services.ai_service import (
    AIFinancialInterpreter,
    CANONICAL_RATIO_KEYS,
)
from src.application.services.parsing_service import FinancialStatementParser
from src.domain.assessment.evaluator import FinancialHealthAssessor
from src.domain.models.ai import (
    AIInterpretationInput,
    AIInterpretationOutput,
    AIRiskItem,
    AIStrengthItem,
    FinancialRatioInput,
)
from src.domain.models.assessment import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    OverallHealthStatus,
    RatioAssessment,
    WarningCategory,
    WarningSeverity,
)
from src.domain.models.ratios import (
    FinancialRatioReport,
    RatioCategory,
    RatioResult,
    RatioStatus,
)
from src.domain.ratios.engine import FinancialRatioCalculator
from src.infrastructure.ai.client import (
    AuthenticationError,
    NetworkError,
    OpenRouterClient,
    OpenRouterConfig,
    RateLimitError,
    ResponseValidationError,
    ServerError,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_assessment():
    """Build a deterministic baseline FinancialAssessment for testing."""
    ratios = {
        "current_ratio": RatioAssessment(
            ratio_key="current_ratio",
            label="Hệ số thanh toán hiện hành",
            category=RatioCategory.LIQUIDITY,
            value=Decimal("1.45"),
            formatted_value="1.45 lần",
            status=AssessmentStatus.WATCH,
            explanation="Hệ số thanh toán hiện hành ở vùng đệm theo dõi (1.0 - 1.5 lần).",
            warnings=["Theo dõi thanh khoản"],
            rule_id="RULE_LIQ_CURRENT_RATIO_WATCH",
            limitations=["Số liệu cuối kỳ"],
        ),
        "debt_to_assets": RatioAssessment(
            ratio_key="debt_to_assets",
            label="Hệ số nợ/tổng tài sản",
            category=RatioCategory.LEVERAGE,
            value=Decimal("0.504"),
            formatted_value="50.40%",
            status=AssessmentStatus.WATCH,
            explanation="Hệ số nợ/tài sản ở vùng đệm theo dõi (50% - 70%).",
            warnings=["Theo dõi đòn bẩy"],
            rule_id="RULE_LEV_DTA_WATCH",
            limitations=["Chưa phân tách nợ vay chịu lãi"],
        ),
        "net_profit_margin": RatioAssessment(
            ratio_key="net_profit_margin",
            label="Tỷ suất lợi nhuận sau thuế",
            category=RatioCategory.PROFITABILITY,
            value=Decimal("0.0578"),
            formatted_value="5.78%",
            status=AssessmentStatus.CALCULATED_NO_BENCHMARK,
            explanation="Kinh doanh có lãi với biên ròng 5.78%.",
            warnings=[],
            rule_id="RULE_PROF_POSITIVE_NO_BENCHMARK",
            limitations=["Cần so sánh ngành"],
        ),
    }

    warnings = [
        FinancialWarning(
            code="LIQUIDITY_CURRENT_RATIO_WATCH",
            category=WarningCategory.LIQUIDITY,
            severity=WarningSeverity.LOW,
            title="Theo dõi thanh khoản: Current Ratio ở vùng đệm (1.45 lần)",
            message="Biên an toàn thanh khoản vừa phải.",
            related_ratios=["current_ratio"],
            evidence="1.0 <= 1.45 < 1.5 lần",
            recommendation="Theo dõi hạn mức tín dụng dự phòng.",
        ),
        FinancialWarning(
            code="LEVERAGE_DEBT_TO_ASSETS_WATCH",
            category=WarningCategory.LEVERAGE,
            severity=WarningSeverity.LOW,
            title="Theo dõi đòn bẩy: Nợ/tài sản ở vùng đệm (50.40%)",
            message="Mức độ nợ trung bình.",
            related_ratios=["debt_to_assets"],
            evidence="50% < 50.40% <= 70%",
            recommendation="Duy trì cơ cấu vốn ổn định.",
        ),
    ]

    return FinancialAssessment(
        company_name="CTCP DƯỢC PHẨM MẪU",
        fiscal_year=2023,
        currency="VND",
        overall_status=OverallHealthStatus.MIXED,
        ratio_assessments=ratios,
        warnings=warnings,
        category_overviews={
            "liquidity": "Khả năng thanh toán ngắn hạn ở mức vừa phải, trong vùng đệm theo dõi.",
            "leverage": "Đòn bẩy tài chính trung bình, cơ cấu nợ và vốn tương đối cân bằng.",
            "efficiency": "Vòng quay tài sản cần đối chiếu thêm với chuẩn ngành.",
            "profitability": "Doanh nghiệp duy trì kết quả kinh doanh có lãi.",
        },
        key_findings=[
            "Sức khỏe tài chính đan xen: Kinh doanh có lãi nhưng thanh khoản ở vùng đệm.",
            "Biên lợi nhuận ròng đạt 5.78%.",
        ],
        limitations=[
            "Số liệu BCTC đơn lẻ 1 năm tài chính.",
            "Các ngưỡng đánh giá là ngưỡng sàng lọc minh họa.",
        ],
        total_ratios_evaluated=3,
        calculated_count=3,
        watch_count=2,
    )


@pytest.fixture
def valid_llm_json():
    return {
        "executive_summary": "CTCP Dược Phẩm Mẫu duy trì kết quả kinh doanh có lãi năm 2023 với biên lợi nhuận ròng 5.78%. Tuy nhiên, các chỉ tiêu thanh khoản và đòn bẩy đang nằm trong vùng đệm cần theo dõi sát.",
        "financial_strengths": [
            {
                "strength_title": "Hoạt động kinh doanh sinh lời dương",
                "evidence": "Net Profit Margin đạt 5.78%",
                "significance": "Tạo dòng tiền và tích lũy thặng dư vốn cho doanh nghiệp."
            }
        ],
        "financial_risks": [
            {
                "risk_title": "Hệ số thanh toán hiện hành ở vùng đệm",
                "severity": "low",
                "evidence": "Current Ratio = 1.45 lần",
                "implication": "Biên an toàn thanh khoản mỏng nếu các khoản phải thu chậm thu hồi.",
                "related_ratios": ["current_ratio"]
            }
        ],
        "ratio_explanations": {
            "current_ratio": "Current Ratio 1.45 lần cho thấy tài sản ngắn hạn đủ bù đắp nợ ngắn hạn nhưng cần quản trị vốn lưu động chặt.",
            "debt_to_assets": "Nợ chiếm 50.40% tổng tài sản, phản ánh cơ cấu tài trợ tương đối cân bằng."
        },
        "recommendations": [
            "Duy trì hạn mức tín dụng dự phòng tại ngân hàng để chủ động dòng tiền.",
            "Thắt chặt công tác thu hồi công nợ để củng cố hệ số thanh toán nhanh."
        ],
        "data_limitations": [
            "Báo cáo phân tích trên số liệu 1 năm, chưa phản ánh tính chu kỳ kinh doanh dài hạn."
        ],
        "disclaimer": "Báo cáo phân tích AI mang tính chất tham khảo, không cấu thành khuyến nghị đầu tư."
    }


# =============================================================================
# UNIT TESTS
# =============================================================================

class TestAIFinancialInterpreter:
    """Test suite for prompt engineering, response parsing, validation, and fallback."""

    def test_build_prompts_contains_all_evidence(self, sample_assessment):
        interpreter = AIFinancialInterpreter(client=MagicMock())
        system_prompt, user_prompt = interpreter.build_prompts(sample_assessment)

        # Check System Prompt instructions
        assert "Chuyên gia Cao cấp về Phân tích Báo cáo Tài chính Doanh nghiệp" in system_prompt
        assert "BẢO TOÀN SỐ LIỆU" in system_prompt
        assert "ngưỡng sàng lọc minh họa" in system_prompt

        # Check User Prompt context contains the 4 core KPIs and no rule engine canned text
        assert "CTCP DƯỢC PHẨM MẪU" in user_prompt
        assert "2023" in user_prompt
        assert "VND" in user_prompt
        assert "1.45 lần" in user_prompt
        assert "current_ratio" in user_prompt
        assert "debt_to_equity" in user_prompt
        assert "roa" in user_prompt
        assert "roe" in user_prompt
        # Pre-configured rule engine warnings are excluded
        assert "LIQUIDITY_CURRENT_RATIO_WATCH" not in user_prompt
        assert "LEVERAGE_DEBT_TO_ASSETS_WATCH" not in user_prompt

    def test_successful_interpretation_parsing(self, sample_assessment, valid_llm_json):
        mock_client = MagicMock()
        mock_client.create_chat_completion.return_value = {
            "content": json.dumps(valid_llm_json, ensure_ascii=False),
            "model": "google/gemma-4-31b-it:free",
            "usage": {"prompt_tokens": 500, "completion_tokens": 300, "total_tokens": 800},
            "id": "gen-test-001",
        }

        interpreter = AIFinancialInterpreter(client=mock_client)
        output = interpreter.interpret(sample_assessment, allow_fallback=False)

        assert isinstance(output, AIInterpretationOutput)
        assert output.is_fallback is False
        assert output.model_used == "google/gemma-4-31b-it:free"
        assert "CTCP Dược Phẩm Mẫu" in output.executive_summary
        assert len(output.financial_strengths) == 1
        assert len(output.financial_risks) == 1
        assert output.financial_risks[0].risk_title == "Hệ số thanh toán hiện hành ở vùng đệm"
        assert output.financial_risks[0].severity == "low"
        assert "current_ratio" in output.ratio_explanations
        assert len(output.recommendations) == 2
        assert output.usage["total_tokens"] == 800

    def test_parse_json_from_markdown_code_blocks(self, sample_assessment, valid_llm_json):
        raw_markdown = f"Dưới đây là kết quả phân tích theo định dạng JSON:\n```json\n{json.dumps(valid_llm_json, ensure_ascii=False)}\n```\nHy vọng hữu ích!"
        mock_client = MagicMock()
        mock_client.create_chat_completion.return_value = {
            "content": raw_markdown,
            "model": "google/gemma-4-31b-it:free",
            "usage": {},
            "id": "gen-test-002",
        }

        interpreter = AIFinancialInterpreter(client=mock_client)
        output = interpreter.interpret(sample_assessment, allow_fallback=False)

        assert isinstance(output, AIInterpretationOutput)
        assert "5.78%" in output.executive_summary

    def test_parse_json_with_outermost_brackets(self, sample_assessment, valid_llm_json):
        raw_text = f"Lời mở đầu...\n{json.dumps(valid_llm_json, ensure_ascii=False)}\nLời kết..."
        mock_client = MagicMock()
        mock_client.create_chat_completion.return_value = {
            "content": raw_text,
            "model": "google/gemma-4-31b-it:free",
            "usage": {},
            "id": "gen-test-003",
        }

        interpreter = AIFinancialInterpreter(client=mock_client)
        output = interpreter.interpret(sample_assessment, allow_fallback=False)
        assert isinstance(output, AIInterpretationOutput)

    def test_malformed_json_raises_when_fallback_disabled(self, sample_assessment):
        mock_client = MagicMock()
        mock_client.create_chat_completion.return_value = {
            "content": "Đây không phải là JSON: {chưa đóng ngoặc",
            "model": "google/gemma-4-31b-it:free",
            "usage": {},
            "id": "gen-bad",
        }

        interpreter = AIFinancialInterpreter(client=mock_client)
        with pytest.raises(ResponseValidationError):
            interpreter.interpret(sample_assessment, allow_fallback=False)

    def test_hallucinated_ratio_keys_are_sanitized(self, sample_assessment, valid_llm_json):
        # Inject hallucinated ratio keys (e.g. pe_ratio, altman_z)
        valid_llm_json["ratio_explanations"]["pe_ratio"] = "P/E bằng 15 lần (bịa đặt)"
        valid_llm_json["ratio_explanations"]["altman_z_score"] = "Altman Z = 3.2 (bịa đặt)"

        mock_client = MagicMock()
        mock_client.create_chat_completion.return_value = {
            "content": json.dumps(valid_llm_json, ensure_ascii=False),
            "model": "google/gemma-4-31b-it:free",
            "usage": {},
            "id": "gen-hallucinate",
        }

        interpreter = AIFinancialInterpreter(client=mock_client)
        output = interpreter.interpret(sample_assessment, allow_fallback=False)

        # Hallucinated keys must be removed
        assert "pe_ratio" not in output.ratio_explanations
        assert "altman_z_score" not in output.ratio_explanations
        assert "current_ratio" in output.ratio_explanations

    def test_negative_equity_trap_defense(self, sample_assessment, valid_llm_json):
        # Inject negative equity into sample assessment
        sample_assessment.ratio_assessments["debt_to_equity"] = RatioAssessment(
            ratio_key="debt_to_equity",
            label="Hệ số nợ/vốn chủ sở hữu",
            category=RatioCategory.LEVERAGE,
            value=None,
            formatted_value="N/A",
            status=AssessmentStatus.UNDEFINED,
            explanation="Vốn chủ sở hữu âm; tỷ số D/E không xác định.",
            warnings=["RỦI RO ĐẶC BIỆT NGHIÊM TRỌNG: Vốn CSH âm"],
            rule_id="RULE_SPECIAL_UNDEFINED",
        )

        # Model attempts to hallucinate strong equity
        valid_llm_json["financial_strengths"].append({
            "strength_title": "Cơ cấu vốn chủ sở hữu dồi dào và an toàn",
            "evidence": "ROE dương giả tạo",
            "significance": "Độ an toàn vốn tốt"
        })

        mock_client = MagicMock()
        mock_client.create_chat_completion.return_value = {
            "content": json.dumps(valid_llm_json, ensure_ascii=False),
            "model": "google/gemma-4-31b-it:free",
            "usage": {},
            "id": "gen-neg-equity",
        }

        interpreter = AIFinancialInterpreter(client=mock_client)
        output = interpreter.interpret(sample_assessment, allow_fallback=False)

        # Hallucinated strength praising equity must be filtered out
        for s in output.financial_strengths:
            title = s.strength_title if isinstance(s, AIStrengthItem) else str(s)
            assert "vốn chủ sở hữu dồi dào" not in title.lower()

    def test_deterministic_fallback_on_network_error(self, sample_assessment):
        mock_client = MagicMock()
        mock_client.create_chat_completion.side_effect = NetworkError("Connection timed out to OpenRouter")

        interpreter = AIFinancialInterpreter(client=mock_client)
        fallback_output = interpreter.interpret(sample_assessment, allow_fallback=True)

        assert isinstance(fallback_output, AIInterpretationOutput)
        assert fallback_output.is_fallback is True
        assert "OpenRouter API Unavailable" in fallback_output.fallback_reason
        assert fallback_output.model_used == "deterministic_rule_engine_v1.0"
        assert "CTCP DƯỢC PHẨM MẪU" in fallback_output.executive_summary
        assert len(fallback_output.financial_risks) == 2
        assert len(fallback_output.recommendations) >= 1
        assert "current_ratio" in fallback_output.ratio_explanations

    def test_deterministic_fallback_on_auth_error(self, sample_assessment):
        mock_client = MagicMock()
        mock_client.create_chat_completion.side_effect = AuthenticationError("Invalid API key")

        interpreter = AIFinancialInterpreter(client=mock_client)
        fallback = interpreter.interpret(sample_assessment, allow_fallback=True)

        assert fallback.is_fallback is True
        assert "AuthenticationError" in fallback.fallback_reason

    def test_deterministic_fallback_on_rate_limit(self, sample_assessment):
        mock_client = MagicMock()
        mock_client.create_chat_completion.side_effect = RateLimitError("HTTP 429 Too Many Requests")

        interpreter = AIFinancialInterpreter(client=mock_client)
        fallback = interpreter.interpret(sample_assessment, allow_fallback=True)

        assert fallback.is_fallback is True
        assert "RateLimitError" in fallback.fallback_reason

    def test_re_raises_error_when_fallback_disabled(self, sample_assessment):
        mock_client = MagicMock()
        mock_client.create_chat_completion.side_effect = ServerError("HTTP 500 Internal Server Error")

        interpreter = AIFinancialInterpreter(client=mock_client)
        with pytest.raises(ServerError):
            interpreter.interpret(sample_assessment, allow_fallback=False)

    def test_ai_models_flexible_risk_coercion(self):
        # Verify that plain string risks are automatically coerced to AIRiskItem objects
        raw_data = {
            "executive_summary": "Tóm tắt...",
            "financial_strengths": ["Biên lợi nhuận dương"],
            "financial_risks": [
                "Thanh khoản ở vùng đệm",
                {"title": "Đòn bẩy ở mức trung bình", "severity": "low"}
            ],
            "recommendations": ["Rà soát dòng tiền"],
            "data_limitations": ["Dữ liệu 1 năm"],
        }
        output = AIInterpretationOutput.model_validate(raw_data)
        assert len(output.financial_risks) == 2
        assert isinstance(output.financial_risks[0], AIRiskItem)
        assert output.financial_risks[0].risk_title == "Thanh khoản ở vùng đệm"
        assert output.financial_risks[1].risk_title == "Đòn bẩy ở mức trung bình"
        assert output.financial_risks[1].severity == "low"

    # =========================================================================
    # Integration with Real CTCP 32 Sample Data (conghuy_A32_2020_sample.txt)
    # =========================================================================
    def test_integration_with_ctcp32_real_sample(self):
        from pathlib import Path
        sample_path = Path("data/samples/conghuy_A32_2020_sample.txt")
        if not sample_path.is_file():
            pytest.skip("Sample file not present in data/samples")
        content = sample_path.read_text(encoding="utf-8")

        # Step 1: Parse
        parser = FinancialStatementParser()
        report = parser.parse(content, source_name="conghuy_A32_2020_sample.txt")

        # Step 2: Calculate 14 ratios
        calc = FinancialRatioCalculator()
        ratio_report = calc.calculate_all(report)

        # Step 3: Assess with rule engine
        assessor = FinancialHealthAssessor()
        assessment = assessor.assess(ratio_report)

        assert assessment.company_name == "CÔNG TY CỔ PHẦN 32"
        assert assessment.fiscal_year == 2020
        assert assessment.watch_count == 6
        assert len(assessment.warnings) == 6

        # Step 4: Build AI interpretation prompts
        interpreter = AIFinancialInterpreter(client=MagicMock())
        sys_p, user_p = interpreter.build_prompts(assessment)

        # Verify that 4 core ratios are present in user prompt without pre-configured commentary
        assert "CÔNG TY CỔ PHẦN 32" in user_p
        assert "2020" in user_p
        assert "current_ratio" in user_p
        assert "1.45 lần" in user_p
        assert "debt_to_equity" in user_p
        assert "1.02 lần" in user_p
        assert "roa" in user_p
        assert "roe" in user_p

        # Step 5: Test deterministic fallback on the real sample
        fallback_output = interpreter.generate_deterministic_fallback(
            assessment=assessment,
            error_reason="Test deterministic fallback generation for CTCP 32",
        )

        assert fallback_output.is_fallback is True
        assert "CÔNG TY CỔ PHẦN 32" in fallback_output.executive_summary
        assert len(fallback_output.financial_risks) == 6
        assert len(fallback_output.ratio_explanations) == 14
        assert len(fallback_output.recommendations) >= 2
