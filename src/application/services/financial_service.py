"""Dịch vụ ứng dụng phân tích tài chính điều phối kiểm tra cân đối, tính toán tỷ số và đánh giá sức khỏe.

Module này đóng vai trò dịch vụ điều phối trung tâm (Application Service) cho toàn bộ
quy trình phân tích tài chính: từ kiểm tra các hằng đẳng thức kế toán Thông tư 200,
tính toán 14 chỉ số tài chính chuẩn mực với độ chính xác số học Decimal, đến áp dụng
bộ quy tắc sàng lọc phân loại sức khỏe tài chính và cảnh báo rủi ro.
"""
from typing import Optional, Tuple

from src.domain.accounting.validator import FinancialValidator
from src.domain.assessment.evaluator import FinancialHealthAssessor
from src.domain.models.assessment import FinancialAssessment
from src.domain.models.bctc import FinancialReport, ValidationResult
from src.domain.models.ratios import FinancialRatioReport
from src.domain.ratios.engine import FinancialRatioCalculator


class FinancialAnalysisService:
    """Điều phối kiểm tra tính cân đối kế toán TT200, tính toán tỷ số và sàng lọc sức khỏe tài chính.

    Attributes:
        validator (FinancialValidator): Đối tượng kiểm tra tính cân đối kế toán.
        calculator (FinancialRatioCalculator): Động cơ tính toán 14 chỉ số tài chính.
        assessor (FinancialHealthAssessor): Động cơ đánh giá phân loại và cảnh báo rủi ro.
    """

    def __init__(
        self,
        validator: Optional[FinancialValidator] = None,
        calculator: Optional[FinancialRatioCalculator] = None,
        assessor: Optional[FinancialHealthAssessor] = None,
    ) -> None:
        """Khởi tạo dịch vụ phân tích tài chính với các thành phần phụ thuộc.

        Args:
            validator (Optional[FinancialValidator]): Trình kiểm tra cân đối kế toán (nếu None sẽ dùng mặc định).
            calculator (Optional[FinancialRatioCalculator]): Trình tính tỷ số tài chính (nếu None sẽ dùng mặc định).
            assessor (Optional[FinancialHealthAssessor]): Trình đánh giá sức khỏe tài chính (nếu None sẽ dùng mặc định).
        """
        self.validator: FinancialValidator = validator or FinancialValidator()
        self.calculator: FinancialRatioCalculator = calculator or FinancialRatioCalculator()
        self.assessor: FinancialHealthAssessor = assessor or FinancialHealthAssessor()

    def validate_statements(
        self, report: FinancialReport, period: str = "current"
    ) -> ValidationResult:
        """Thực hiện kiểm tra 4 hằng đẳng thức cân đối kế toán theo quy định Thông tư 200/2014/TT-BTC.

        Args:
            report (FinancialReport): Báo cáo tài chính chứa Bảng CĐKT và Báo cáo KQKD.
            period (str): Kỳ báo cáo cần kiểm tra ("current" cho kỳ này, "previous" cho kỳ trước).

        Returns:
            ValidationResult: Kết quả kiểm tra gồm các phép kiểm tra đạt/không đạt và sai lệch số học.
        """
        result = self.validator.validate(report, period=period)
        report.validation_results = result
        return result

    def calculate_ratios(
        self, report: FinancialReport, period: str = "current"
    ) -> FinancialRatioReport:
        """Tính toán toàn bộ 14 chỉ số tài chính cốt lõi với độ chính xác số học Decimal.

        Args:
            report (FinancialReport): Báo cáo tài chính chứa dữ liệu các chỉ tiêu.
            period (str): Kỳ kế toán cần tính toán ("current" hoặc "previous").

        Returns:
            FinancialRatioReport: Báo cáo tỷ số tài chính gồm 4 nhóm: Thanh khoản, Cơ cấu vốn,
                Hiệu quả hoạt động, và Khả năng sinh lời.
        """
        return self.calculator.calculate_all(report, period=period)

    def assess_health(
        self, ratio_report: FinancialRatioReport
    ) -> FinancialAssessment:
        """Đánh giá 14 chỉ số tài chính theo bộ ngưỡng sàng lọc và phát sinh các cảnh báo rủi ro.

        Args:
            ratio_report (FinancialRatioReport): Báo cáo tỷ số tài chính đã tính toán.

        Returns:
            FinancialAssessment: Kết quả đánh giá sức khỏe tài chính tổng thể, phân loại từng chỉ số,
                danh sách điểm mạnh, rủi ro xếp theo mức độ nghiêm trọng và khuyến nghị quản trị.
        """
        return self.assessor.assess(ratio_report)

    def analyze(
        self, report: FinancialReport, period: str = "current"
    ) -> Tuple[ValidationResult, FinancialRatioReport, FinancialAssessment]:
        """Thực hiện quy trình phân tích tài chính toàn diện đầu-cuối (end-to-end).

        Quy trình bao gồm 3 bước tuần tự:
        1. Kiểm tra tính cân đối kế toán (validate_statements).
        2. Tính toán 14 tỷ số tài chính (calculate_ratios).
        3. Đánh giá sức khỏe tài chính và phân loại rủi ro (assess_health).

        Args:
            report (FinancialReport): Báo cáo tài chính đầu vào.
            period (str): Kỳ báo cáo phân tích ("current" hoặc "previous").

        Returns:
            Tuple[ValidationResult, FinancialRatioReport, FinancialAssessment]:
                Bộ 3 kết quả: (Kết quả kiểm tra cân đối, Báo cáo tỷ số, Đánh giá sức khỏe tài chính).
        """
        validation_res = self.validate_statements(report, period=period)
        ratio_report = self.calculate_ratios(report, period=period)
        assessment = self.assess_health(ratio_report)
        return validation_res, ratio_report, assessment
