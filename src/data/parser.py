"""Semantic parser and line item mapping for Vietnamese financial statements (Circular 200)."""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from src.data.normalizer import AccountingNumberNormalizer, NumberStatus
from src.data.schema import (
    AccountingStandard,
    BalanceSheet,
    CashFlowStatement,
    FinancialReport,
    IncomeStatement,
    LineItem,
    MappingMethod,
    MappingStatus,
)
from src.ocr.models import DocumentExtractionResult, PageExtractionResult

logger = logging.getLogger(__name__)


# ==============================================================================
# CANONICAL DEFINITIONS FOR CIRCULAR 200 / VAS
# ==============================================================================

BALANCE_SHEET_CANONICAL = {
    "current_assets": {
        "code": "100",
        "standard_label": "Tài sản ngắn hạn",
        "synonyms": ["tai san ngan han", "tsnh", "tai san luu dong", "a tai san ngan han"],
        "disambiguation_antipatterns": ["dai han", "khac"],
    },
    "cash_and_equivalents": {
        "code": "110",
        "standard_label": "Tiền và các khoản tương đương tiền",
        "synonyms": ["tien va cac khoan tuong duong tien", "tien va tuong duong tien", "tien"],
        "disambiguation_antipatterns": ["dau tu", "phai thu"],
    },
    "short_term_investments": {
        "code": "120",
        "standard_label": "Đầu tư tài chính ngắn hạn",
        "synonyms": ["dau tu tai chinh ngan han", "dau tu ngan han", "chung khoan kinh doanh"],
        "disambiguation_antipatterns": ["dai han"],
    },
    "short_term_receivables": {
        "code": "130",
        "standard_label": "Các khoản phải thu ngắn hạn",
        "synonyms": ["cac khoan phai thu ngan han", "phai thu ngan han", "phai thu khach hang"],
        "disambiguation_antipatterns": ["dai han", "khac", "noi bo"],
    },
    "inventory": {
        "code": "140",
        "standard_label": "Hàng tồn kho",
        "synonyms": ["hang ton kho", "htk", "ton kho"],
        "disambiguation_antipatterns": ["du phong"],
    },
    "other_current_assets": {
        "code": "150",
        "standard_label": "Tài sản ngắn hạn khác",
        "synonyms": ["tai san ngan han khac", "tsnh khac"],
        "disambiguation_antipatterns": ["dai han"],
    },
    "non_current_assets": {
        "code": "200",
        "standard_label": "Tài sản dài hạn",
        "synonyms": ["tai san dai han", "tsdh", "tai san co dinh va dau tu dai han", "b tai san dai han"],
        "disambiguation_antipatterns": ["ngan han"],
    },
    "long_term_receivables": {
        "code": "210",
        "standard_label": "Các khoản phải thu dài hạn",
        "synonyms": ["cac khoan phai thu dai han", "phai thu dai han"],
        "disambiguation_antipatterns": ["ngan han"],
    },
    "fixed_assets": {
        "code": "220",
        "standard_label": "Tài sản cố định",
        "synonyms": ["tai san co dinh", "tscd"],
        "disambiguation_antipatterns": ["vo hinh", "thue tai chinh", "nguyen gia", "hao mon"],
    },
    "long_term_investments": {
        "code": "250",
        "standard_label": "Đầu tư tài chính dài hạn",
        "synonyms": ["dau tu tai chinh dai han", "dau tu dai han"],
        "disambiguation_antipatterns": ["ngan han"],
    },
    "total_assets": {
        "code": "270",
        "standard_label": "Tổng cộng tài sản",
        "synonyms": ["tong cong tai san", "tong tai san", "tong cong tai san 270"],
        "disambiguation_antipatterns": ["nguon von", "ngan han", "dai han"],
    },
    "liabilities": {
        "code": "300",
        "standard_label": "Nợ phải trả",
        "synonyms": ["no phai tra", "tong no phai tra", "c no phai tra"],
        "disambiguation_antipatterns": ["von chu so huu", "ngan han", "dai han"],
    },
    "current_liabilities": {
        "code": "310",
        "standard_label": "Nợ ngắn hạn",
        "synonyms": ["no ngan han"],
        "disambiguation_antipatterns": ["dai han"],
    },
    "non_current_liabilities": {
        "code": "330",
        "standard_label": "Nợ dài hạn",
        "synonyms": ["no dai han"],
        "disambiguation_antipatterns": ["ngan han"],
    },
    "equity": {
        "code": "400",
        "standard_label": "Vốn chủ sở hữu",
        "synonyms": ["von chu so huu", "vcsh", "d von chu so huu"],
        "disambiguation_antipatterns": ["no phai tra", "nguon von"],
    },
    "total_equity_and_liabilities": {
        "code": "440",
        "standard_label": "Tổng cộng nguồn vốn",
        "synonyms": ["tong cong nguon von", "tong nguon von", "tong cong nguon von 440"],
        "disambiguation_antipatterns": ["tai san", "von chu so huu"],
    },
}

