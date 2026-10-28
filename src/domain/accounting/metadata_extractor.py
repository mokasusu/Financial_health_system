"""Trích xuất siêu dữ liệu (Metadata) Báo cáo tài chính Việt Nam (Thông tư 200).

Module này cung cấp bộ trích xuất thông minh (StatementMetadataExtractor):
- Phân loại trang tài liệu thuộc loại báo cáo nào (Bảng cân đối kế toán B01-DN, KQKD B02-DN...).
- Bóc tách niên độ tài chính, ngày khóa sổ lập BCTC (DD/MM/YYYY), nhãn kỳ kế toán.
- Xác định đơn vị tiền tệ hạch toán (VND, nghìn VND, triệu VND, tỷ VND, USD).
- Nhận diện tiêu đề cột kỳ này / kỳ trước từ dòng tiêu đề bảng.
- Bóc tách tên doanh nghiệp lập báo cáo kết hợp bộ lọc loại trừ hãng kiểm toán độc lập (Auditor Blacklist).
"""
import re
from typing import List, Optional, Tuple

from src.domain.accounting.normalizer import AccountingNumberNormalizer

# Danh sách đen các đơn vị và từ khóa kiểm toán độc lập để tránh nhận diện nhầm là doanh nghiệp lập BCTC
AUDITOR_BLACKLIST = [
    "KIỂM TOÁN", "KIEM TOAN", "AUDIT", "TNHH KIỂM TOÁN",
    "KPMG", "PWC", "DELOITTE", "ERNST & YOUNG", "PRICEWATERHOUSECOOPERS",
    "GRANT THORNTON", "BDO", "A&C",
]


