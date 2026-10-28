"""Từ điển kế toán mờ (Fuzzy Lexicon Corrector) cho Báo cáo tài chính Việt Nam (Thông tư 200).

Module này cung cấp bộ sửa lỗi chính tả chuyên ngành kế toán (FinancialLexiconCorrector):
- Khắc phục các lỗi OCR tiếng Việt phổ biến: mất dấu thanh, sai dấu mũ, lỗi nhận diện ký tự tương tự.
- Đối sánh mờ (Fuzzy Matching với difflib.SequenceMatcher) có định hướng theo mã số chỉ tiêu (item_code).
- Tích hợp bộ lọc từ phản mẫu (antipatterns) để tránh nhầm lẫn giữa các khoản mục ngắn hạn và dài hạn.
"""
import difflib
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.domain.accounting.normalizer import AccountingNumberNormalizer

logger = logging.getLogger(__name__)


class FinancialLexiconCorrector:
    """Bộ hiệu đính từ vựng kế toán mờ cho các dòng chỉ tiêu BCTC tiếng Việt.

    Chuẩn hóa các nhãn chữ thô bị lỗi OCR về tên gọi tiếng Việt chuẩn mực
    theo Thông tư 200/2014/TT-BTC và chuẩn mực kế toán Việt Nam (VAS).

    Attributes:
        CODE_THRESHOLD (float): Ngưỡng tương đồng tối thiểu khi có mã số chỉ tiêu (0.58).
        GLOBAL_THRESHOLD (float): Ngưỡng tương đồng tối thiểu khi đối sánh toàn cục không có mã số (0.72).
    """

    CODE_THRESHOLD = 0.58
    GLOBAL_THRESHOLD = 0.72

    # Danh mục từ vựng chuẩn hóa toàn diện theo TT200
    STANDARD_LEXICON: List[Dict[str, Any]] = [
        # --- BẢNG CÂN ĐỐI KẾ TOÁN (B 01 - DN / B 01a - DN/HN) ---
        # TÀI SẢN NGẮN HẠN
        {"code": "100", "standard_label": "Tài sản ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han", "khac"]},
        {"code": "110", "standard_label": "Tiền và các khoản tương đương tiền", "context": "balance_sheet", "antipatterns": ["dau tu", "phai thu"]},
        {"code": "111", "standard_label": "Tiền", "context": "balance_sheet", "antipatterns": ["tuong duong", "dau tu"]},
        {"code": "112", "standard_label": "Các khoản tương đương tiền", "context": "balance_sheet", "antipatterns": []},
        {"code": "120", "standard_label": "Đầu tư tài chính ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han", "chung khoan", "du phong", "dao han"]},
        {"code": "121", "standard_label": "Chứng khoán kinh doanh", "context": "balance_sheet", "antipatterns": ["du phong", "dao han"]},
        {"code": "122", "standard_label": "Dự phòng giảm giá chứng khoán kinh doanh", "context": "balance_sheet", "antipatterns": []},
        {"code": "123", "standard_label": "Đầu tư nắm giữ đến ngày đáo hạn", "context": "balance_sheet", "antipatterns": ["kinh doanh", "chung khoan"]},
        {"code": "130", "standard_label": "Các khoản phải thu ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han", "khac", "noi bo"]},
        {"code": "131", "standard_label": "Phải thu ngắn hạn của khách hàng", "context": "balance_sheet", "antipatterns": ["dai han", "tra truoc"]},
        {"code": "132", "standard_label": "Trả trước cho người bán ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "135", "standard_label": "Phải thu về cho vay ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "136", "standard_label": "Phải thu ngắn hạn khác", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "137", "standard_label": "Dự phòng phải thu ngắn hạn khó đòi", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "139", "standard_label": "Tài sản thiếu chờ xử lý", "context": "balance_sheet", "antipatterns": []},
        {"code": "140", "standard_label": "Hàng tồn kho", "context": "balance_sheet", "antipatterns": ["du phong"]},
        {"code": "141", "standard_label": "Hàng tồn kho", "context": "balance_sheet", "antipatterns": ["du phong"]},
        {"code": "149", "standard_label": "Dự phòng giảm giá hàng tồn kho", "context": "balance_sheet", "antipatterns": []},
        {"code": "150", "standard_label": "Tài sản ngắn hạn khác", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "151", "standard_label": "Chi phí trả trước ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "152", "standard_label": "Thuế giá trị gia tăng được khấu trừ", "context": "balance_sheet", "antipatterns": []},
        {"code": "153", "standard_label": "Thuế và các khoản khác phải thu Nhà nước", "context": "balance_sheet", "antipatterns": []},

        # TÀI SẢN DÀI HẠN
        {"code": "200", "standard_label": "Tài sản dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han", "khac"]},
        {"code": "210", "standard_label": "Các khoản phải thu dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "211", "standard_label": "Phải thu dài hạn của khách hàng", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "212", "standard_label": "Trả trước cho người bán dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "215", "standard_label": "Phải thu về cho vay dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "216", "standard_label": "Phải thu dài hạn khác", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "219", "standard_label": "Dự phòng phải thu dài hạn khó đòi", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "220", "standard_label": "Tài sản cố định", "context": "balance_sheet", "antipatterns": ["vo hinh", "thue tai chinh", "nguyen gia", "hao mon"]},
        {"code": "221", "standard_label": "Tài sản cố định hữu hình", "context": "balance_sheet", "antipatterns": ["vo hinh", "thue tai chinh"]},
        {"code": "222", "standard_label": "Nguyên giá", "context": "balance_sheet", "antipatterns": ["hao mon"]},
        {"code": "223", "standard_label": "Giá trị hao mòn lũy kế", "context": "balance_sheet", "antipatterns": ["nguyen gia"]},
        {"code": "224", "standard_label": "Tài sản cố định thuê tài chính", "context": "balance_sheet", "antipatterns": []},
        {"code": "227", "standard_label": "Tài sản cố định vô hình", "context": "balance_sheet", "antipatterns": ["huu hinh"]},
        {"code": "228", "standard_label": "Nguyên giá", "context": "balance_sheet", "antipatterns": ["hao mon"]},
        {"code": "229", "standard_label": "Giá trị hao mòn lũy kế", "context": "balance_sheet", "antipatterns": ["nguyen gia"]},
        {"code": "230", "standard_label": "Bất động sản đầu tư", "context": "balance_sheet", "antipatterns": []},
        {"code": "240", "standard_label": "Tài sản dở dang dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "242", "standard_label": "Chi phí xây dựng cơ bản dở dang", "context": "balance_sheet", "antipatterns": []},
        {"code": "250", "standard_label": "Đầu tư tài chính dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "251", "standard_label": "Đầu tư vào công ty con", "context": "balance_sheet", "antipatterns": []},
        {"code": "252", "standard_label": "Đầu tư vào công ty liên doanh, liên kết", "context": "balance_sheet", "antipatterns": []},
        {"code": "253", "standard_label": "Đầu tư góp vốn vào đơn vị khác", "context": "balance_sheet", "antipatterns": []},
        {"code": "254", "standard_label": "Dự phòng đầu tư tài chính dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "255", "standard_label": "Đầu tư nắm giữ đến ngày đáo hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "260", "standard_label": "Tài sản dài hạn khác", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "261", "standard_label": "Chi phí trả trước dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "262", "standard_label": "Tài sản thuế thu nhập hoãn lại", "context": "balance_sheet", "antipatterns": []},
        {"code": "270", "alt_codes": ["280"], "standard_label": "Tổng cộng tài sản", "context": "balance_sheet", "antipatterns": ["nguon von", "ngan han", "dai han khac", "dai hn khac", "khac"]},

        # NỢ PHẢI TRẢ
        {"code": "300", "standard_label": "Nợ phải trả", "context": "balance_sheet", "antipatterns": ["von chu so huu", "ngan han", "dai han"]},
        {"code": "310", "standard_label": "Nợ ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "311", "standard_label": "Phải trả người bán ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "312", "standard_label": "Người mua trả tiền trước ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "313", "standard_label": "Thuế và các khoản phải nộp Nhà nước", "context": "balance_sheet", "antipatterns": []},
        {"code": "314", "standard_label": "Phải trả người lao động", "context": "balance_sheet", "antipatterns": []},
        {"code": "315", "standard_label": "Chi phí phải trả ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "319", "standard_label": "Phải trả ngắn hạn khác", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "320", "standard_label": "Vay và nợ thuê tài chính ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "321", "standard_label": "Dự phòng phải trả ngắn hạn", "context": "balance_sheet", "antipatterns": ["dai han"]},
        {"code": "322", "standard_label": "Quỹ khen thưởng, phúc lợi", "context": "balance_sheet", "antipatterns": []},
        {"code": "330", "standard_label": "Nợ dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "331", "standard_label": "Phải trả người bán dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "332", "standard_label": "Người mua trả tiền trước dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "333", "standard_label": "Chi phí phải trả dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "337", "standard_label": "Phải trả dài hạn khác", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "338", "standard_label": "Vay và nợ thuê tài chính dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "341", "standard_label": "Dự phòng phải trả dài hạn", "context": "balance_sheet", "antipatterns": ["ngan han"]},
        {"code": "342", "standard_label": "Thuế thu nhập hoãn lại phải trả", "context": "balance_sheet", "antipatterns": []},

        # VỐN CHỦ SỞ HỮU
        {"code": "400", "alt_codes": ["410"], "standard_label": "Vốn chủ sở hữu", "context": "balance_sheet", "antipatterns": ["no phai tra", "nguon von"]},
        {"code": "411", "standard_label": "Vốn góp của chủ sở hữu", "context": "balance_sheet", "antipatterns": []},
        {"code": "412", "standard_label": "Thặng dư vốn cổ phần", "context": "balance_sheet", "antipatterns": []},
        {"code": "414", "standard_label": "Vốn khác của chủ sở hữu", "context": "balance_sheet", "antipatterns": []},
        {"code": "415", "standard_label": "Cổ phiếu quỹ", "context": "balance_sheet", "antipatterns": []},
        {"code": "418", "standard_label": "Quỹ đầu tư phát triển", "context": "balance_sheet", "antipatterns": []},
        {"code": "420", "alt_codes": ["421"], "standard_label": "Lợi nhuận sau thuế chưa phân phối", "context": "balance_sheet", "antipatterns": []},
        {"code": "421a", "standard_label": "LNST chưa phân phối lũy kế đến cuối kỳ trước", "context": "balance_sheet", "antipatterns": []},
        {"code": "421b", "standard_label": "LNST chưa phân phối kỳ này", "context": "balance_sheet", "antipatterns": []},
        {"code": "429", "standard_label": "Lợi ích cổ đông không kiểm soát", "context": "balance_sheet", "antipatterns": []},
        {"code": "430", "standard_label": "Nguồn kinh phí và quỹ khác", "context": "balance_sheet", "antipatterns": []},
        {"code": "440", "standard_label": "Tổng cộng nguồn vốn", "context": "balance_sheet", "antipatterns": ["tai san", "von chu so huu"]},

        # --- BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH (B 02 - DN / B 02a - DN/HN) ---
        {"code": "01", "standard_label": "Doanh thu bán hàng và cung cấp dịch vụ", "context": "income_statement", "antipatterns": ["thuan", "tai chinh"]},
        {"code": "02", "standard_label": "Các khoản giảm trừ doanh thu", "context": "income_statement", "antipatterns": []},
        {"code": "10", "standard_label": "Doanh thu thuần về bán hàng và cung cấp dịch vụ", "context": "income_statement", "antipatterns": ["chua giam tru"]},
        {"code": "11", "standard_label": "Giá vốn hàng bán", "context": "income_statement", "antipatterns": []},
        {"code": "20", "standard_label": "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ", "context": "income_statement", "antipatterns": ["thuan", "truoc thue", "sau thue"]},
        {"code": "21", "alt_codes": ["22"], "standard_label": "Doanh thu hoạt động tài chính", "context": "income_statement", "antipatterns": ["chi phi"]},
        {"code": "22", "alt_codes": ["23"], "standard_label": "Chi phí tài chính", "context": "income_statement", "antipatterns": ["lai vay", "doanh thu", "di vay"]},
        {"code": "23", "alt_codes": ["24"], "standard_label": "Chi phí lãi vay", "context": "income_statement", "antipatterns": []},
        {"code": "25", "standard_label": "Chi phí bán hàng", "context": "income_statement", "antipatterns": ["quan ly"]},
        {"code": "26", "standard_label": "Chi phí quản lý doanh nghiệp", "context": "income_statement", "antipatterns": ["ban hang"]},
        {"code": "30", "standard_label": "Lợi nhuận thuần từ hoạt động kinh doanh", "context": "income_statement", "antipatterns": ["gop", "truoc thue", "sau thue"]},
        {"code": "31", "standard_label": "Thu nhập khác", "context": "income_statement", "antipatterns": ["chi phi", "loi nhuan"]},
        {"code": "32", "standard_label": "Chi phí khác", "context": "income_statement", "antipatterns": ["thu nhap", "loi nhuan"]},
        {"code": "40", "standard_label": "Lợi nhuận khác", "context": "income_statement", "antipatterns": []},
        {"code": "50", "standard_label": "Tổng lợi nhuận kế toán trước thuế", "context": "income_statement", "antipatterns": ["sau thue", "gop"]},
        {"code": "51", "standard_label": "Chi phí thuế thu nhập doanh nghiệp hiện hành", "context": "income_statement", "antipatterns": []},
        {"code": "52", "standard_label": "Chi phí thuế thu nhập doanh nghiệp hoãn lại", "context": "income_statement", "antipatterns": []},
        {"code": "60", "standard_label": "Lợi nhuận sau thuế thu nhập doanh nghiệp", "context": "income_statement", "antipatterns": ["truoc thue", "gop"]},
        {"code": "61", "standard_label": "Lợi nhuận sau thuế của công ty mẹ", "context": "income_statement", "antipatterns": []},
        {"code": "62", "standard_label": "Lợi nhuận sau thuế của cổ đông không kiểm soát", "context": "income_statement", "antipatterns": []},
        {"code": "70", "standard_label": "Lãi cơ bản trên cổ phiếu", "context": "income_statement", "antipatterns": []},
        {"code": "71", "standard_label": "Lãi suy giảm trên cổ phiếu", "context": "income_statement", "antipatterns": []},
    ]

    _CODE_MAP: Dict[str, List[Dict[str, Any]]] = {}
    _INITIALIZED: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Khởi tạo bộ nhớ đệm (Cache) mã số chỉ tiêu để tăng tốc độ tra cứu đối sánh."""
        if cls._INITIALIZED:
            return
        cls._CODE_MAP = {}
        for entry in cls.STANDARD_LEXICON:
            clean_lbl = AccountingNumberNormalizer.clean_label(entry["standard_label"])
            entry["_clean_label"] = clean_lbl
            entry["_unaccented_label"] = AccountingNumberNormalizer.strip_accents(clean_lbl)

            codes = [entry["code"]] + entry.get("alt_codes", [])
            for c in codes:
                c_norm = c.strip().lstrip("0") or "0"
                cls._CODE_MAP.setdefault(c_norm, []).append(entry)
                cls._CODE_MAP.setdefault(c.strip(), []).append(entry)
        cls._INITIALIZED = True

    @classmethod
    def correct_label(
        cls,
        raw_label: str,
        item_code: Optional[str] = None,
        context: str = "unknown",
    ) -> Tuple[str, bool]:
        """Hiệu đính nhãn chỉ tiêu OCR thô sang tên gọi kế toán tiếng Việt chuẩn.

        Thực thi quy trình đối sánh 2 giai đoạn:
        - Giai đoạn 1: Ưu tiên lọc theo mã số chỉ tiêu (item_code) nếu có.
        - Giai đoạn 2: Tìm kiếm mờ toàn cục có kiểm tra từ phản mẫu (antipatterns).

        Args:
            raw_label (str): Tên chỉ tiêu thô bóc tách từ OCR.
            item_code (Optional[str]): Mã số chỉ tiêu kế toán tương ứng nếu có (VD: '100', '110').
            context (str): Bối cảnh bảng biểu ('balance_sheet', 'income_statement', hoặc 'unknown').

        Returns:
            Tuple[str, bool]: (Tên chỉ tiêu đã hiệu đính, True nếu có chỉnh sửa / False nếu giữ nguyên).
        """
        cls._ensure_initialized()
        cleaned_raw = AccountingNumberNormalizer.clean_label(raw_label)
        unaccented_raw = AccountingNumberNormalizer.strip_accents(cleaned_raw)

        if not unaccented_raw or len(unaccented_raw) < 3:
            return raw_label, False

        # Giai đoạn 1: Định hướng tra cứu theo item_code nếu có
        if item_code:
            code_key = str(item_code).strip()
            code_norm = code_key.lstrip("0") or "0"
            candidates = cls._CODE_MAP.get(code_norm, []) or cls._CODE_MAP.get(code_key, [])
            for cand in candidates:
                if context in ("balance_sheet", "income_statement") and cand["context"] != context:
                    continue

                has_anti = any(
                    anti in unaccented_raw for anti in cand.get("antipatterns", [])
                )
                if has_anti:
                    continue

                cand_unaccented = cand["_unaccented_label"]
                if (
                    unaccented_raw == cand_unaccented
                    or unaccented_raw in cand_unaccented
                    or cand_unaccented in unaccented_raw
                ):
                    return cand["standard_label"], True

                ratio = difflib.SequenceMatcher(None, unaccented_raw, cand_unaccented).ratio()
                if ratio >= cls.CODE_THRESHOLD:
                    return cand["standard_label"], True

        # Giai đoạn 2: Đối sánh mờ toàn cục (Global Fuzzy Match)
        best_cand: Optional[Dict[str, Any]] = None
        best_ratio: float = 0.0

        for cand in cls.STANDARD_LEXICON:
            if context in ("balance_sheet", "income_statement") and cand["context"] != context:
                continue

            has_anti = any(
                anti in unaccented_raw for anti in cand.get("antipatterns", [])
            )
            if has_anti:
                continue

            cand_unaccented = cand["_unaccented_label"]
            if unaccented_raw == cand_unaccented:
                return cand["standard_label"], True

            ratio = difflib.SequenceMatcher(None, unaccented_raw, cand_unaccented).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_cand = cand

        if best_cand is not None and best_ratio >= cls.GLOBAL_THRESHOLD:
            return best_cand["standard_label"], True

        return raw_label, False

    @classmethod
    def correct(
        cls,
        raw_label: str,
        item_code: Optional[str] = None,
        context: str = "unknown",
    ) -> Tuple[str, bool]:
        """Bí danh tiện ích cho phương thức correct_label.

        Args:
            raw_label (str): Nhãn gốc.
            item_code (Optional[str]): Mã số chỉ tiêu.
            context (str): Bối cảnh bảng biểu.

        Returns:
            Tuple[str, bool]: Nhãn hiệu đính và cờ chỉ báo có sửa đổi.
        """
        return cls.correct_label(raw_label, item_code, context)