INCOME_STATEMENT_CANONICAL = {
    "gross_revenue": {
        "code": "01",
        "standard_label": "Doanh thu bán hàng và cung cấp dịch vụ",
        "synonyms": [
            "doanh thu ban hang va cung cap dich vu",
            "doanh thu ban hang",
            "tong doanh thu ban hang",
        ],
        "disambiguation_antipatterns": ["thuan", "tai chinh"],
    },
    "revenue_deductions": {
        "code": "02",
        "standard_label": "Các khoản giảm trừ doanh thu",
        "synonyms": ["cac khoan giam tru doanh thu", "giam tru doanh thu"],
        "disambiguation_antipatterns": [],
    },
    "net_revenue": {
        "code": "10",
        "standard_label": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
        "synonyms": [
            "doanh thu thuan ve ban hang va cung cap dich vu",
            "doanh thu thuan",
            "doanh thu thuan ve ban hang",
        ],
        "disambiguation_antipatterns": ["chua giam tru"],
    },
    "cost_of_goods_sold": {
        "code": "11",
        "standard_label": "Giá vốn hàng bán",
        "synonyms": ["gia von hang ban", "gia von"],
        "disambiguation_antipatterns": [],
    },
    "gross_profit": {
        "code": "20",
        "standard_label": "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
        "synonyms": [
            "loi nhuan gop ve ban hang va cung cap dich vu",
            "loi nhuan gop",
            "lai gop",
        ],
        "disambiguation_antipatterns": ["thuan", "truoc thue", "sau thue"],
    },
    "financial_income": {
        "code": "21",
        "standard_label": "Doanh thu hoạt động tài chính",
        "synonyms": ["doanh thu hoat dong tai chinh", "doanh thu tai chinh"],
        "disambiguation_antipatterns": ["chi phi"],
    },
    "financial_expenses": {
        "code": "22",
        "standard_label": "Chi phí tài chính",
        "synonyms": ["chi phi tai chinh"],
        "disambiguation_antipatterns": ["lai vay", "doanh thu"],
    },
    "interest_expenses": {
        "code": "23",
        "standard_label": "Chi phí lãi vay",
        "synonyms": ["chi phi lai vay", "trong do chi phi lai vay", "lai vay"],
        "disambiguation_antipatterns": [],
    },
    "selling_expenses": {
        "code": "25",
        "standard_label": "Chi phí bán hàng",
        "synonyms": ["chi phi ban hang"],
        "disambiguation_antipatterns": ["quan ly"],
    },
    "administrative_expenses": {
        "code": "26",
        "standard_label": "Chi phí quản lý doanh nghiệp",
        "synonyms": ["chi phi quan ly doanh nghiep", "chi phi quan ly", "cp qldn"],
        "disambiguation_antipatterns": ["ban hang"],
    },
    "operating_profit": {
        "code": "30",
        "standard_label": "Lợi nhuận thuần từ hoạt động kinh doanh",
        "synonyms": [
            "loi nhuan thuan tu hoat dong kinh doanh",
            "loi nhuan thuan hdkd",
            "loi nhuan tu hoat dong kinh doanh",
        ],
        "disambiguation_antipatterns": ["gop", "truoc thue", "sau thue"],
    },
    "other_income": {
        "code": "31",
        "standard_label": "Thu nhập khác",
        "synonyms": ["thu nhap khac"],
        "disambiguation_antipatterns": ["chi phi", "loi nhuan"],
    },
    "other_expenses": {
        "code": "32",
        "standard_label": "Chi phí khác",
        "synonyms": ["chi phi khac"],
        "disambiguation_antipatterns": ["thu nhap", "loi nhuan"],
    },
    "net_other_profit": {
        "code": "40",
        "standard_label": "Lợi nhuận khác",
        "synonyms": ["loi nhuan khac"],
        "disambiguation_antipatterns": [],
    },
    "net_profit_before_tax": {
        "code": "50",
        "standard_label": "Tổng lợi nhuận kế toán trước thuế",
        "synonyms": [
            "tong loi nhuan ke toan truoc thue",
            "loi nhuan truoc thue",
            "tong loi nhuan truoc thue",
        ],
        "disambiguation_antipatterns": ["sau thue", "gop"],
    },
    "income_tax_expense": {
        "code": "51",
        "standard_label": "Chi phí thuế thu nhập doanh nghiệp hiện hành",
        "synonyms": [
            "chi phi thue thu nhap doanh nghiep hien hanh",
            "chi phi thue tndn",
            "thue thu nhap doanh nghiep",
        ],
        "disambiguation_antipatterns": [],
    },
    "net_profit_after_tax": {
        "code": "60",
        "standard_label": "Lợi nhuận sau thuế thu nhập doanh nghiệp",
        "synonyms": [
            "loi nhuan sau thue thu nhap doanh nghiep",
            "loi nhuan sau thue",
            "lai sau thue",
            "loi nhuan thuan sau thue",
        ],
        "disambiguation_antipatterns": ["truoc thue", "gop"],
    },
}


