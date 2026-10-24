"""Unit and integration tests for UI export utilities and pipeline execution (Sprint 6)."""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app import execute_pipeline
from src.data.parser import FinancialStatementParser
from src.data.schema import FinancialReport, ValidationCheck, ValidationResult, CheckStatus
from src.financial.ai_models import AIInterpretationOutput, AIRiskItem, AIStrengthItem
from src.financial.assessment import FinancialHealthAssessor
from src.financial.assessment_models import (
    AssessmentStatus,
    FinancialAssessment,
    FinancialWarning,
    OverallHealthStatus,
    RatioAssessment,
    WarningCategory,
    WarningSeverity,
)
from src.financial.ratios import FinancialRatioCalculator, RatioCategory
from src.ui.export import (
    export_analysis_to_json,
    export_ratios_to_csv,
    export_warnings_to_csv,
)


@pytest.fixture
def mock_assessment() -> FinancialAssessment:
    """Fixture providing a mock FinancialAssessment with evaluated ratios and warnings."""
    ratios = {
        "current_ratio": RatioAssessment(
            ratio_key="current_ratio",
            label="Hệ số thanh toán hiện hành",
            category=RatioCategory.LIQUIDITY,
            value=Decimal("1.45"),
            formatted_value="1.45 lần",
            status=AssessmentStatus.WATCH,
            explanation="Nằm trong vùng đệm theo dõi.",
            warnings=["Biên an toàn thanh khoản mỏng"],
            rule_id="RULE_LIQ_CURRENT_RATIO_WATCH",
            limitations=["Chưa tính tính mùa vụ"],
        ),
        "debt_to_assets": RatioAssessment(
            ratio_key="debt_to_assets",
            label="Hệ số nợ trên tài sản",
            category=RatioCategory.LEVERAGE,
            value=Decimal("0.63"),
            formatted_value="63.00%",
            status=AssessmentStatus.WATCH,
            explanation="Đòn bẩy ở mức trung bình.",
            rule_id="RULE_LEV_DEBT_TO_ASSETS_WATCH",
        ),
        "undefined_ratio": RatioAssessment(
            ratio_key="undefined_ratio",
            label="Chỉ số chưa xác định",
            category=RatioCategory.PROFITABILITY,
            value=None,
            formatted_value="N/A",
            status=AssessmentStatus.UNDEFINED,
            explanation="Không xác định do âm vốn CSH.",
        ),
    }

    warnings = [
        FinancialWarning(
            code="LIQUIDITY_CURRENT_RATIO_WATCH",
            category=WarningCategory.LIQUIDITY,
            severity=WarningSeverity.LOW,
            title="Theo dõi thanh khoản",
            message="Biên an toàn thanh khoản mỏng.",
            related_ratios=["current_ratio"],
            evidence="current_ratio = 1.45 lần",
            recommendation="Theo dõi hạn mức tín dụng dự phòng.",
        ),
        FinancialWarning(
            code="LEVERAGE_HIGH",
            category=WarningCategory.LEVERAGE,
            severity=WarningSeverity.HIGH,
            title="Đòn bẩy cao",
            message="Nợ chiếm tỷ trọng đáng kể.",
            evidence="debt_to_assets = 63%",
            recommendation="Rà soát nghĩa vụ nợ đến hạn.",
        ),
    ]

    return FinancialAssessment(
        company_name="CTCP Dệt May Thử Nghiệm",
        fiscal_year=2020,
        currency="VND",
        overall_status=OverallHealthStatus.MIXED,
        ratio_assessments=ratios,
        warnings=warnings,
        category_overviews={
            "liquidity": "Thanh khoản ở mức trung bình",
            "leverage": "Đòn bẩy ở mức cao",
        },
        key_findings=["Khả năng sinh lời dương", "Đòn bẩy tài chính cần theo dõi"],
        limitations=["Dữ liệu đơn kỳ"],
        total_ratios_evaluated=3,
        calculated_count=2,
        alert_count=0,
        watch_count=2,
    )


@pytest.fixture
def mock_ai_output() -> AIInterpretationOutput:
    """Fixture providing a mock AIInterpretationOutput."""
    return AIInterpretationOutput(
        executive_summary="Doanh nghiệp hoạt động có lãi nhưng áp lực nợ ngắn hạn cần theo dõi.",
        financial_strengths=[
            AIStrengthItem(
                strength_title="Biên lợi nhuận dương",
                evidence="NPM đạt 2.5%",
                significance="Duy trì được thặng dư",
            ),
            "Kiểm soát chi phí tốt",
        ],
        financial_risks=[
            AIRiskItem(
                risk_title="Đòn bẩy nợ tăng",
                severity="high",
                evidence="D/A = 63%",
                implication="Áp lực trả nợ lớn",
                related_ratios=["debt_to_assets"],
            )
        ],
        recommendations=["Cơ cấu lại kỳ hạn nợ", "Đẩy nhanh thu hồi công nợ"],
        data_limitations=["Chưa có benchmark ngành"],
        is_fallback=True,
        fallback_reason="Chưa cấu hình API Key OpenRouter",
        model_used="google/gemma-4-31b-it:free",
    )


