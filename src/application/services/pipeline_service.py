"""Dịch vụ điều phối đường ống phân tích tài chính đầu-cuối (Analysis Pipeline Service).

Đóng vai trò là Use Case Orchestrator trung tâm của Tầng Application:
- Tiếp nhận luồng byte tệp trực tiếp trong RAM (Zero File Retention).
- Phối hợp: Trích xuất PDF/OCR ➔ Bóc tách bảng BCTC TT200 ➔ Kiểm định 4 đẳng thức ➔
  Tính 14 tỷ số Decimal ➔ Thẩm định sức khỏe doanh nghiệp ➔ Nhận định AI độc lập.
- Cung cấp giao diện thực thi mạch lạc cho Presentation Controller và kiểm thử tích hợp.
"""
import logging
from typing import Optional, Tuple

from src.application.interfaces.pdf import IDocumentExtractor
from src.application.services.ai_service import AIInterpretationService
from src.application.services.financial_service import FinancialAnalysisService
from src.application.services.parsing_service import FinancialStatementParser
from src.domain.models.ai import AIInterpretationOutput
from src.domain.models.assessment import FinancialAssessment
from src.domain.models.bctc import FinancialReport
from src.domain.models.ocr import DocumentExtractionResult
from src.domain.models.ratios import FinancialRatioReport

logger = logging.getLogger(__name__)