class FinancialStatementParser:
    """Parser to transform OCR documents or structured tables into normalized FinancialReport."""

    def __init__(self, decimal_convention: str = "auto"):
        self.decimal_convention = decimal_convention

    def parse(
        self,
        document_input: Union[DocumentExtractionResult, str, List[PageExtractionResult]],
        source_name: Optional[str] = None,
    ) -> FinancialReport:
        """Parse document extraction into a validated FinancialReport.

        Args:
            document_input: DocumentExtractionResult, text string, or list of pages.
            source_name: Optional document identifier.

        Returns:
            FinancialReport containing parsed BalanceSheet and IncomeStatement.
        """
        doc_name = source_name or "Financial Document"
        pages_to_process: List[Tuple[int, str, List[List[List[Optional[str]]]]]] = []

        if isinstance(document_input, DocumentExtractionResult):
            doc_name = document_input.source_name
            for p in document_input.pages:
                pages_to_process.append((p.page_number, p.text, p.tables))
        elif isinstance(document_input, str):
            # Check if text contains standard page delimiters (e.g. ===== PAGE \d+ =====)
            if re.search(r"=====\s*PAGE\s+\d+\s*=====", document_input):
                splits = re.split(r"=====\s*PAGE\s+(\d+)\s*=====", document_input)
                # splits[0] is header before Page 1; then (p_num, p_text) pairs
                for i in range(1, len(splits), 2):
                    p_num = int(splits[i])
                    p_text = splits[i + 1]
                    pages_to_process.append((p_num, p_text, []))
            else:
                pages_to_process.append((1, document_input, []))
        elif isinstance(document_input, list):
            for p in document_input:
                pages_to_process.append((p.page_number, p.text, p.tables))

        balance_sheet = BalanceSheet()
        income_statement = IncomeStatement()

        # Step 1: Detect Document metadata (unit, fiscal year, company name)
        full_text = "\n".join(text for _, text, _ in pages_to_process)
        detected_unit = self._detect_unit(full_text)
        fiscal_year = self._detect_fiscal_year(full_text)
        company_name = self._detect_company_name(full_text)

        balance_sheet.currency = detected_unit
        income_statement.currency = detected_unit

        # Step 2: Process pages and detect statement context
        current_context = "unknown"

        for page_num, text, tables in pages_to_process:
            page_context = self._detect_statement_type(text)
            if page_context != "unknown":
                current_context = page_context

            # Method A: Process structured tables if present (from pdfplumber)
            if tables:
                for table in tables:
                    self._parse_raw_table(
                        table=table,
                        page_num=page_num,
                        context=current_context,
                        unit=detected_unit,
                        bs=balance_sheet,
                        is_=income_statement,
                    )

            # Method B: Process text lines or HTML <table> tags in page text
            self._parse_text_lines_or_html(
                text=text,
                page_num=page_num,
                context=current_context,
                unit=detected_unit,
                bs=balance_sheet,
                is_=income_statement,
            )

        return FinancialReport(
            company_name=company_name,
            fiscal_year=fiscal_year,
            unit=detected_unit,
            source_document=doc_name,
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )

    def _parse_text_lines_or_html(
        self,
        text: str,
        page_num: int,
        context: str,
        unit: str,
        bs: BalanceSheet,
        is_: IncomeStatement,
    ) -> None:
        """Parse raw text lines and embedded HTML <table> rows."""
        # 1. Check for HTML table rows: <tr><td>...</td></tr>
        tr_matches = re.findall(r"<tr>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL)
        if tr_matches:
            for tr_content in tr_matches:
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr_content, flags=re.IGNORECASE | re.DOTALL)
                clean_tds = [re.sub(r"<[^>]+>", "", td).strip() for td in tds]
                if clean_tds:
                    self._process_row_tokens(clean_tds, page_num, context, unit, bs, is_)
            return

        # 2. Plain text line processing
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for lines with label and numbers
            # Check if line matches: [Label] [Code optional] [Number 1] [Number 2 optional]
            tokens = [t.strip() for t in re.split(r"\t+|\s{2,}", line) if t.strip()]
            if len(tokens) >= 2:
                self._process_row_tokens(tokens, page_num, context, unit, bs, is_)

    def _parse_raw_table(
        self,
        table: List[List[Optional[str]]],
        page_num: int,
        context: str,
        unit: str,
        bs: BalanceSheet,
        is_: IncomeStatement,
    ) -> None:
        """Parse a 2D matrix of cells extracted by pdfplumber."""
        for row in table:
            if not row:
                continue
            clean_row = [str(cell).strip() if cell is not None else "" for cell in row]
            if any(clean_row):
                self._process_row_tokens(clean_row, page_num, context, unit, bs, is_)

    def _process_row_tokens(
        self,
        row_cells: List[str],
        page_num: int,
        context: str,
        unit: str,
        bs: BalanceSheet,
        is_: IncomeStatement,
    ) -> None:
        """Analyze row tokens, identify label, item code, and numeric values."""
        if not row_cells or len(row_cells) < 2:
            return

        # Do not extract primary statement items from Notes to Financial Statements (B 09 - DN)
        if context == "notes":
            return

        # Find the text label column (usually column 0 or 1 if col 0 is index like A, B, I, 1)
        label_idx = 0
        if len(row_cells[0]) <= 3 and len(row_cells) > 1 and len(row_cells[1]) > 3:
            label_idx = 1

        raw_label = row_cells[label_idx]
        if not raw_label or raw_label.lower() in {"chỉ tiêu", "chi tieu", "tài sản", "nguồn vốn", "mã số"}:
            return

        # Look for item code (2-3 digit number like 100, 110, 01, 10) and valid numbers
        item_code: Optional[str] = None
        number_values: List[Decimal] = []

        for idx, cell in enumerate(row_cells):
            if idx == label_idx or (label_idx == 1 and idx == 0):
                continue
            cell_clean = cell.strip()
            if not cell_clean:
                continue

            # Check if cell is an item code e.g. "100", "110", "01"
            if re.fullmatch(r"\d{2,3}", cell_clean) and item_code is None:
                item_code = cell_clean
                continue

            # Filter out non-numeric cells (e.g. note references like 'VI.1.', 'V.3.')
            norm_res = AccountingNumberNormalizer.parse(
                cell_clean, decimal_convention=self.decimal_convention, unit=unit
            )
            if norm_res.is_valid and norm_res.value is not None:
                number_values.append(norm_res.value)

        if not number_values:
            return

        cur_val = number_values[0] if len(number_values) > 0 else None
        prev_val = number_values[1] if len(number_values) > 1 else None

        # Perform Semantic Mapping
        line_item = self.map_line_item(
            raw_label=raw_label,
            item_code=item_code,
            cur_val=cur_val,
            prev_val=prev_val,
            unit=unit,
            source_page=page_num,
            context=context,
        )

        # Assign to target statement (prioritize keeping earlier primary statement entries)
        if line_item.canonical_key in BALANCE_SHEET_CANONICAL:
            existing = bs.items.get(line_item.canonical_key)
            if (
                existing is None
                or existing.mapping_status != MappingStatus.MAPPED
                or line_item.confidence_score > existing.confidence_score
            ):
                bs.items[line_item.canonical_key] = line_item
            else:
                bs.unmapped_items.append(line_item)
        elif line_item.canonical_key in INCOME_STATEMENT_CANONICAL:
            existing = is_.items.get(line_item.canonical_key)
            if (
                existing is None
                or existing.mapping_status != MappingStatus.MAPPED
                or line_item.confidence_score > existing.confidence_score
            ):
                is_.items[line_item.canonical_key] = line_item
            else:
                is_.unmapped_items.append(line_item)
        else:
            if context == "income_statement":
                is_.unmapped_items.append(line_item)
            else:
                bs.unmapped_items.append(line_item)

    def map_line_item(
        self,
        raw_label: str,
        item_code: Optional[str],
        cur_val: Optional[Any],
        prev_val: Optional[Any],
        unit: str,
        source_page: int,
        context: str = "unknown",
    ) -> LineItem:
        """Map a line item to a canonical key using prioritized rules."""
        cleaned_label = AccountingNumberNormalizer.clean_label(raw_label)
        warnings: List[str] = []

        # Target dictionary based on context or full search
        canon_dict: Dict[str, Dict[str, Any]] = {}
        if context == "balance_sheet":
            canon_dict = BALANCE_SHEET_CANONICAL
        elif context == "income_statement":
            canon_dict = INCOME_STATEMENT_CANONICAL
        elif context == "notes":
            canon_dict = {}
        else:
            # Combined dictionary
            canon_dict = {**BALANCE_SHEET_CANONICAL, **INCOME_STATEMENT_CANONICAL}

        # Priority 1: Exact Item Code Match (if valid item code provided)
        if item_code:
            clean_code = item_code.zfill(2)  # "1" -> "01"
            for c_key, c_meta in canon_dict.items():
                if c_meta["code"] == clean_code or c_meta["code"] == item_code:
                    return LineItem(
                        raw_label=raw_label,
                        normalized_label=cleaned_label,
                        canonical_key=c_key,
                        item_code=item_code,
                        current_period_value=cur_val,
                        previous_period_value=prev_val,
                        unit=unit,
                        source_page=source_page,
                        mapping_method=MappingMethod.CODE_EXACT,
                        mapping_status=MappingStatus.MAPPED,
                        confidence_score=0.98,
                    )

        # Priority 2: Exact Normalized Label Match
        for c_key, c_meta in canon_dict.items():
            std_cleaned = AccountingNumberNormalizer.clean_label(c_meta["standard_label"])
            if cleaned_label == std_cleaned:
                return LineItem(
                    raw_label=raw_label,
                    normalized_label=cleaned_label,
                    canonical_key=c_key,
                    item_code=c_meta["code"],
                    current_period_value=cur_val,
                    previous_period_value=prev_val,
                    unit=unit,
                    source_page=source_page,
                    mapping_method=MappingMethod.LABEL_EXACT,
                    mapping_status=MappingStatus.MAPPED,
                    confidence_score=0.95,
                )

        # Priority 3: Synonym Match with Disambiguation Anti-Patterns Check
        candidate_matches: List[Tuple[str, float]] = []

        for c_key, c_meta in canon_dict.items():
            # Check anti-patterns first to avoid false positives (e.g. short-term vs long-term)
            has_antipattern = any(
                anti in cleaned_label for anti in c_meta.get("disambiguation_antipatterns", [])
            )
            if has_antipattern:
                continue

            for syn in c_meta["synonyms"]:
                syn_clean = AccountingNumberNormalizer.clean_label(syn)
                if syn_clean == cleaned_label:
                    candidate_matches.append((c_key, 0.90))
                    break
                elif syn_clean in cleaned_label or (cleaned_label in syn_clean and len(cleaned_label) >= 6):
                    # Partial match
                    if len(syn_clean) >= 6:  # Prevent trivial substrings
                        candidate_matches.append((c_key, 0.75))
                        break

        if len(candidate_matches) == 1:
            best_key, conf = candidate_matches[0]
            status = MappingStatus.MAPPED if conf >= 0.85 else MappingStatus.NEEDS_REVIEW
            return LineItem(
                raw_label=raw_label,
                normalized_label=cleaned_label,
                canonical_key=best_key,
                item_code=canon_dict[best_key]["code"],
                current_period_value=cur_val,
                previous_period_value=prev_val,
                unit=unit,
                source_page=source_page,
                mapping_method=MappingMethod.LABEL_SYNONYM,
                mapping_status=status,
                confidence_score=conf,
                warnings=warnings,
            )
        elif len(candidate_matches) > 1:
            warnings.append(
                f"Multiple mapping candidates found ({[k for k, _ in candidate_matches]}); marked for review"
            )
            # Pick highest confidence but mark as needs_review
            candidate_matches.sort(key=lambda x: x[1], reverse=True)
            top_key, top_conf = candidate_matches[0]
            return LineItem(
                raw_label=raw_label,
                normalized_label=cleaned_label,
                canonical_key=top_key,
                item_code=canon_dict[top_key]["code"],
                current_period_value=cur_val,
                previous_period_value=prev_val,
                unit=unit,
                source_page=source_page,
                mapping_method=MappingMethod.LABEL_SYNONYM,
                mapping_status=MappingStatus.NEEDS_REVIEW,
                confidence_score=top_conf * 0.8,
                warnings=warnings,
            )

        # Unmapped
        return LineItem(
            raw_label=raw_label,
            normalized_label=cleaned_label,
            canonical_key=None,
            item_code=item_code,
            current_period_value=cur_val,
            previous_period_value=prev_val,
            unit=unit,
            source_page=source_page,
            mapping_method=MappingMethod.UNMAPPED,
            mapping_status=MappingStatus.UNMAPPED,
            confidence_score=0.0,
            warnings=["No canonical financial key matched"],
        )

    @staticmethod
    def _detect_statement_type(text: str) -> str:
        """Detect which financial statement a page text belongs to."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        header_lines = lines[:15]
        header_text = "\n".join(header_lines).upper()

        # If it's a Table of Contents (Mục lục), do not misidentify as statement
        if "MỤC LỤC" in header_text or "MUC LUC" in header_text:
            return "unknown"

        # Check for Notes / Thuyết minh (B 09 - DN)
        if (
            re.search(r"B\s*09\s*-\s*DN", header_text)
            or any(("BẢN THUYẾT MINH" in l.upper() or "BAN THUYET MINH" in l.upper()) and len(l) < 60 for l in header_lines)
        ):
            return "notes"

        # Check for Balance Sheet (B 01 - DN)
        if (
            re.search(r"B\s*01\s*-\s*DN", header_text)
            or any(("BẢNG CÂN ĐỐI KẾ TOÁN" in l.upper() or "BANG CAN DOI KE TOAN" in l.upper()) and len(l) < 60 for l in header_lines)
        ):
            return "balance_sheet"

        # Check for Income Statement (B 02 - DN)
        if (
            re.search(r"B\s*02\s*-\s*DN", header_text)
            or any(("KẾT QUẢ HOẠT ĐỘNG KINH DOANH" in l.upper() or "KET QUA HOAT DONG KINH DOANH" in l.upper()) and len(l) < 60 for l in header_lines)
        ):
            return "income_statement"

        # Check for Cash Flow (B 03 - DN)
        if (
            re.search(r"B\s*03\s*-\s*DN", header_text)
            or any(("LƯU CHUYỂN TIỀN TỆ" in l.upper() or "LUU CHUYEN TIEN TE" in l.upper() or "LUU CHUYÊN TIÊN TÊ" in l.upper()) and len(l) < 60 for l in header_lines)
        ):
            return "cash_flow"

        return "unknown"

    @staticmethod
    def _detect_unit(text: str) -> str:
        """Detect reporting currency unit from document header."""
        match = re.search(r"(?:Đơn vị tính|ĐVT|Don vi tinh)\s*[:\-]?\s*([^\n\r,;]+)", text, re.IGNORECASE)
        if match:
            raw_unit = match.group(1).split("\n")[0].strip()
            # Normalize to standard unit
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
    def _detect_fiscal_year(text: str) -> Optional[int]:
        """Detect fiscal year from statements e.g. 2020 or 31/12/2020."""
        match = re.search(r"(?:năm|nam|31/12/|31-12-)\s*(\d{4})", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _detect_company_name(text: str) -> Optional[str]:
        """Extract target audited company name, skipping auditing firms."""
        matches = re.findall(r"(?:CÔNG TY|CONG TY)\s+[A-Z0-9À-Ỹ\s\.\-]+(?:\n|$)", text, re.IGNORECASE)
        for m in matches:
            clean = m.strip()
            if not any(k in clean.upper() for k in ["KIỂM TOÁN", "KIEM TOAN", "AUDIT", "TNHH KIỂM TOÁN"]):
                return clean
        return matches[0].strip() if matches else None
