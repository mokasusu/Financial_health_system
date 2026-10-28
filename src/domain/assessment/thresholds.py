"""Định nghĩa tập trung các ngưỡng sàng lọc tài chính và tuyên bố miễn trừ trách nhiệm.

Module này cung cấp:
- DEFAULT_SCREENING_THRESHOLDS: Bảng ngưỡng sàng lọc tham chiếu minh họa (Illustrative Screening Thresholds)
  cho các chỉ số thanh khoản và cơ cấu vốn / đòn bẩy bằng số học Decimal.
  Phân loại giá trị chỉ số thành 3 vùng: An toàn (Adequate), Cần theo dõi (Watch), Cảnh báo rủi ro (Alert).
- STANDARD_DISCLAIMERS: Danh sách các tuyên bố miễn trừ trách nhiệm pháp lý chuẩn mực
  nhằm đảm bảo tính thận trọng và đạo đức trong phân tích Công nghệ Tài chính (FinTech).
"""
from decimal import Decimal
from typing import Any, Dict, List

# =============================================================================
# NGƯỠNG SÀNG LỌC TÀI CHÍNH THAM CHIẾU (SCREENING THRESHOLDS)
# GHI CHÚ QUAN TRỌNG:
# Các ngưỡng dưới đây là NGƯỠNG SÀNG LỌC MINH HỌA (illustrative screening thresholds),
# được thiết kế phục vụ phân loại rủi ro mức quy tắc ban đầu.
# Chúng KHÔNG đại diện cho chuẩn mực kế toán pháp lý hay chuẩn so sánh ngành phổ quát.
# Các ngưỡng này có thể được cấu hình hoặc thay thế linh hoạt theo ngành nghề cụ thể.
# =============================================================================
DEFAULT_SCREENING_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    # Nhóm Thanh khoản
    "current_ratio": {
        "alert_max": Decimal("1.0"),   # < 1.0: Cảnh báo thanh khoản ngắn hạn suy yếu
        "watch_max": Decimal("1.5"),   # 1.0 <= val < 1.5: Cần theo dõi khả năng thanh toán
        "adequate_min": Decimal("1.5"),# >= 1.5: Vùng an toàn sàng lọc
        "unit": "lần",
    },
    "quick_ratio": {
        "alert_max": Decimal("0.5"),   # < 0.5: Cảnh báo thanh khoản nhanh (thiếu hụt tài sản nhanh)
        "watch_max": Decimal("1.0"),   # 0.5 <= val < 1.0: Cần theo dõi
        "adequate_min": Decimal("1.0"),# >= 1.0: Vùng an toàn sàng lọc
        "unit": "lần",
    },
    "cash_ratio": {
        "alert_max": Decimal("0.1"),   # < 0.1: Cảnh báo đệm tiền mặt và tương đương tiền mỏng
        "watch_max": Decimal("0.2"),   # 0.1 <= val < 0.2: Cần theo dõi
        "adequate_min": Decimal("0.2"),# >= 0.2: Vùng an toàn sàng lọc
        "unit": "lần",
    },

    # Nhóm Cơ cấu vốn / Đòn bẩy tài chính
    "debt_to_assets": {
        "alert_min": Decimal("0.7"),   # > 0.70 (70%): Cảnh báo tỷ trọng nợ vay/chiếm dụng cao
        "watch_min": Decimal("0.5"),   # 0.50 < val <= 0.70: Cần theo dõi áp lực nợ
        "adequate_max": Decimal("0.5"),# <= 0.50 (50%): Vùng đòn bẩy vừa phải, an toàn
        "unit": "%",
    },
    "debt_to_equity": {
        "alert_min": Decimal("2.0"),   # > 2.0: Cảnh báo tổng nợ vượt quá 2 lần vốn chủ sở hữu
        "watch_min": Decimal("1.0"),   # 1.0 < val <= 2.0: Cần theo dõi cơ cấu vốn
        "adequate_max": Decimal("1.0"),# <= 1.0: Nợ không vượt quá vốn chủ sở hữu
        "unit": "lần",
    },
    "equity_ratio": {
        "alert_max": Decimal("0.3"),   # < 0.30 (30%): Cảnh báo tỷ trọng vốn tự có mỏng
        "watch_max": Decimal("0.5"),   # 0.30 <= val < 0.50: Cần theo dõi
        "adequate_min": Decimal("0.5"),# >= 0.50 (50%): Tự tài trợ từ 50% tổng tài sản trở lên
        "unit": "%",
    },
}

# Các tuyên bố miễn trừ trách nhiệm pháp lý và giới hạn phân tích chuẩn mực
STANDARD_DISCLAIMERS: List[str] = [
    "Các ngưỡng đánh giá là ngưỡng sàng lọc minh họa ban đầu, không đại diện cho chuẩn mực kế toán hay chuẩn ngành phổ quát.",
    "Đánh giá rule-based chưa tính đến các đặc thù về mô hình kinh doanh, chu kỳ hoạt động và mùa vụ của doanh nghiệp.",
    "Kết quả phản ánh số liệu BCTC tại thời điểm lập báo cáo, cần kết hợp phân tích lưu chuyển tiền tệ và thuyết minh chi tiết.",
    "Hệ thống không cung cấp lời khuyên đầu tư, khuyến nghị giao dịch chứng khoán hoặc quyết định cấp tín dụng chắc chắn.",
]