class TestExportLogic:
    """Test JSON and CSV export serializers."""

    def test_export_analysis_to_json_valid_and_complete(self, mock_assessment, mock_ai_output):
        json_str = export_analysis_to_json(mock_assessment, mock_ai_output)
        data = json.loads(json_str)

        # Validate top-level keys
        assert "metadata" in data
        assert data["metadata"]["company_name"] == "CTCP Dệt May Thử Nghiệm"
        assert data["metadata"]["fiscal_year"] == 2020

        # Validate overall health
        assert data["overall_health"]["status"] == "mixed"
        assert len(data["ratios"]) == 3
        assert len(data["warnings"]) == 2

        # Validate ratios numeric handling
        cr_item = next(r for r in data["ratios"] if r["ratio_key"] == "current_ratio")
        assert cr_item["value"] == 1.45
        assert isinstance(cr_item["value"], float)

        # Validate None value handling
        undef_item = next(r for r in data["ratios"] if r["ratio_key"] == "undefined_ratio")
        assert undef_item["value"] is None
        assert undef_item["formatted_value"] == "N/A"

        # Validate AI section
        assert "ai_interpretation" in data
        assert data["ai_interpretation"]["is_fallback"] is True
        assert data["ai_interpretation"]["model_used"] == "google/gemma-4-31b-it:free"

    def test_export_analysis_to_json_with_none_fields(self):
        sparse_assessment = FinancialAssessment(
            company_name=None,
            fiscal_year=None,
            overall_status=OverallHealthStatus.INSUFFICIENT_DATA,
        )
        json_str = export_analysis_to_json(sparse_assessment, ai_output=None, report=None)
        data = json.loads(json_str)

        assert data["metadata"]["company_name"] == "Chưa xác định"
        assert data["metadata"]["fiscal_year"] is None
        assert data["overall_health"]["status"] == "insufficient_data"
        assert "ai_interpretation" not in data
        assert "statement_validation" not in data

    def test_export_ratios_to_csv(self, mock_assessment):
        csv_str = export_ratios_to_csv(mock_assessment)
        lines = [line.strip() for line in csv_str.strip().split("\n")]

        # Header + 3 ratios = 4 lines
        assert len(lines) == 4
        assert "Mã chỉ số" in lines[0]
        assert "Hệ số thanh toán hiện hành" in csv_str
        assert "1.45" in csv_str
        assert "Chỉ số chưa xác định" in csv_str

    def test_export_warnings_to_csv(self, mock_assessment):
        csv_str = export_warnings_to_csv(mock_assessment)
        lines = [line.strip() for line in csv_str.strip().split("\n")]

        # Header + 2 warnings = 3 lines
        assert len(lines) == 3
        assert "Mã cảnh báo" in lines[0]
        assert "LIQUIDITY_CURRENT_RATIO_WATCH" in csv_str
        assert "LEVERAGE_HIGH" in csv_str


class TestPipelineExecution:
    """Test pipeline execution error handling and integration."""

    def test_execute_pipeline_empty_txt_file(self):
        report, assessment, ai_output, err = execute_pipeline(
            file_bytes=b"   ", file_name="empty.txt"
        )
        assert report is None
        assert assessment is None
        assert "rỗng" in err

    def test_execute_pipeline_corrupt_pdf(self):
        report, assessment, ai_output, err = execute_pipeline(
            file_bytes=b"not_a_valid_pdf_content", file_name="corrupt.pdf"
        )
        assert assessment is None
        assert "thất bại" in err.lower() or "lỗi" in err.lower()

    def test_execute_pipeline_sample_integration(self):
        sample_path = Path("data/samples/conghuy_A32_2020_sample.txt")
        if not sample_path.exists():
            pytest.skip("Sample file not present in data/samples")

        file_bytes = sample_path.read_bytes()

        # Run pipeline with deterministic fallback (without real API calls)
        report, assessment, ai_output, method = execute_pipeline(
            file_bytes=file_bytes,
            file_name=sample_path.name,
            period="current",
            enable_ai=True,
        )

        assert report is not None
        assert assessment is not None
        assert ai_output is not None
        assert "Văn bản mẫu" in method

        # Company metadata & year
        assert assessment.fiscal_year == 2020
        assert "32" in (assessment.company_name or "")

        # 14 ratios evaluated
        assert len(assessment.ratio_assessments) == 14
        assert assessment.get_assessment("current_ratio") is not None
        assert assessment.get_assessment("debt_to_assets") is not None

        # Validation check present
        assert report.validation_results is not None
        assert report.validation_results.total_checks > 0


class TestStreamlitAppLaunch:
    """Test native Streamlit AppTest execution."""

    def test_streamlit_app_renders_and_runs_cleanly(self):
        """Verify app.py loads, renders sidebar, and executes analysis without exception."""
        from streamlit.testing.v1 import AppTest

        app_path = Path(__file__).resolve().parent.parent.parent / "app.py"
        at = AppTest.from_file(str(app_path))
        at.run()
        assert not at.exception

        # Click the analyze button (index 0)
        at.button[0].click().run()
        assert not at.exception

    def test_app_starts_without_data_directory(self):
        """Verify get_available_sample_options works cleanly when data/ is absent."""
        from unittest.mock import patch
        from app import get_available_sample_options
        with patch("pathlib.Path.is_file", return_value=False):
            options = get_available_sample_options()
            assert isinstance(options, dict)
            assert len(options) == 0

    def test_in_memory_upload_no_file_retention(self):
        """Verify uploaded documents are processed purely in-memory with zero file retention."""
        import os
        before_files = set(os.listdir(os.getcwd()))

        sample_path = Path("data/samples/conghuy_A32_2020_sample.txt")
        if sample_path.is_file():
            file_bytes = sample_path.read_bytes()
            report, assessment, ai_output, method = execute_pipeline(
                file_bytes=file_bytes,
                file_name="user_upload_test.txt",
                period="current",
                enable_ai=False,
            )
            assert report is not None
            assert assessment is not None

        after_files = set(os.listdir(os.getcwd()))
        # Ensure no temporary file or uploaded document was persisted in the working directory
        new_files = after_files - before_files
        assert not any("user_upload_test" in f for f in new_files)