class StatementMetadataExtractor:
    """Bộ trích xuất siêu dữ liệu báo cáo tài chính từ nội dung văn bản bóc tách."""

    @staticmethod
    def detect_statement_type(text: str) -> str:
        """Nhận diện loại báo cáo tài chính của trang tài liệu dựa trên tiêu đề và mã hiệu mẫu số.

        Args:
            text (str): Toàn bộ nội dung văn bản của trang tài liệu.

        Returns:
            str: Loại báo cáo ('balance_sheet', 'income_statement', 'cash_flow', 'notes', hoặc 'unknown').
        """
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        header_lines = lines[:20]
        header_text = "\n".join(header_lines)
        header_unaccented = AccountingNumberNormalizer.strip_accents(header_text).upper()

        # Loại trừ trang mục lục tài liệu
        if "MUC LUC" in header_unaccented or "TABLE OF CONTENTS" in header_unaccented:
            return "unknown"

        # Loại trừ các trang báo cáo kiểm toán hoặc báo cáo của ban giám đốc
        if any(k in header_unaccented for k in [
            "BAO CAO KIEM TOAN", "BAO CAO CUA BAN DIEU HANH", "BAN DIEU HANH", "BAN KIEM SOAT", "Y KIEN KIEM TOAN"
        ]):
            return "unknown"

        filtered_unaccented = "\n".join([
            l for l in header_unaccented.splitlines()
            if not any(k in l for k in ["DINH KEM", "HOP THANH", "BO PHAN"])
        ])

        # Bảng Cân Đối Kế Toán (Mẫu B 01 - DN)
        if (
            re.search(r"\bB\s*01[a-z]?\b", header_text, re.I)
            or "CAN DOI KE TOAN" in filtered_unaccented
            or "BAO CAO TINH HINH TAI CHINH" in filtered_unaccented
            or ("TINH HINH TAI CHINH" in filtered_unaccented and ("TAI NGAY" in filtered_unaccented or "MA SO" in filtered_unaccented))
        ):
            return "balance_sheet"

        # Báo Cáo Kết Quả Hoạt Động Kinh Doanh (Mẫu B 02 - DN)
        if (
            re.search(r"\bB\s*02[a-z]?\b", header_text, re.I)
            or "KET QUA HOAT DONG KINH DOANH" in filtered_unaccented
            or "KET QUA KINH DOANH" in filtered_unaccented
            or ("KT QU" in filtered_unaccented and "KINH DOANH" in filtered_unaccented)
            or ("HOT DNG KINH DOANH" in filtered_unaccented and "BAO CAO" in filtered_unaccented)
        ):
            return "income_statement"

        # Báo Cáo Lưu Chuyển Tiền Tệ (Mẫu B 03 - DN)
        if (
            re.search(r"\bB\s*03[a-z]?\b", header_text, re.I)
            or "LUU CHUYEN TIEN TE" in filtered_unaccented
            or "LUU CHUYN TIN T" in filtered_unaccented
            or "LUU CHUYEN TIEN" in filtered_unaccented
        ):
            return "cash_flow"

        # Bản Thuyết Minh Báo Cáo Tài Chính (Mẫu B 09 - DN)
        if (
            re.search(r"\bB\s*09[a-z]?\b", header_text, re.I)
            or "BAN THUYET MINH" in filtered_unaccented
            or "THUYET MINH BAO CAO TAI CHINH" in filtered_unaccented
        ):
            return "notes"

        return "unknown"

    @staticmethod
    def detect_unit(text: str) -> str:
        """Bóc tách đơn vị tiền tệ hạch toán từ dòng 'Đơn vị tính' trên phần đầu báo cáo.

        Args:
            text (str): Nội dung văn bản tài liệu.

        Returns:
            str: Đơn vị tiền tệ chuẩn ('triệu VND', 'tỷ VND', 'nghìn VND', 'USD', hoặc 'VND').
        """
        match = re.search(r"(?:Đơn vị tính|ĐVT|Don vi tinh)\s*[:\-]?\s*([^\n\r,;]+)", text, re.IGNORECASE)
        if match:
            raw_unit = match.group(1).split("\n")[0].strip()
            if "triệu" in raw_unit.lower() or "trieu" in raw_unit.lower():
                return "triệu VND"
            elif "tỷ" in raw_unit.lower() or "ty" in raw_unit.lower():
                return "tỷ VND"
            elif "nghìn" in raw_unit.lower() or "nghin" in raw_unit.lower():
                return "nghìn VND"
            elif "usd" in raw_unit.lower():
                return "USD"
            elif "vnd" in raw_unit.lower() or "đồng" in raw_unit.lower():
                return "VND"
        return "VND"

    @staticmethod
    def detect_as_of_date(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Bóc tách ngày khóa sổ lập BCTC (định dạng DD/MM/YYYY) và năm tài chính.

        Áp dụng các mẫu biểu thức chính quy (Regex) nhận diện cấu trúc ngày tháng tiếng Việt và tiếng Anh.

        Args:
            text (str): Nội dung văn bản tài liệu.

        Returns:
            Tuple[Optional[str], Optional[int]]: (Chuỗi ngày 'DD/MM/YYYY', Năm tài chính nguyên).
        """
        text_clean = text.replace("\r", " ").replace("\n", " ")

        # 1. Mẫu: 'tại ngày DD tháng MM năm YYYY'
        m = re.search(r"(?:tại\s+ngày|ngày)\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 2. Mẫu: 'kết thúc vào ngày DD tháng MM năm YYYY'
        m = re.search(r"kết\s+thúc\s+(?:vào\s+)?ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 3. Mẫu: 'tại ngày DD/MM/YYYY'
        m = re.search(r"(?:tại\s+ngày|kết\s+thúc\s+ngày|ngày|tại)\s*[:\-]?\s*(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 4. Mẫu tiếng Anh: 'as at DD Month YYYY'
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        m = re.search(r"as\s+(?:at|of)\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo_str, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            mo = month_map.get(mo_str)
            if mo and 1 <= d <= 31:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 5. Mẫu tiếng Anh dạng số: 'as at DD/MM/YYYY'
        m_asof = re.search(r"as\s+(?:at|of)\s*[:\-]?\s*(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if m_asof:
            d, mo, y = int(m_asof.group(1)), int(m_asof.group(2)), int(m_asof.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 6. Mẫu: 'cho năm tài chính kết thúc ngày DD/MM/YYYY'
        m = re.search(r"(?:cho\s+năm\s+tài\s+chính|năm\s+tài\s+chính).*?(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 7. Mẫu tổng quát: bất kỳ chuỗi DD/MM/YYYY nào (loại trừ ngày ban hành TT200: 22/12/2014)
        m = re.search(r"\b(3[01]|0[1-9]|[12]\d)[/-](0[1-9]|1[0-2])[/-]((?:19|20)\d{2})\b", text_clean)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if f"{d:02d}/{mo:02d}/{y}" != "22/12/2014":
                return f"{d:02d}/{mo:02d}/{y}", y

        return None, None

    @staticmethod
    def detect_period_label(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Nhận diện nhãn kỳ kế toán tổng quát (VD: 'Năm 2020', 'Quý 1/2026', '6 tháng 2024').

        Args:
            text (str): Nội dung văn bản tài liệu.

        Returns:
            Tuple[Optional[str], Optional[int]]: (Nhãn kỳ báo cáo, Năm tài chính).
        """
        text_clean = text.replace("\r", " ").replace("\n", " ")

        # Nhận diện báo cáo quý: 'Quý X năm YYYY'
        m_q = re.search(r"quý\s*(\d|\b[IVXLCDM]+\b)[/-]?\s*(?:năm\s*)?((?:19|20)\d{2})", text_clean, re.I)
        if m_q:
            q_num = m_q.group(1)
            y = int(m_q.group(2))
            return f"Quý {q_num}/{y}", y

        # Nhận diện báo cáo bán niên / 6 tháng đầu năm
        m_semi = re.search(r"(?:6\s+tháng\s+(?:đầu\s+năm\s+)?|bán\s+niên\s*)((?:19|20)\d{2})", text_clean, re.I)
        if m_semi:
            y = int(m_semi.group(1))
            return f"6 tháng {y}", y

        # Nhận diện ngày kết thúc kỳ: 31/12 thì ghi nhận là cả Năm tài chính
        m_end = re.search(r"kết\s+thúc\s+(?:vào\s+)?ngày\s+(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if not m_end:
            m_end = re.search(r"kết\s+thúc\s+(?:vào\s+)?ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+((?:19|20)\d{2})", text_clean, re.I)
        if m_end:
            d, mo, y = int(m_end.group(1)), int(m_end.group(2)), int(m_end.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                if d == 31 and mo == 12:
                    return f"Năm {y}", y
                return f"Kỳ kết thúc {d:02d}/{mo:02d}/{y}", y

        # Nhận diện từ khóa 'Năm YYYY' (bỏ qua năm 2014 của Thông tư 200)
        m_yr = re.search(r"\bnăm\s+((?:19|20)\d{2})\b", text_clean, re.I)
        if m_yr:
            y = int(m_yr.group(1))
            if y != 2014:
                return f"Năm {y}", y

        return None, None

    @staticmethod
    def detect_column_headers(row_cells: List[str], context: str) -> Tuple[Optional[str], Optional[str]]:
        """Nhận diện tên nhãn tiêu đề cột kỳ này và kỳ trước từ một dòng bảng BCTC.

        Args:
            row_cells (List[str]): Danh sách các ô văn bản trong một dòng.
            context (str): Bối cảnh bảng ('balance_sheet' hoặc 'income_statement').

        Returns:
            Tuple[Optional[str], Optional[str]]: (Tên cột kỳ hiện tại, Tên cột kỳ so sánh trước).
        """
        row_text = " ".join(str(c).strip() for c in row_cells if c is not None)
        if not row_text.strip():
            return None, None

        l_row = row_text.lower()
        # Bỏ qua các dòng tiêu đề chung văn bản hành chính
        if any(t in l_row for t in ["báo cáo", "báo cáo tài chính", "bộ tài chính", "thông tư", "ban hành", "mẫu số", "mẫu b"]):
            if not ("mã số" in l_row and re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", row_text)):
                return None, None

        # 1. Tìm các ngày tháng định dạng DD/MM/YYYY trong dòng
        date_matches = re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})[/.-]((?:19|20)\d{2})\b", row_text)
        found_dates: List[str] = []
        for m in date_matches:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                found_dates.append(f"{d:02d}/{mo:02d}/{y}")

        if len(found_dates) >= 2:
            return found_dates[0], found_dates[1]
        elif len(found_dates) == 1 and context == "balance_sheet":
            if any(k in l_row for k in ["mã số", "thuyết minh", "chỉ tiêu", "đơn vị tính"]):
                return found_dates[0], None

        # 2. Tìm các năm 'Năm YYYY'
        years = re.findall(r"\bnăm\s+((?:19|20)\d{2})\b", row_text, re.I)
        if len(years) >= 2:
            return f"Năm {years[0]}", f"Năm {years[1]}"
        elif len(years) == 1 and context == "income_statement":
            if any(k in l_row for k in ["chỉ tiêu", "mã số", "thuyết minh", "đơn vị tính"]):
                y = int(years[0])
                if y != 2014:
                    return f"Năm {y}", f"Năm {y - 1}"

        # 3. Tìm các quý 'Quý X/YYYY'
        q_matches = re.findall(r"quý\s*(\d|\b[IVXLCDM]+\b)[/-]?\s*(?:năm\s*)?((?:19|20)\d{2})", row_text, re.I)
        if len(q_matches) >= 2:
            return f"Quý {q_matches[0][0]}/{q_matches[0][1]}", f"Quý {q_matches[1][0]}/{q_matches[1][1]}"

        # 4. Tìm các cặp nhãn chữ kế toán kinh điển
        if "cuối năm" in l_row and "đầu năm" in l_row:
            return "Số cuối năm", "Số đầu năm"
        if "cuối kỳ" in l_row and "đầu năm" in l_row:
            return "Số cuối kỳ", "Số đầu năm"
        if "cuối kỳ" in l_row and "đầu kỳ" in l_row:
            return "Số cuối kỳ", "Số đầu kỳ"
        if "năm nay" in l_row and "năm trước" in l_row:
            return "Năm nay", "Năm trước"
        if "kỳ này" in l_row and "kỳ trước" in l_row:
            return "Kỳ này", "Kỳ trước"

        return None, None

    @classmethod
    def detect_fiscal_year(cls, text: str) -> Optional[int]:
        """Phát hiện niên độ năm tài chính áp dụng từ nội dung văn bản.

        Args:
            text (str): Nội dung văn bản tài liệu.

        Returns:
            Optional[int]: Năm tài chính (VD: 2020) hoặc None.
        """
        _, y = cls.detect_as_of_date(text)
        if y:
            return y
        _, y = cls.detect_period_label(text)
        if y:
            return y
        matches = re.finditer(r"(?:cho\s+năm\s+tài\s+chính|năm\s+tài\s+chính|năm|nam|31/12/|31-12-)\s*(\d{4})", text, re.IGNORECASE)
        for m in matches:
            yr = int(m.group(1))
            span_start = max(0, m.start() - 30)
            prefix = text[span_start:m.start()].upper()
            if "200/2014" in prefix or "THÔNG TƯ" in prefix:
                continue
            if 1990 <= yr <= 2100:
                return yr
        return None

    @staticmethod
    def detect_company_name(text: str) -> Optional[str]:
        """Trích xuất tên doanh nghiệp lập báo cáo tài chính, tự động loại trừ hãng kiểm toán.

        Args:
            text (str): Nội dung văn bản tài liệu (thường là trang bìa hoặc đầu BCTC).

        Returns:
            Optional[str]: Tên doanh nghiệp chuẩn hoặc None nếu không nhận diện được.
        """
        matches = re.findall(r"(?:CÔNG TY|CONG TY)\s+[A-Z0-9À-Ỹ\s\.\-]+(?:\n|$)", text, re.IGNORECASE)
        for m in matches:
            clean = m.strip()
            # Bỏ qua nếu dòng chứa tên hãng kiểm toán độc lập
            if not any(k in clean.upper() for k in AUDITOR_BLACKLIST):
                return clean
        return matches[0].strip() if matches else None