class AnalysisPipelineService:
    """Dịch vụ điều phối toàn bộ đường ống phân tích Báo cáo tài chính E2E.

    Attributes:
        extractor (Optional[IDocumentExtractor]): Bộ trích xuất tài liệu PDF/Scan.
        parser (FinancialStatementParser): Bộ phân tích cú pháp cấu trúc bảng BCTC.
        analysis_service (FinancialAnalysisService): Bộ tính toán tỷ số và kiểm định kế toán.
        ai_service (AIInterpretationService): Dịch vụ tạo nhận định thông minh bằng AI.
    """

    def __init__(
        self,
        extractor: Optional[IDocumentExtractor] = None,
        parser: Optional[FinancialStatementParser] = None,
        analysis_service: Optional[FinancialAnalysisService] = None,
        ai_service: Optional[AIInterpretationService] = None,
    ):
        """Khởi tạo dịch vụ đường ống với các dependencies cần thiết.

        Args:
            extractor (Optional[IDocumentExtractor]): Bộ trích xuất tài liệu (nếu None sẽ tải trễ).
            parser (Optional[FinancialStatementParser]): Bộ phân tích bảng (mặc định tạo mới).
            analysis_service (Optional[FinancialAnalysisService]): Bộ phân tích tài chính.
            ai_service (Optional[AIInterpretationService]): Dịch vụ nhận định AI.
        """
        self.extractor = extractor
        self.parser = parser or FinancialStatementParser()
        self.analysis_service = analysis_service or FinancialAnalysisService()
        self.ai_service = ai_service or AIInterpretationService()

    def _get_extractor(self) -> IDocumentExtractor:
        """Khởi tạo trễ (Lazy Loading) bộ trích xuất PDFExtractor nếu chưa được tiêm phụ thuộc.

        Returns:
            IDocumentExtractor: Thể hiện của bộ trích xuất tài liệu sẵn sàng làm việc.
        """
        if self.extractor is None:
            from src.infrastructure.pdf.extractor import PDFExtractor
            self.extractor = PDFExtractor(extract_tables=False)
        return self.extractor

    def extract_financial_report(
        self,
        file_bytes: Optional[bytes],
        file_name: str,
        period: str = "current",
    ) -> Tuple[Optional[FinancialReport], Optional[str]]:
        """Bước 1: Trích xuất nội dung văn bản/OCR, cấu trúc hóa BCTC và kiểm định cân đối TT200.

        Xử lý hoàn toàn trong bộ nhớ RAM từ chuỗi file_bytes, không ghi file ra ổ đĩa.

        Args:
            file_bytes (Optional[bytes]): Dữ liệu tệp tải lên dưới dạng byte trong RAM.
            file_name (str): Tên tệp (hỗ trợ .pdf, .txt).
            period (str): Kỳ phân tích ('current' hoặc 'previous').

        Returns:
            Tuple[Optional[FinancialReport], Optional[str]]:
                (Báo cáo tài chính đã bóc tách và kiểm định, Phương thức trích xuất hoặc thông báo lỗi).
        """
        extraction_method = "Trích xuất văn bản"

        # Phân nhánh xử lý tệp văn bản mẫu .txt
        if file_name.lower().endswith(".txt"):
            extraction_method = "Văn bản mẫu có cấu trúc"
            text_content = file_bytes.decode("utf-8", errors="replace") if file_bytes else ""
            if not text_content.strip():
                return None, "Tệp văn bản tải lên rỗng."
            report = self.parser.parse(text_content, source_name=file_name)
        else:
            # Xử lý tệp PDF / Ảnh quét qua bộ trích xuất định tuyến thông minh
            extractor = self._get_extractor()
            try:
                extraction_result: DocumentExtractionResult = extractor.extract(
                    file_input=file_bytes or b"", source_name=file_name
                )
            except Exception as exc:
                return None, f"Lỗi trong quá trình trích xuất tài liệu: {exc}"

            if not extraction_result.success:
                err_msg = (
                    " | ".join(extraction_result.errors)
                    if extraction_result.errors
                    else "Không trích xuất được nội dung"
                )
                return None, f"Trích xuất thất bại: {err_msg}"

            if not extraction_result.full_text.strip():
                return None, "Không tìm thấy nội dung văn bản trong tài liệu tải lên."

            extraction_method = "PDF / OCR Hybrid"
            report = self.parser.parse(extraction_result, source_name=file_name)

        # Chạy kiểm định 4 đẳng thức cân đối kế toán ban đầu
        validation_summary = self.analysis_service.validate_statements(report, period=period)
        report.validation_results = validation_summary

        has_bs_items = bool(report.balance_sheet and report.balance_sheet.items)
        has_is_items = bool(report.income_statement and report.income_statement.items)
        if not has_bs_items and not has_is_items:
            return report, "Không nhận diện được các chỉ tiêu Bảng Cân đối kế toán hoặc Kết quả kinh doanh."

        return report, extraction_method

    def calculate_assessment_and_ai(
        self,
        report: FinancialReport,
        period: str = "current",
        enable_ai: bool = True,
    ) -> Tuple[FinancialRatioReport, FinancialAssessment, Optional[AIInterpretationOutput]]:
        """Bước 2: Tính toán 14 tỷ số tài chính Decimal, thẩm định rủi ro và tạo nhận định AI.

        Args:
            report (FinancialReport): BCTC đã qua bóc tách ở Bước 1.
            period (str): Kỳ phân tích ('current' hoặc 'previous').
            enable_ai (bool): Cho phép gọi API OpenRouter để tạo nhận định chuyên sâu.

        Returns:
            Tuple[FinancialRatioReport, FinancialAssessment, Optional[AIInterpretationOutput]]:
                (Báo cáo 14 tỷ số, Báo cáo đánh giá rủi ro rule-based, Báo cáo nhận định chuyên sâu AI).
        """
        ratio_report = self.analysis_service.calculate_ratios(report, period=period)
        assessment = self.analysis_service.assess_health(ratio_report)

        ai_output = None
        if enable_ai:
            try:
                ai_output = self.ai_service.interpret(
                    assessment=assessment,
                    ratio_report=ratio_report,
                    allow_fallback=True,
                )
            except Exception as exc:
                logger.warning("Lỗi nhận định AI qua OpenRouter: %s", exc)
                ai_output = None

        return ratio_report, assessment, ai_output

    def execute_pipeline(
        self,
        file_bytes: Optional[bytes],
        file_name: str,
        period: str = "current",
        enable_ai: bool = True,
    ) -> Tuple[Optional[FinancialReport], Optional[FinancialAssessment], Optional[AIInterpretationOutput], Optional[str]]:
        """Thực thi trọn vẹn quy trình phân tích BCTC đầu-cuối (Hợp nhất Bước 1 và Bước 2).

        Args:
            file_bytes (Optional[bytes]): Dữ liệu tệp nhị phân trong bộ nhớ RAM.
            file_name (str): Tên tệp tài liệu.
            period (str): Kỳ báo cáo ('current' hoặc 'previous').
            enable_ai (bool): Cờ bật/tắt nhận định điều hành bằng AI.

        Returns:
            Tuple[Optional[FinancialReport], Optional[FinancialAssessment], Optional[AIInterpretationOutput], Optional[str]]:
                (Báo cáo tài chính BCTC, Đánh giá sức khỏe, Nhận định AI, Phương thức xử lý hoặc thông báo lỗi).
        """
        report, method_or_err = self.extract_financial_report(file_bytes, file_name, period=period)
        if report is None:
            return None, None, None, method_or_err

        has_bs_items = bool(report.balance_sheet and report.balance_sheet.items)
        has_is_items = bool(report.income_statement and report.income_statement.items)
        if not has_bs_items and not has_is_items:
            return report, None, None, method_or_err

        ratio_report, assessment, ai_output = self.calculate_assessment_and_ai(
            report, period=period, enable_ai=enable_ai
        )
        return report, assessment, ai_output, method_or_err
