"""Mô hình dữ liệu trích xuất văn bản và cấu trúc Layout từ tài liệu PDF / OCR.

Module này cung cấp các thực thể lưu trữ kết quả phân tích tài liệu:
- Phương thức trích xuất (ExtractionMethod: NATIVE_TEXT, PADDLE_OCR, HYBRID...)
- Trạng thái phân giải trang (ExtractionStatus: COMPLETE, PARTIAL, EMPTY, FAILED)
- Vùng Layout trên trang (LayoutRegion: text, title, table, figure, header, footer)
- Kết quả trích xuất từng trang (PageExtractionResult) và toàn bộ tài liệu (DocumentExtractionResult).
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    """Phương thức kỹ thuật được áp dụng để trích xuất nội dung từ trang tài liệu.

    Attributes:
        NATIVE_TEXT: Trích xuất trực tiếp văn bản số (Native text) qua PyMuPDF/pdfplumber.
        PADDLE_OCR: Trích xuất bằng mô hình PaddleOCR GPU/CPU cho trang quét hình ảnh.
        HYBRID: Kết hợp trích xuất văn bản số và OCR trên cùng một trang.
        OCR: Nhãn tương thích ngược cho các trang dùng OCR.
        EMPTY: Trang hoàn toàn trắng hoặc không chứa dữ liệu ký tự.
        FAILED: Xảy ra lỗi ngoại lệ trong quá trình xử lý trang.
    """
    NATIVE_TEXT = "native_text"
    PADDLE_OCR = "paddle_ocr"
    HYBRID = "hybrid"
    OCR = "ocr"  # Duy trì tương thích ngược
    EMPTY = "empty"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    """Trạng thái ngữ nghĩa thể hiện mức độ hoàn thiện của quá trình trích xuất.

    Attributes:
        COMPLETE: Trích xuất trọn vẹn, độ tin cậy cao, không có lỗi hoặc cảnh báo.
        PARTIAL: Trích xuất một phần, có cảnh báo chất lượng hoặc độ tin cậy thấp.
        EMPTY: Không có nội dung ký tự nào được tìm thấy.
        FAILED: Xử lý thất bại hoàn toàn.
    """
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"
    FAILED = "failed"


class LayoutRegion(BaseModel):
    """Vùng cấu trúc hình học (Layout Region) được phát hiện trên trang tài liệu.

    Attributes:
        region_type (str): Phân loại vùng ('text', 'title', 'table', 'figure', 'header', 'footer').
        bbox (Tuple[int, int, int, int]): Tọa độ khung bao giới hạn (x1, y1, x2, y2).
        confidence (float): Độ tin cậy nhận diện vùng của mô hình thị giác (0.0 đến 1.0).
        text (str): Nội dung văn bản OCR trích xuất được trong vùng này.
        html (str): Cấu trúc bảng dạng HTML (nếu là vùng bảng biểu 'table').
        included (bool): True nếu vùng được giữ lại xử lý tiếp; False nếu bị lọc bỏ (header/footer nhiễu).
        source_method (Optional[str]): Công cụ hoặc thuật toán phát hiện (VD: 'pp_structure').
        needs_review (bool): Cờ đánh dấu vùng có dấu hiệu nghi ngờ cần người dùng kiểm tra lại.
        review_reason (Optional[str]): Lý do cụ thể đánh dấu cần đối soát lại.
    """
    region_type: str = Field(description="Loại vùng: text, title, table, figure, header, footer, v.v.")
    bbox: Tuple[int, int, int, int] = Field(description="(x1, y1, x2, y2) bounding box coordinates")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ tin cậy của vùng (0.0 - 1.0)")
    text: str = Field(default="", description="Text OCR (cho vùng text/title)")
    html: str = Field(default="", description="HTML representation (cho vùng table)")
    included: bool = Field(default=True, description="False nếu bị lọc bỏ (header, footer, figure, logo)")
    source_method: Optional[str] = Field(default=None, description="Phương pháp/engine phát hiện (pp_structure, fallback_crop, v.v.)")
    needs_review: bool = Field(default=False, description="Cờ đánh dấu vùng cần người dùng xem xét/kiểm tra lại")
    review_reason: Optional[str] = Field(default=None, description="Lý do đánh dấu cần kiểm tra")


class PageExtractionResult(BaseModel):
    """Kết quả trích xuất toàn diện của một trang tài liệu đơn lẻ.

    Attributes:
        source_name (str): Tên tệp hoặc định danh của tài liệu nguồn.
        page_number (int): Số thứ tự trang (đánh chỉ mục bắt đầu từ 1).
        text (str): Toàn bộ nội dung văn bản trích xuất được từ trang.
        extraction_method (str): Phương thức trích xuất đã dùng (native_text, paddle_ocr...).
        status (ExtractionStatus): Trạng thái hoàn thiện ngữ nghĩa của trang.
        warnings (List[str]): Danh sách các cảnh báo phát sinh trong quá trình xử lý trang.
        success (bool): Cờ chỉ báo việc trích xuất trang có thành công hay không.
        char_count (int): Tổng số lượng ký tự văn bản trích xuất được.
        tables (List[List[List[Optional[str]]]]): Dữ liệu bảng biểu dạng ma trận 3 chiều trích xuất được.
        ocr_confidence (float): Điểm tin cậy OCR trung bình của các dòng chữ trên trang.
        layout_regions (List[LayoutRegion]): Danh sách các vùng layout hình học bóc tách được.
        routing_reason (Optional[str]): Căn cứ lựa chọn tuyến xử lý cho trang (VD: có ít ký tự native text).
        needs_review (bool): Cờ cảnh báo trang có chất lượng thấp cần người dùng kiểm tra lại.
        error_details (Optional[str]): Chi tiết lỗi ngoại lệ nếu việc trích xuất trang thất bại.
    """
    source_name: str = Field(description="Tên hoặc định danh của tài liệu nguồn")
    page_number: int = Field(ge=1, description="Số thứ tự trang, bắt đầu từ 1")
    text: str = Field(default="", description="Nội dung văn bản bóc tách được")
    extraction_method: str = Field(
        default=ExtractionMethod.EMPTY.value,
        description="Phương thức trích xuất áp dụng (native_text, paddle_ocr, ocr, empty, failed)"
    )
    status: ExtractionStatus = Field(
        default=ExtractionStatus.COMPLETE,
        description="Trạng thái ngữ nghĩa: complete, partial, empty, failed"
    )
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo kỹ thuật phát sinh khi xử lý trang")
    success: bool = Field(default=True, description="Đánh dấu việc trích xuất trang có thành công hay không")
    char_count: int = Field(default=0, description="Tổng số ký tự văn bản thu được")
    tables: List[List[List[Optional[str]]]] = Field(
        default_factory=list,
        description="Danh sách ma trận bảng biểu trích xuất từ trang"
    )
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ tin cậy OCR trung bình của trang (0.0 - 1.0)")
    layout_regions: List[LayoutRegion] = Field(default_factory=list, description="Danh sách các vùng layout phát hiện trên trang")
    routing_reason: Optional[str] = Field(default=None, description="Lý do định tuyến trang")
    needs_review: bool = Field(default=False, description="Cờ đánh dấu trang cần người dùng rà soát")
    error_details: Optional[str] = Field(default=None, description="Chi tiết lỗi nếu trích xuất trang thất bại")

    def model_post_init(self, __context: Any) -> None:
        """Hậu xử lý tự động đồng bộ số lượng ký tự, trạng thái và cờ kiểm tra chất lượng trang."""
        if "char_count" not in self.model_fields_set and self.text:
            self.char_count = len(self.text)
        elif not self.char_count and self.text:
            self.char_count = len(self.text)

        if "status" not in self.model_fields_set:
            if not self.success or self.extraction_method == ExtractionMethod.FAILED.value:
                self.status = ExtractionStatus.FAILED
            elif self.extraction_method == ExtractionMethod.EMPTY.value or not self.text.strip():
                self.status = ExtractionStatus.EMPTY
            elif self.warnings or self.needs_review or (0.0 < self.ocr_confidence < 0.60):
                self.status = ExtractionStatus.PARTIAL
            else:
                self.status = ExtractionStatus.COMPLETE

        if "success" not in self.model_fields_set:
            self.success = (self.status != ExtractionStatus.FAILED)

        if "needs_review" not in self.model_fields_set and self.status == ExtractionStatus.PARTIAL:
            self.needs_review = True


class DocumentExtractionResult(BaseModel):
    """Kết quả trích xuất tổng hợp của toàn bộ tệp tài liệu PDF / BCTC.

    Hợp nhất thông tin toàn bộ các trang, đo lường thời gian xử lý và tổng kết lỗi/cảnh báo.
    """
    source_name: str = Field(description="Tên hoặc đường dẫn định danh tài liệu nguồn")
    total_pages: int = Field(ge=0, default=0, description="Tổng số trang của tài liệu")
    pages: List[PageExtractionResult] = Field(
        default_factory=list,
        description="Danh sách kết quả trích xuất từng trang theo đúng thứ tự gốc"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata trích xuất từ phần đầu tài liệu")
    success: bool = Field(default=True, description="Trạng thái thành công chung của toàn tài liệu")
    status: ExtractionStatus = Field(
        default=ExtractionStatus.COMPLETE,
        description="Trạng thái ngữ nghĩa tổng thể: complete, partial, empty, failed"
    )
    needs_review: bool = Field(default=False, description="Cờ cảnh báo nếu có bất kỳ trang nào cần người dùng rà soát lại")
    has_ocr_pages: bool = Field(default=False, description="Đánh dấu tài liệu có chứa trang cần chạy OCR hay không")
    has_native_pages: bool = Field(default=False, description="Đánh dấu tài liệu có chứa trang văn bản số hay không")
    has_tables: bool = Field(default=False, description="Đánh dấu có bảng biểu kế toán được phát hiện hay không")
    processing_time_seconds: float = Field(default=0.0, description="Tổng thời gian xử lý tài liệu tính bằng giây")
    errors: List[str] = Field(default_factory=list, description="Danh sách các lỗi phát sinh ở cấp độ tài liệu")

    def model_post_init(self, __context: Any) -> None:
        """Hậu xử lý tự động tổng hợp trạng thái tài liệu dựa trên tình trạng của từng trang thành phần."""
        if "status" not in self.model_fields_set:
            if not self.success or (self.errors and len(self.errors) > 0 and self.total_pages == 0):
                self.status = ExtractionStatus.FAILED
            elif self.total_pages == 0 or (self.pages and all(p.status == ExtractionStatus.EMPTY for p in self.pages)):
                self.status = ExtractionStatus.EMPTY
            elif any(p.status in (ExtractionStatus.PARTIAL, ExtractionStatus.FAILED) for p in self.pages) or self.errors:
                self.status = ExtractionStatus.PARTIAL
            else:
                self.status = ExtractionStatus.COMPLETE

        if "success" not in self.model_fields_set:
            self.success = (self.status != ExtractionStatus.FAILED)

        if "needs_review" not in self.model_fields_set:
            self.needs_review = any(p.needs_review for p in self.pages) or (self.status == ExtractionStatus.PARTIAL)

    @property
    def full_text(self) -> str:
        """Ghép toàn bộ nội dung văn bản của tất cả các trang, phân cách bởi ranh giới trang rõ ràng.

        Returns:
            str: Chuỗi văn bản đầy đủ kèm nhãn đánh dấu phân tách từng trang (VD: ===== PAGE 1 =====).
        """
        return "\n\n".join(
            f"===== PAGE {p.page_number} =====\n{p.text}" for p in self.pages if p.text.strip()
        )
