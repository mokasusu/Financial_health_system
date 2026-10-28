"""Chuẩn hóa số học và đơn vị tính cho Báo cáo tài chính Việt Nam (Thông tư 200).

Module này cung cấp các công cụ chuẩn hóa chuyên sâu:
- Nhận diện định dạng số kế toán Việt Nam (1.234.567,89) và Quốc tế (1,234,567.89).
- Xử lý số âm kế toán trong dấu ngoặc đơn (123.456) thành -123456.
- Nhận diện ký tự gạch ngang '-' đại diện cho số 0 hoặc không phát sinh.
- Chuyển đổi chính xác sang kiểu dữ liệu Decimal tuyệt đối (loại bỏ sai số float).
- Quy đổi đơn vị tính tiền tệ (nghìn, triệu, tỷ VND) và làm sạch nhãn chữ tiếng Việt.
"""
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import List, Optional, Tuple
import unicodedata
from pydantic import BaseModel, Field


class NumberStatus(str, Enum):
    """Trạng thái phân loại kết quả trích xuất số học từ bảng BCTC.

    Attributes:
        VALID: Bóc tách thành công thành số Decimal hợp lệ.
        MISSING: Ô trống hoặc chỉ chứa khoảng trắng (dữ liệu thiếu).
        DASH_NOT_APPLICABLE: Ký tự gạch ngang '-' chỉ thị không phát sinh hoặc bằng 0.
        AMBIGUOUS: Chứa ký tự nhiễu OCR mơ hồ (VD: nhầm giữa chữ O và số 0).
        INVALID: Chuỗi không thể phân tích cú pháp thành một giá trị số.
    """
    VALID = "valid"                            # Bóc tách thành công thành Decimal chính xác
    MISSING = "missing"                        # Ô trống hoặc chỉ có khoảng trắng
    DASH_NOT_APPLICABLE = "dash_na"            # Dấu gạch ngang '-' chỉ thị số 0 hoặc không áp dụng
    AMBIGUOUS = "ambiguous"                    # Chứa ký tự chữ và số lẫn lộn do nhiễu OCR
    INVALID = "invalid"                        # Không thể phân tích thành số


class ParsedNumber(BaseModel):
    """Kết quả phân tích cú pháp một chuỗi số kế toán.

    Attributes:
        value (Optional[Decimal]): Giá trị Decimal chính xác nếu hợp lệ.
        is_valid (bool): True nếu giá trị số sẵn sàng đưa vào tính toán.
        status (NumberStatus): Trạng thái chi tiết (VALID, MISSING, DASH_NOT_APPLICABLE...).
        raw_text (str): Chuỗi ký tự thô ban đầu từ ô bảng biểu hoặc OCR.
        is_negative (bool): Đánh dấu giá trị là số âm (từ dấu trừ hoặc ngoặc đơn).
        unit (str): Đơn vị tiền tệ nhận diện được (VND, USD...).
        warnings (List[str]): Cảnh báo phát sinh trong quá trình chuẩn hóa.
    """
    value: Optional[Decimal] = Field(default=None, description="Giá trị Decimal chính xác nếu hợp lệ")
    is_valid: bool = Field(default=False, description="Cờ hợp lệ phục vụ tính toán")
    status: NumberStatus = Field(default=NumberStatus.INVALID, description="Trạng thái phân loại số học")
    raw_text: str = Field(default="", description="Chuỗi ký tự gốc ban đầu")
    is_negative: bool = Field(default=False, description="True nếu là số âm (trong ngoặc đơn hoặc có dấu trừ)")
    unit: str = Field(default="VND", description="Đơn vị tiền tệ áp dụng")
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo kiểm toán trong quá trình chuẩn hóa")


# Bảng tra cứu hệ số nhân quy đổi các đơn vị tính thông dụng về đồng cơ sở (VND)
UNIT_MULTIPLIERS = {
    "vnd": Decimal("1"),
    "đồng": Decimal("1"),
    "dong": Decimal("1"),
    "đ": Decimal("1"),
    "d": Decimal("1"),
    "nghìn": Decimal("1000"),
    "nghin": Decimal("1000"),
    "nghìn vnd": Decimal("1000"),
    "nghìn đồng": Decimal("1000"),
    "nghin dong": Decimal("1000"),
    "k": Decimal("1000"),
    "triệu": Decimal("1000000"),
    "trieu": Decimal("1000000"),
    "triệu vnd": Decimal("1000000"),
    "triệu đồng": Decimal("1000000"),
    "trieu dong": Decimal("1000000"),
    "tỷ": Decimal("1000000000"),
    "ty": Decimal("1000000000"),
    "tỷ vnd": Decimal("1000000000"),
    "tỷ đồng": Decimal("1000000000"),
    "ty dong": Decimal("1000000000"),
}


