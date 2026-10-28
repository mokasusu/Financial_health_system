"""Nhà máy dịch vụ (Service Factory) phục vụ tiêm phụ thuộc (Dependency Injection).

Module này triển khai mẫu thiết kế Factory Pattern cho toàn bộ tầng hạ tầng (Infrastructure)
và tầng ứng dụng (Application), cho phép khởi tạo lười (lazy loading) các máy khách AI,
động cơ trích xuất OCR PaddleOCR đơn phiên bản (singleton), bộ bóc tách PDF 3 tuyến,
dịch vụ phân tích tài chính TT200 và chuỗi đường ống hợp nhất (AnalysisPipelineService).
"""
from typing import TYPE_CHECKING, Optional

from src.infrastructure.ocr.paddle_engine import PaddleOCREngine, get_shared_paddle_engine
from src.infrastructure.pdf.extractor import PDFExtractor

if TYPE_CHECKING:
    from src.application.services.ai_service import AIInterpretationService
    from src.application.services.financial_service import FinancialAnalysisService
    from src.application.services.parsing_service import FinancialStatementParser
    from src.application.services.pipeline_service import AnalysisPipelineService
    from src.infrastructure.ai.client import OpenRouterClient, OpenRouterConfig


class ServiceFactory:
    """Nhà máy Dependency Injection thủ công khởi tạo và liên kết các dịch vụ hệ thống."""

    @staticmethod
    def create_ocr_engine(
        use_gpu: bool = True,
        lang: str = "vi",
        enable_layout: bool = True,
        use_table_recognition: bool = False,
    ) -> PaddleOCREngine:
        """Khởi tạo hoặc tái sử dụng phiên bản dùng chung (singleton) của động cơ PaddleOCREngine.

        Args:
            use_gpu (bool): Cho phép tận dụng GPU CUDA nếu khả dụng (tự động chuyển CPU nếu không có CUDA).
            lang (str): Mã ngôn ngữ nhận diện OCR (mặc định 'vi' cho Tiếng Việt).
            enable_layout (bool): Kích hoạt phân tích bố cục PP-Structure để lọc nhiễu.
            use_table_recognition (bool): Tải mô hình nhận diện ô bảng (mặc định False để tiết kiệm VRAM).

        Returns:
            PaddleOCREngine: Phiên bản động cơ OCR đã cấu hình.
        """
        return get_shared_paddle_engine(
            use_gpu=use_gpu,
            lang=lang,
            enable_layout=enable_layout,
            use_table_recognition=use_table_recognition,
        )

    @staticmethod
    def create_pdf_extractor(
        extract_tables: bool = False,
        paddle_engine: Optional[PaddleOCREngine] = None,
        ocr_engine: Optional[PaddleOCREngine] = None,
    ) -> PDFExtractor:
        """Khởi tạo bộ bóc tách tài liệu PDFExtractor kèm động cơ OCR tích hợp.

        Args:
            extract_tables (bool): Cho phép bóc tách bảng biểu cấu trúc bằng pdfplumber.
            paddle_engine (Optional[PaddleOCREngine]): Động cơ PaddleOCREngine tùy chỉnh.
            ocr_engine (Optional[PaddleOCREngine]): Bí danh tương thích cho paddle_engine.

        Returns:
            PDFExtractor: Trình bóc tách PDF 3 tuyến (Native vector, Scanned OCR, Mixed hybrid).
        """
        engine = paddle_engine or ocr_engine
        return PDFExtractor(
            extract_tables=extract_tables,
            paddle_engine=engine,
        )

    @staticmethod
    def create_ai_client(
        config: Optional["OpenRouterConfig"] = None,
    ) -> "OpenRouterClient":
        """Khởi tạo máy khách OpenRouterClient từ biến môi trường hoặc cấu hình chỉ định.

        Args:
            config (Optional[OpenRouterConfig]): Đối tượng cấu hình tùy chỉnh (nếu None sẽ đọc từ .env).

        Returns:
            OpenRouterClient: Máy khách gọi API OpenRouter.
        """
        from src.infrastructure.ai.client import OpenRouterClient
        return OpenRouterClient(config=config)

    @staticmethod
    def create_parsing_service(
        decimal_convention: str = "auto",
    ) -> "FinancialStatementParser":
        """Khởi tạo dịch vụ phân tích cú pháp chỉ tiêu BCTC Thông tư 200.

        Args:
            decimal_convention (str): Quy ước dấu phân cách số ("auto", "vietnamese", "international").

        Returns:
            FinancialStatementParser: Trình phân tích cú pháp và ánh xạ ngữ nghĩa BCTC.
        """
        from src.application.services.parsing_service import FinancialStatementParser
        return FinancialStatementParser(decimal_convention=decimal_convention)

    @staticmethod
    def create_financial_service() -> "FinancialAnalysisService":
        """Khởi tạo dịch vụ kiểm tra cân đối TT200, tính 14 tỷ số và đánh giá sức khỏe tài chính.

        Returns:
            FinancialAnalysisService: Dịch vụ phân tích tài chính nghiệp vụ.
        """
        from src.application.services.financial_service import FinancialAnalysisService
        return FinancialAnalysisService()

    @staticmethod
    def create_ai_service(
        client: Optional["OpenRouterClient"] = None,
    ) -> "AIInterpretationService":
        """Khởi tạo dịch vụ diễn giải tài chính AI với máy khách kết nối.

        Args:
            client (Optional[OpenRouterClient]): Máy khách AI đã cấu hình.

        Returns:
            AIInterpretationService: Dịch vụ diễn giải báo cáo qua AI.
        """
        from src.application.services.ai_service import AIInterpretationService
        return AIInterpretationService(client=client)

    @classmethod
    def create_pipeline_service(
        cls,
        extract_tables: bool = False,
        decimal_convention: str = "auto",
    ) -> "AnalysisPipelineService":
        """Lắp ráp dịch vụ đường ống xử lý hoàn chỉnh (AnalysisPipelineService) với đầy đủ thành phần phụ thuộc.

        Args:
            extract_tables (bool): Tùy chọn trích xuất bảng cấu trúc.
            decimal_convention (str): Quy ước dấu phân cách số ("auto").

        Returns:
            AnalysisPipelineService: Dịch vụ đường ống đầu-cuối từ tệp PDF/ảnh tới báo cáo tổng thể.
        """
        from src.application.services.pipeline_service import AnalysisPipelineService

        # Khởi tạo các thành phần phụ thuộc theo cấu hình
        extractor = cls.create_pdf_extractor(extract_tables=extract_tables)
        parser = cls.create_parsing_service(decimal_convention=decimal_convention)
        analysis_service = cls.create_financial_service()
        ai_service = cls.create_ai_service()

        return AnalysisPipelineService(
            extractor=extractor,
            parser=parser,
            analysis_service=analysis_service,
            ai_service=ai_service,
        )
