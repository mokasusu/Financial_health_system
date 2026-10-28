"""Định nghĩa mô hình và Enums cho từng chỉ tiêu kế toán BCTC theo Thông tư 200/2014/TT-BTC.

Module này cung cấp các thực thể dữ liệu (Entities/Value Objects) phản ánh chi tiết
từng dòng chỉ tiêu kế toán, phương thức ánh xạ (Mapping), trạng thái kiểm tra (Validation)
và số học Decimal tuyệt đối để ngăn ngừa sai số làm tròn số thực.
"""
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class MappingMethod(str, Enum):
    """Phương thức bóc tách và ánh xạ từ dòng thô sang chỉ tiêu kế toán chuẩn.

    Attributes:
        CODE_EXACT: Khớp chính xác theo mã số chỉ tiêu chính thức (VD: Mã số 100, 110, 300).
        LABEL_EXACT: Khớp chính xác tuyệt đối theo chuỗi tên chỉ tiêu đã chuẩn hóa.
        LABEL_SYNONYM: Khớp thông qua từ điển từ đồng nghĩa kế toán (Synonyms).
        REGEX_RULE: Khớp bằng các luật biểu thức chính quy (Regex) theo ngữ cảnh.
        UNMAPPED: Không thể ánh xạ tin cậy vào bất kỳ chỉ tiêu chuẩn nào.
    """
    CODE_EXACT = "code_exact"          # Khớp chính xác mã số (VD: MS 100, 110)
    LABEL_EXACT = "label_exact"        # Khớp chính xác nhãn chữ chuẩn hóa
    LABEL_SYNONYM = "label_synonym"    # Khớp qua từ điển từ đồng nghĩa
    REGEX_RULE = "regex_rule"          # Khớp qua quy tắc biểu thức chính quy
    UNMAPPED = "unmapped"              # Chưa thể ánh xạ tin cậy


class MappingStatus(str, Enum):
    """Trạng thái kiểm định và mức độ tin cậy của quá trình ánh xạ chỉ tiêu.

    Attributes:
        MAPPED: Ánh xạ thành công với độ tin cậy cao, dữ liệu sẵn sàng phân tích.
        NEEDS_REVIEW: Khớp một phần hoặc phát hiện mơ hồ, cần người dùng đối soát lại.
        UNMAPPED: Không tìm thấy chỉ tiêu tương ứng trong chuẩn mực kế toán.
    """
    MAPPED = "mapped"                  # Đã ánh xạ thành công, độ tin cậy cao
    NEEDS_REVIEW = "needs_review"      # Cần xem xét lại do nghi ngờ hoặc khớp một phần
    UNMAPPED = "unmapped"              # Chưa được ánh xạ vào chuẩn kế toán


class AccountingStandard(str, Enum):
    """Hệ thống chuẩn mực kế toán áp dụng cho doanh nghiệp tại Việt Nam.

    Attributes:
        TT200_2014: Chế độ kế toán doanh nghiệp theo Thông tư 200/2014/TT-BTC.
        VAS: Chuẩn mực kế toán Việt Nam chung (Vietnamese Accounting Standards).
        UNKNOWN: Chưa xác định được chuẩn mực áp dụng từ báo cáo.
    """
    TT200_2014 = "TT200/2014/TT-BTC"   # Thông tư 200/2014/TT-BTC
    VAS = "VAS"                        # Chuẩn mực kế toán Việt Nam chung
    UNKNOWN = "unknown"                # Chưa xác định rõ chuẩn mực


class CheckStatus(str, Enum):
    """Trạng thái kết quả kiểm định một đẳng thức cân đối kế toán.

    Attributes:
        PASS: Đẳng thức hoàn toàn cân bằng (sai số trong ngưỡng cho phép).
        WARNING: Có sai lệch nhỏ (thường do sai số làm tròn hoặc trình bày đơn vị).
        FAIL: Đẳng thức mất cân đối nghiêm trọng, số liệu kế toán có bất thường.
        NOT_CHECKABLE: Thiếu chỉ tiêu đầu vào bắt buộc, không đủ dữ liệu kiểm tra.
    """
    PASS = "pass"                      # Cân đối hoàn toàn (Đạt)
    WARNING = "warning"                # Cảnh báo sai lệch nhỏ
    FAIL = "fail"                      # Lỗi mất cân đối kế toán
    NOT_CHECKABLE = "not_checkable"    # Không đủ số liệu để kiểm tra


class LineItem(BaseModel):
    """Mô hình dữ liệu đại diện cho một dòng chỉ tiêu kế toán sau khi chuẩn hóa.

    Lưu trữ đầy đủ số liệu tài chính kỳ này, kỳ trước (bằng Decimal),
    mã số kế toán, nguồn gốc trang tài liệu, độ tin cậy OCR và dấu vết kiểm toán.
    """
    raw_label: str = Field(description="Tên chỉ tiêu gốc chưa làm sạch bóc tách từ OCR/Parser")
    normalized_label: str = Field(description="Tên chỉ tiêu đã làm sạch (chuyển chữ thường, xóa khoảng trắng thừa)")
    canonical_key: Optional[str] = Field(default=None, description="Khóa định danh chuẩn của hệ thống (VD: current_assets, net_revenue)")
    item_code: Optional[str] = Field(default=None, description="Mã số chỉ tiêu kế toán chính thức (VD: 100, 110, 310) nếu xác định được")
    accounting_standard: AccountingStandard = Field(default=AccountingStandard.TT200_2014, description="Chuẩn mực kế toán áp dụng")
    current_period_value: Optional[Decimal] = Field(default=None, description="Số liệu kỳ báo cáo hiện tại (Decimal)")
    previous_period_value: Optional[Decimal] = Field(default=None, description="Số liệu kỳ so sánh trước đó (Decimal)")
    unit: Optional[str] = Field(default="VND", description="Đơn vị tính tiền tệ (VND, nghìn VND, triệu VND, tỷ VND)")
    source_page: Optional[int] = Field(default=None, description="Số thứ tự trang tài liệu gốc (bắt đầu từ 1)")
    mapping_method: MappingMethod = Field(default=MappingMethod.UNMAPPED, description="Phương thức bóc tách/ánh xạ đã dùng")
    mapping_status: MappingStatus = Field(default=MappingStatus.UNMAPPED, description="Trạng thái độ tin cậy ánh xạ")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Điểm tin cậy tổng hợp (từ 0.0 đến 1.0)")
    ocr_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Độ tin cậy nhận dạng ký tự của mô hình OCR")
    mapping_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Độ tin cậy ánh xạ ngữ nghĩa sang chỉ tiêu chuẩn")
    row_consistency: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Điểm nhất quán logic giữa tên chỉ tiêu, mã số và giá trị số")
    warnings: List[str] = Field(default_factory=list, description="Danh sách các cảnh báo kiểm toán phát sinh trong quá trình bóc tách")
