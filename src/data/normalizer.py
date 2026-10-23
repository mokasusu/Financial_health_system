"""Controlled accounting number and unit normalization for Vietnamese financial statements."""
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import List, Optional
from pydantic import BaseModel, Field


class NumberStatus(str, Enum):
    """Classification status of normalized number extraction."""
    VALID = "valid"                            # Successfully parsed to exact Decimal
    MISSING = "missing"                        # Empty cell or whitespace only
    DASH_NOT_APPLICABLE = "dash_na"            # Dash '-' indicating no transaction or zero
    AMBIGUOUS = "ambiguous"                    # Contains mixed letters/noise (e.g. OCR O vs 0)
    INVALID = "invalid"                        # Could not be parsed as a numeric value


class ParsedNumber(BaseModel):
    """Result of parsing an accounting number string."""
    value: Optional[Decimal] = Field(default=None, description="Exact Decimal value if valid")
    is_valid: bool = Field(default=False)
    status: NumberStatus = Field(default=NumberStatus.INVALID)
    raw_text: str = Field(default="")
    is_negative: bool = Field(default=False)
    unit: str = Field(default="VND")
    warnings: List[str] = Field(default_factory=list)


# Units scaling multipliers
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
    """Strict accounting number normalizer with audit provenance and ambiguity checks."""

    # Dash characters representing zero or not applicable
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
        """Parse raw string into exact Decimal accounting value.

        Args:
            raw_input: Unprocessed string from OCR or PDF cell.
            decimal_convention: 'auto', 'vi' (1.234,56), or 'us' (1,234.56).
            unit: Detected or assumed unit of the table (defaults to 'VND').
            scale_to_base_vnd: If True and unit is e.g. 'trieu', multiplies by 1,000,000.
            treat_dash_as_zero: If True, assigns Decimal(0) to dashes while marking status.

        Returns:
            ParsedNumber containing the Decimal value, status, and warnings.
        """
        raw_text = "" if raw_input is None else str(raw_input).strip()

        # Case 1: Empty or whitespace
        if not raw_text:
            return ParsedNumber(
                value=None,
                is_valid=False,
                status=NumberStatus.MISSING,
                raw_text=raw_text,
                unit=unit,
                warnings=["Empty or whitespace cell; treated as missing data"],
            )

        # Case 2: Exact Dash
        if raw_text in cls.DASH_CHARS:
            dash_val = Decimal("0") if treat_dash_as_zero else None
            return ParsedNumber(
                value=dash_val,
                is_valid=treat_dash_as_zero,
                status=NumberStatus.DASH_NOT_APPLICABLE,
                raw_text=raw_text,
                unit=unit,
                warnings=["Dash '-' detected: indicates zero balance or non-applicable line"],
            )

        # Detect and safely strip currency symbols/codes before checking ambiguous characters
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

        # Check for ambiguous characters (e.g. OCR letter O, l, I inside numbers)
        # We do NOT replace them guessing; we report ambiguity for manual/audit review.
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
                    "Cannot safely guess numbers without ground truth."
                ],
            )

        # Case 3: Parenthesized negative numbers: e.g. (12.345) or (12,345)
        is_negative = False

        # Check for parentheses: (123.456)
        paren_match = re.match(r"^\s*\(\s*(.*?)\s*\)\s*$", text_to_parse)
        if paren_match:
            is_negative = True
            text_to_parse = paren_match.group(1)
        elif text_to_parse.startswith("-") or text_to_parse.startswith("−"):
            is_negative = True
            text_to_parse = text_to_parse[1:]
        elif text_to_parse.endswith("-") or text_to_parse.endswith("−"):
            is_negative = True
            text_to_parse = text_to_parse[:-1]

        # Strip remaining packaging symbols (brackets, asterisk note markers like (*))
        text_to_parse = re.sub(r"\[.*?\]|\(.*?\)", "", text_to_parse)
        text_to_parse = text_to_parse.replace("*", "").strip()

        # Remove inner whitespace e.g. "123 456 789"
        text_to_parse = re.sub(r"\s+", "", text_to_parse)

        # Resolve thousand and decimal separators
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

            # Apply unit scaling if requested
            multiplier = Decimal("1")
            ret_unit = detected_unit
            if scale_to_base_vnd:
                clean_unit = detected_unit.strip().lower()
                multiplier = UNIT_MULTIPLIERS.get(clean_unit, Decimal("1"))
                if multiplier != Decimal("1"):
                    val = val * multiplier
                    ret_unit = "VND"  # Reset unit to base VND to prevent subsequent double scaling
                    warnings.append(f"Scaled by unit '{detected_unit}' (factor {multiplier})")

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
                warnings=[f"Decimal conversion failure for '{clean_num_str}': {exc}"],
            )

    @classmethod
    def _resolve_separators(
        cls,
        text: str,
        convention: str,
    ) -> tuple[Optional[str], List[str]]:
        """Normalize thousands and decimal separators into standard Decimal string '12345.67'."""
        warnings: List[str] = []

        # Check if only digits exist
        if re.fullmatch(r"\d+", text):
            return text, warnings

        has_dot = "." in text
        has_comma = "," in text

        # Format with both dot and comma
        if has_dot and has_comma:
            last_dot = text.rfind(".")
            last_comma = text.rfind(",")

            if last_dot > last_comma:
                # Comma is thousands, Dot is decimal: e.g. 1,234,567.89 (US style)
                comma_parts = text.split(",")
                if len(comma_parts) > 1 and not all(len(p.split(".")[0]) == 3 for p in comma_parts[1:]):
                    return None, [f"Invalid thousands comma format in '{text}'"]
                normalized = text.replace(",", "")
            else:
                # Dot is thousands, Comma is decimal: e.g. 1.234.567,89 (VN style)
                dot_parts = text.split(".")
                if len(dot_parts) > 1 and not all(len(p.split(",")[0]) == 3 for p in dot_parts[1:]):
                    return None, [f"Invalid thousands dot format in '{text}'"]
                normalized = text.replace(".", "").replace(",", ".")
            return normalized, warnings

        # Format with ONLY DOT: e.g. 123.456.789 OR 123.45
        if has_dot and not has_comma:
            parts = text.split(".")
            # If multiple dots e.g. 1.234.567 -> verify every part after first has exactly 3 digits
            if len(parts) > 2:
                if all(len(p) == 3 for p in parts[1:]):
                    return "".join(parts), warnings
                else:
                    return None, [f"Invalid thousands separator format: segments do not have 3 digits in '{text}'"]

            # Single dot: e.g. 356.691 or 12.5
            part_after_dot = parts[1]
            if convention == "vi":
                # In strict VN convention, dot is thousands separator
                if len(part_after_dot) == 3:
                    return "".join(parts), warnings
                else:
                    return None, [f"Strict Vietnamese convention requires 3 digits after thousands dot in '{text}'"]
            elif convention == "us":
                return text, warnings
            else:
                # Auto convention
                # In accounting reports, 3 digits after dot usually indicates thousands (e.g. 450.000)
                if len(part_after_dot) == 3:
                    warnings.append(
                        f"Single dot in '{text}' treated as thousands separator (accounting standard)"
                    )
                    return "".join(parts), warnings
                else:
                    return text, warnings

        # Format with ONLY COMMA: e.g. 123,456,789 OR 123,45
        if has_comma and not has_dot:
            parts = text.split(",")
            if len(parts) > 2:
                if all(len(p) == 3 for p in parts[1:]):
                    return "".join(parts), warnings
                else:
                    return None, [f"Invalid thousands separator format: segments do not have 3 digits in '{text}'"]

            part_after_comma = parts[1]
            if convention == "vi":
                # In strict VN convention, single comma is decimal separator
                return f"{parts[0]}.{parts[1]}", warnings
            elif convention == "us":
                if len(part_after_comma) == 3:
                    return "".join(parts), warnings
                else:
                    return None, [f"Strict US convention requires 3 digits after thousands comma in '{text}'"]
            else:
                if len(part_after_comma) == 3:
                    warnings.append(
                        f"Single comma in '{text}' treated as thousands separator"
                    )
                    return "".join(parts), warnings
                else:
                    # e.g. 12,5% or 100,5 -> decimal separator
                    return f"{parts[0]}.{parts[1]}", warnings

        return None, [f"Unrecognized number format: '{text}'"]

    @classmethod
    def clean_label(cls, raw_label: str) -> str:
        """Clean an accounting line item label for matching.

        Strips Roman numerals, numbers, asterisks, punctuation, extra whitespace.
        """
        if not raw_label:
            return ""

        text = raw_label.strip()

        # Remove HTML tags if present (e.g. <td> or <tr>)
        text = re.sub(r"<[^>]+>", " ", text).strip()

        # Remove Roman numerals prefix (e.g. "I. ", "II - ", "III. ")
        text = re.sub(r"^(?:[IVXLCDM]+)[\.\-\:\s]+", "", text, flags=re.IGNORECASE)

        # Remove Letter prefix (e.g. "A. ", "B - ")
        text = re.sub(r"^[A-Z][\.\-\:\s]+", "", text)

        # Remove Arabic numbers prefix (e.g. "1. ", "2. ", "1 - ")
        text = re.sub(r"^\d+[\.\-\:\s]+", "", text)

        # Remove asterisks and note references (*), (1), v.v.
        text = re.sub(r"\(\*\)|\*|\(\d+\)", "", text)

        # Remove leading/trailing punctuation and collapse multiple spaces
        text = re.sub(r"^[\-\:\.\s]+|[\-\:\.\s]+$", "", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip().lower()