class AccountingNumberNormalizer:
    """Bộ chuẩn hóa số kế toán nghiêm ngặt với dấu vết kiểm toán số học.

    Hỗ trợ xử lý định dạng phân cách hàng nghìn / thập phân đa dạng,
    số âm trong ngoặc đơn kế toán và quy đổi tỷ lệ đơn vị tiền tệ.
    """

    # Tập hợp các ký tự gạch ngang chỉ thị số 0 hoặc không phát sinh giao dịch
    DASH_CHARS = {"-", "—", "–", "−", "--", "---"}

    @classmethod
    def parse(
        cls,
        raw_input: Optional[str],
        decimal_convention: str = "auto",
        unit: str = "VND",
        scale_to_base_vnd: bool = False,
        treat_dash_as_zero: bool = True,
    ) -> ParsedNumber:
        """Phân tích chuỗi thô thành số học Decimal chính xác tuyệt đối.

        Args:
            raw_input (Optional[str]): Chuỗi văn bản thô bóc tách từ OCR hoặc ô PDF.
            decimal_convention (str): Quy ước phân cách ('auto', 'vi': 1.234,56, hoặc 'us': 1,234.56).
            unit (str): Đơn vị tiền tệ nhận diện của bảng (mặc định 'VND').
            scale_to_base_vnd (bool): Nếu True và đơn vị là 'triệu', sẽ tự động nhân với 1.000.000.
            treat_dash_as_zero (bool): Nếu True, gán giá trị Decimal(0) cho ký tự gạch ngang '-'.

        Returns:
            ParsedNumber: Đối tượng kết quả chứa giá trị Decimal, trạng thái và cảnh báo.
        """
        raw_text = "" if raw_input is None else str(raw_input).strip()

        # Trường hợp 1: Ô trống hoặc chỉ chứa khoảng trắng
        if not raw_text:
            return ParsedNumber(
                value=None,
                is_valid=False,
                status=NumberStatus.MISSING,
                raw_text=raw_text,
                unit=unit,
                warnings=["Ô trống hoặc chỉ có khoảng trắng; được coi là thiếu dữ liệu"],
            )

        # Trường hợp 2: Dấu gạch ngang chỉ thị số 0 kế toán
        if raw_text in cls.DASH_CHARS:
            dash_val = Decimal("0") if treat_dash_as_zero else None
            return ParsedNumber(
                value=dash_val,
                is_valid=treat_dash_as_zero,
                status=NumberStatus.DASH_NOT_APPLICABLE,
                raw_text=raw_text,
                unit=unit,
                warnings=["Dấu gạch ngang '-' phát hiện: biểu thị số dư bằng 0 hoặc không áp dụng"],
            )

        # Nhận diện và loại bỏ ký hiệu tiền tệ trước khi kiểm tra ký tự nhiễu
        curr_pattern = r"\b(?:VND|VNĐ|vnd|vnđ|USD|usd|EUR|eur)\b|[đĐ\$€£]"
        found_curr = re.findall(curr_pattern, raw_text)
        detected_unit = unit
        if found_curr:
            curr_str = found_curr[0].strip().upper()
            if curr_str in {"VND", "VNĐ", "Đ"}:
                detected_unit = "VND"
            elif curr_str in {"USD", "$"}:
                detected_unit = "USD"
            elif curr_str in {"EUR", "€"}:
                detected_unit = "EUR"

        text_to_parse = re.sub(curr_pattern, "", raw_text).strip()
        text_to_parse = text_to_parse.strip(" |;:*#^")
        text_to_parse = re.sub(r"[\*#\^]+$", "", text_to_parse).strip()
        if re.search(r"\d[a-zA-Z]$", text_to_parse) and not re.search(r"\d[a-zA-Z]{2,}$", text_to_parse):
            text_to_parse = text_to_parse[:-1]

        # Kiểm tra ký tự mơ hồ OCR (lẫn lộn chữ và số bất thường)
        cleaned = text_to_parse.replace(" ", "")
        if re.search(r"\d[a-zA-Z]|[a-zA-Z]\d", cleaned):
            return ParsedNumber(
                value=None,
                is_valid=False,
                status=NumberStatus.AMBIGUOUS,
                raw_text=raw_text,
                unit=detected_unit,
                warnings=[
                    f"Ambiguous OCR characters detected in '{raw_text}'. "
                    "Không thể tự động suy đoán số an toàn nếu thiếu dữ liệu gốc."
                ],
            )

        # Trường hợp 3: Số âm kế toán trong dấu ngoặc đơn hoặc có dấu trừ
        is_negative = False
        text_to_parse = re.sub(r"[\*#\^]+$", "", text_to_parse).strip()

        paren_match = re.match(r"^\s*[\(\[]\s*(.*?)\s*[\)\]]\s*$", text_to_parse)
        if paren_match:
            is_negative = True
            text_to_parse = paren_match.group(1)
        elif text_to_parse.startswith("(") or text_to_parse.startswith("["):
            is_negative = True
            text_to_parse = text_to_parse[1:]
        elif text_to_parse.endswith(")") or text_to_parse.endswith("]"):
            is_negative = True
            text_to_parse = text_to_parse[:-1]
        elif text_to_parse.startswith("-") or text_to_parse.startswith("−"):
            is_negative = True
            text_to_parse = text_to_parse[1:]
        elif text_to_parse.endswith("-") or text_to_parse.endswith("−"):
            is_negative = True
            text_to_parse = text_to_parse[:-1]

        # Loại bỏ các ghi chú thuyết minh trong ngoặc vuông hoặc tròn thừa
        text_to_parse = re.sub(r"\[.*?\]|\(.*?\)", "", text_to_parse)
        text_to_parse = re.sub(r"[\*#\^]+", "", text_to_parse).strip()

        if re.search(r"\d[a-zA-Z]$", text_to_parse) and not re.search(r"\d[a-zA-Z]{2,}$", text_to_parse):
            text_to_parse = text_to_parse[:-1]

        text_to_parse = re.sub(r"\s+", "", text_to_parse)

        # Chuẩn hóa dấu phân cách hàng nghìn và thập phân
        clean_num_str, warnings = cls._resolve_separators(text_to_parse, decimal_convention)
        if clean_num_str is None:
            return ParsedNumber(
                value=None,
                is_valid=False,
                status=NumberStatus.INVALID,
                raw_text=raw_text,
                unit=detected_unit,
                warnings=warnings,
            )

        try:
            val = Decimal(clean_num_str)
            if is_negative:
                val = -val

            multiplier = Decimal("1")
            ret_unit = detected_unit
            if scale_to_base_vnd:
                clean_unit = detected_unit.strip().lower()
                multiplier = UNIT_MULTIPLIERS.get(clean_unit, Decimal("1"))
                if multiplier != Decimal("1"):
                    val = val * multiplier
                    ret_unit = "VND"
                    warnings.append(f"Quy đổi theo đơn vị '{detected_unit}' (hệ số nhân {multiplier})")

            return ParsedNumber(
                value=val,
                is_valid=True,
                status=NumberStatus.VALID,
                raw_text=raw_text,
                is_negative=is_negative,
                unit=ret_unit,
                warnings=warnings,
            )
        except InvalidOperation as exc:
            return ParsedNumber(
                value=None,
                is_valid=False,
                status=NumberStatus.INVALID,
                raw_text=raw_text,
                unit=detected_unit,
                warnings=[f"Lỗi chuyển đổi sang Decimal cho chuỗi '{clean_num_str}': {exc}"],
            )

    @classmethod
    def _resolve_separators(
        cls,
        text: str,
        convention: str,
    ) -> Tuple[Optional[str], List[str]]:
        """Chuẩn hóa dấu chấm và phẩy thành chuỗi số Decimal chuẩn '12345.67'.

        Args:
            text (str): Chuỗi số đã làm sạch khoảng trắng.
            convention (str): Quy ước phân cách ('auto', 'vi', hoặc 'us').

        Returns:
            Tuple[Optional[str], List[str]]: Chuỗi định dạng Decimal chuẩn và danh sách cảnh báo.
        """
        warnings: List[str] = []

        if re.fullmatch(r"\d+", text):
            return text, warnings

        has_dot = "." in text
        has_comma = "," in text

        # Trường hợp có cả dấu chấm và dấu phẩy (VD: 1.234.567,89 hoặc 1,234,567.89)
        if has_dot and has_comma:
            dot_count = text.count(".")
            comma_count = text.count(",")
            if (dot_count >= 2 and comma_count == 1) or (comma_count >= 2 and dot_count == 1):
                mixed_parts = re.split(r"[,.]", text)
                if len(mixed_parts) >= 3 and all(len(p) == 3 for p in mixed_parts[1:]):
                    return "".join(mixed_parts), warnings

            last_dot = text.rfind(".")
            last_comma = text.rfind(",")

            if last_dot > last_comma:
                # Dấu chấm xuất hiện sau cùng -> Dấu chấm là dấu thập phân (kiểu US: 1,234.56)
                comma_parts = text.split(",")
                if len(comma_parts) > 1 and not all(len(p.split(".")[0]) == 3 for p in comma_parts[1:]):
                    return None, [f"Định dạng dấu phẩy hàng nghìn không hợp lệ trong '{text}'"]
                normalized = text.replace(",", "")
            else:
                # Dấu phẩy xuất hiện sau cùng -> Dấu phẩy là dấu thập phân (kiểu VN: 1.234,56)
                dot_parts = text.split(".")
                if len(dot_parts) > 1 and not all(len(p.split(",")[0]) == 3 for p in dot_parts[1:]):
                    return None, [f"Định dạng dấu chấm hàng nghìn không hợp lệ trong '{text}'"]
                normalized = text.replace(".", "").replace(",", ".")
            return normalized, warnings

        # Trường hợp chỉ có dấu chấm (VD: 1.234.567 hoặc 1234.56)
        if has_dot and not has_comma:
            parts = text.split(".")
            if len(parts) > 2:
                # Nhiều dấu chấm -> Chắc chắn là phân cách hàng nghìn kiểu Việt Nam
                if all(len(p) == 3 for p in parts[1:]):
                    return "".join(parts), warnings
                else:
                    return None, [f"Định dạng dấu phân cách không đúng quy cách 3 chữ số trong '{text}'"]

            part_after_dot = parts[1]
            if convention == "vi":
                if len(part_after_dot) == 3:
                    return "".join(parts), warnings
                else:
                    return None, [f"Quy chuẩn Việt Nam nghiêm ngặt yêu cầu 3 chữ số sau dấu chấm hàng nghìn trong '{text}'"]
            elif convention == "us":
                return text, warnings
            else:
                if len(part_after_dot) == 3:
                    warnings.append(
                        f"Dấu chấm đơn trong '{text}' được xử lý như dấu phân cách hàng nghìn (chuẩn kế toán VN)"
                    )
                    return "".join(parts), warnings
                else:
                    return text, warnings

        # Trường hợp chỉ có dấu phẩy (VD: 1,234,567 hoặc 1234,56)
        if has_comma and not has_dot:
            parts = text.split(",")
            if len(parts) > 2:
                if all(len(p) == 3 for p in parts[1:]):
                    return "".join(parts), warnings
                else:
                    return None, [f"Định dạng dấu phân cách không đúng quy cách 3 chữ số trong '{text}'"]

            part_after_comma = parts[1]
            if convention == "vi":
                return f"{parts[0]}.{parts[1]}", warnings
            elif convention == "us":
                if len(part_after_comma) == 3:
                    return "".join(parts), warnings
                else:
                    return None, [f"Quy chuẩn US nghiêm ngặt yêu cầu 3 chữ số sau dấu phẩy hàng nghìn trong '{text}'"]
            else:
                if len(part_after_comma) == 3:
                    warnings.append(
                        f"Dấu phẩy đơn trong '{text}' được xử lý như dấu phân cách hàng nghìn"
                    )
                    return "".join(parts), warnings
                else:
                    return f"{parts[0]}.{parts[1]}", warnings

        return None, [f"Định dạng số không nhận dạng được: '{text}'"]

    @classmethod
    def clean_label(cls, raw_label: str) -> str:
        """Làm sạch nhãn tên chỉ tiêu kế toán để chuẩn bị cho việc đối sánh từ điển.

        Loại bỏ các tiền tố La Mã (I., II.), chữ cái đầu mục (A., B.), số thứ tự,
        dấu hoa thị và các khoảng trắng dư thừa.

        Args:
            raw_label (str): Nhãn gốc từ bảng BCTC.

        Returns:
            str: Nhãn đã làm sạch, viết thường.
        """
        if not raw_label:
            return ""

        text = raw_label.strip()
        text = re.sub(r"<[^>]+>", " ", text).strip()
        text = re.sub(r"^(?:[IVXLCDM]+)[\.\-\:\s]+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^[A-Z][\.\-\:\s]+", "", text)
        text = re.sub(r"^\d+[\.\-\:\s]+", "", text)
        text = re.sub(r"\(\*\)|\*|\(\d+\)", "", text)
        text = re.sub(r"^[\-\:\.\s]+|[\-\:\.\s]+$", "", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip().lower()

    @classmethod
    def strip_accents(cls, text: str) -> str:
        """Xóa bỏ dấu tiếng Việt để đối sánh mềm mại không phân biệt dấu.

        Args:
            text (str): Chuỗi tiếng Việt có dấu.

        Returns:
            str: Chuỗi tiếng Việt không dấu, viết thường.
        """
        if not text:
            return ""
        t = text.replace("đ", "d").replace("Đ", "D")
        nfkd = unicodedata.normalize("NFKD", t)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()
