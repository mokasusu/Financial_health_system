"""Dịch vụ trích xuất và ánh xạ ngữ nghĩa chỉ tiêu Báo cáo Tài chính (Thông tư 200/2014/TT-BTC).

Module này đóng vai trò phân tích cú pháp (parser) cấp ứng dụng (Application Layer),
chuyển đổi kết quả trích xuất văn bản OCR hoặc bảng biểu có cấu trúc thành mô hình thực thể
FinancialReport hoàn chỉnh, hỗ trợ nhận diện mẫu biểu BCTC, đơn vị tiền tệ, niên độ kế toán,
và thuật toán ánh xạ chỉ tiêu 3 cấp độ (Mã số -> Nhãn chuẩn -> Từ đồng nghĩa).
"""
from decimal import Decimal
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.domain.accounting.canonical import (
    BALANCE_SHEET_CANONICAL,
    INCOME_STATEMENT_CANONICAL,
    GENERIC_FINANCIAL_WORDS,
)
from src.domain.accounting.lexicon import FinancialLexiconCorrector
from src.domain.accounting.metadata_extractor import StatementMetadataExtractor
from src.domain.accounting.normalizer import AccountingNumberNormalizer, NumberStatus
from src.domain.models.bctc import (
    AccountingStandard,
    BalanceSheet,
    CashFlowStatement,
    FinancialReport,
    IncomeStatement,
)
from src.domain.models.line_item import (
    LineItem,
    MappingMethod,
    MappingStatus,
)
from src.domain.models.ocr import (
    DocumentExtractionResult,
    PageExtractionResult,
)

logger = logging.getLogger(__name__)


class FinancialStatementParser:
    """Bộ phân tích cú pháp chuyển đổi tài liệu OCR/bảng biểu thành FinancialReport chuẩn hóa.

    Attributes:
        decimal_convention (str): Quy ước dấu phân cách số ("auto", "vietnamese", "international").
    """

    def __init__(self, decimal_convention: str = "auto") -> None:
        """Khởi tạo bộ phân tích cú pháp báo cáo tài chính.

        Args:
            decimal_convention (str): Quy ước dấu thập phân và hàng nghìn.
                Mặc định là "auto" để thuật toán tự động nhận diện dựa trên mật độ dấu.
        """
        self.decimal_convention: str = decimal_convention

    def parse(
        self,
        document_input: Union[DocumentExtractionResult, str, List[PageExtractionResult]],
        source_name: Optional[str] = None,
    ) -> FinancialReport:
        """Phân tích kết quả trích xuất tài liệu thành mô hình FinancialReport hoàn chỉnh.

        Hàm thực hiện quy trình 3 giai đoạn:
        1. Nhận diện siêu dữ liệu tài liệu (tên công ty, đơn vị tiền tệ, niên độ, ngày lập).
        2. Duyệt qua từng trang tài liệu, xác định ngữ cảnh báo cáo (Bảng cân đối kế toán hoặc
           Kết quả kinh doanh), bóc tách bảng cấu trúc (pdfplumber) hoặc dòng văn bản OCR/HTML.
        3. Tổng hợp các chỉ tiêu đã ánh xạ, chuẩn hóa niên độ và đối chiếu thời điểm báo cáo.

        Args:
            document_input (Union[DocumentExtractionResult, str, List[PageExtractionResult]]):
                Dữ liệu đầu vào từ OCR hoặc trích xuất PDF dạng chuỗi ký tự, danh sách trang
                hoặc đối tượng DocumentExtractionResult.
            source_name (Optional[str]): Tên định danh tài liệu nguồn (ví dụ: tên tệp PDF).

        Returns:
            FinancialReport: Báo cáo tài chính chứa Bảng cân đối kế toán và Báo cáo kết quả kinh doanh.
        """
        doc_name: str = source_name or "Financial Document"
        # Danh sách các trang cần xử lý dưới dạng tuple (số trang, nội dung text, danh sách bảng)
        pages_to_process: List[Tuple[int, str, List[List[List[Optional[str]]]]]] = []

        if isinstance(document_input, DocumentExtractionResult):
            doc_name = document_input.source_name
            for p in document_input.pages:
                pages_to_process.append((p.page_number, p.text, p.tables))
        elif isinstance(document_input, str):
            # Kiểm tra nếu chuỗi văn bản chứa phân cách trang chuẩn dạng ===== PAGE \d+ =====
            if re.search(r"=====\s*PAGE\s+\d+\s*=====", document_input):
                splits = re.split(r"=====\s*PAGE\s+(\d+)\s*=====", document_input)
                # splits[0] là header trước Trang 1; các phần tử tiếp theo là cặp (p_num, p_text)
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

        # Bước 1: Trích xuất siêu dữ liệu toàn văn (đơn vị tính, năm tài chính, tên công ty, ngày tháng)
        full_text: str = "\n".join(text for _, text, _ in pages_to_process)
        detected_unit: str = self._detect_unit(full_text)
        company_name: Optional[str] = self._detect_company_name(full_text)
        detected_as_of_date, detected_year = self._detect_as_of_date(full_text)
        detected_period, is_year = self._detect_period_label(full_text)
        fiscal_year: Optional[int] = detected_year or is_year or self._detect_fiscal_year(full_text)

        balance_sheet.currency = detected_unit
        income_statement.currency = detected_unit

        # Bước 2: Duyệt từng trang và nhận diện ngữ cảnh báo cáo
        current_context: str = "unknown"

        for page_num, text, tables in pages_to_process:
            page_context = self._detect_statement_type(text)
            if page_context != "unknown":
                current_context = page_context

            # Nếu trang là Bảng cân đối kế toán, cập nhật ngày báo cáo và niên độ từ tiêu đề trang
            if current_context == "balance_sheet":
                page_date, page_year = self._detect_as_of_date(text)
                if page_date:
                    balance_sheet.as_of_date = page_date
                    detected_as_of_date = page_date
                if page_year:
                    fiscal_year = page_year
            elif current_context == "income_statement":
                page_period, page_is_year = self._detect_period_label(text)
                if page_period:
                    income_statement.period = page_period
                    detected_period = page_period
                if page_is_year and not fiscal_year:
                    fiscal_year = page_is_year

            # Phương pháp A: Xử lý bảng có cấu trúc nếu có sẵn (từ pdfplumber)
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

            # Phương pháp B: Xử lý dòng văn bản thuần hoặc các thẻ HTML <table> trong text
            self._parse_text_lines_or_html(
                text=text,
                page_num=page_num,
                context=current_context,
                unit=detected_unit,
                bs=balance_sheet,
                is_=income_statement,
            )

        # Bước 3: Hoàn thiện thông tin ngày báo cáo và niên độ tài chính
        final_as_of: Optional[str] = balance_sheet.as_of_date or detected_as_of_date
        final_period: Optional[str] = income_statement.period or detected_period
        if not fiscal_year:
            if final_as_of:
                m_y = re.search(r"\b((?:19|20)\d{2})\b", final_as_of)
                if m_y:
                    fiscal_year = int(m_y.group(1))
            elif final_period:
                m_y = re.search(r"\b((?:19|20)\d{2})\b", final_period)
                if m_y:
                    fiscal_year = int(m_y.group(1))

        if not balance_sheet.as_of_date and final_as_of:
            balance_sheet.as_of_date = final_as_of
        if not income_statement.period and final_period:
            income_statement.period = final_period

        return FinancialReport(
            company_name=company_name,
            fiscal_year=fiscal_year,
            as_of_date=final_as_of,
            period=final_period,
            unit=detected_unit,
            source_document=doc_name,
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )

    @staticmethod
    def _expand_cell_tokens(row_cells: List[str]) -> List[str]:
        """Tách các token trong ô khi nhiều cột hoặc số bị gộp chung vào một chuỗi ký tự.

        Args:
            row_cells (List[str]): Danh sách chuỗi các ô trong dòng.

        Returns:
            List[str]: Danh sách ô đã được tách rời hợp lệ.
        """
        expanded: List[str] = []
        for cell in row_cells:
            cell_str = cell.strip()
            if not cell_str:
                continue

            # Các chuỗi công thức diễn giải (ví dụ: '100 = 110 + 120 + ...') không được tách nhỏ
            if any(op in cell_str for op in ["=", "+"]):
                expanded.append(cell_str)
                continue

            parts = [p.strip() for p in cell_str.split(" ") if p.strip()]
            if len(parts) > 1:
                # Kiểm tra từng phần xem có phải số tiền, mã số la mã hoặc mã số chỉ tiêu không
                is_num_or_code = [
                    bool(
                        re.fullmatch(r"\(?[\d.,]+[A-Za-z]?\)?", p)
                        or re.fullmatch(r"[IVXLCDM]+\.\d+.*", p, re.I)
                        or re.fullmatch(r"\d{2,3}", p)
                    )
                    for p in parts
                ]
                # Chỉ tách nếu tất cả phần đều là số/mã, hoặc cụm 2-3 phần tử gồm mã số + số tiền
                if all(is_num_or_code) or (len(parts) <= 3 and is_num_or_code[0] and is_num_or_code[1]):
                    expanded.extend(parts)
                    continue
            expanded.append(cell_str)
        return expanded

    def _parse_text_lines_or_html(
        self,
        text: str,
        page_num: int,
        context: str,
        unit: str,
        bs: BalanceSheet,
        is_: IncomeStatement,
    ) -> None:
        """Phân tích các dòng văn bản thô hoặc các hàng HTML <table> nhúng trong text trang.

        Args:
            text (str): Toàn bộ văn bản trang.
            page_num (int): Số thứ tự trang hiện tại.
            context (str): Ngữ cảnh loại báo cáo ("balance_sheet", "income_statement", v.v.).
            unit (str): Đơn vị tiền tệ tính toán ("VND", "USD", v.v.).
            bs (BalanceSheet): Đối tượng Bảng cân đối kế toán đang ghi nhận.
            is_ (IncomeStatement): Đối tượng Báo cáo kết quả kinh doanh đang ghi nhận.
        """
        # 1. Kiểm tra cấu trúc hàng bảng HTML: <tr><td>...</td></tr>
        tr_matches = re.findall(r"<tr>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL)
        if tr_matches:
            for tr_content in tr_matches:
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr_content, flags=re.IGNORECASE | re.DOTALL)
                clean_tds = [re.sub(r"<[^>]+>", "", td).strip() for td in tds]
                if clean_tds:
                    expanded_tds = self._expand_cell_tokens(clean_tds)
                    # Nhận diện tiêu đề cột kỳ báo cáo nếu chưa xác định
                    if context == "balance_sheet" and not bs.current_period_name:
                        c_cur, c_prev = self._detect_column_headers(expanded_tds, context)
                        if c_cur:
                            bs.current_period_name = c_cur
                            bs.previous_period_name = c_prev
                            if not bs.as_of_date and re.fullmatch(r"\d{2}/\d{2}/\d{4}", c_cur):
                                bs.as_of_date = c_cur
                    elif context == "income_statement" and not is_.current_period_name:
                        c_cur, c_prev = self._detect_column_headers(expanded_tds, context)
                        if c_cur:
                            is_.current_period_name = c_cur
                            is_.previous_period_name = c_prev

                    self._process_row_tokens(expanded_tds, page_num, context, unit, bs, is_)
            return

        # 2. Xử lý các dòng văn bản phân cách bởi khoảng trắng hoặc tab
        lines = text.splitlines()
        pending_label: str = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue

            tokens = [t.strip() for t in re.split(r"\t+|\s{2,}", line) if t.strip()]
            if not tokens:
                continue

            expanded_tokens = self._expand_cell_tokens(tokens)

            # Kiểm tra dòng tiêu đề cột bảng (ví dụ: Mã số \t Thuyết minh \t 31/3/2026 \t 1/1/2026)
            if context == "balance_sheet" and not bs.current_period_name:
                c_cur, c_prev = self._detect_column_headers(expanded_tokens, context)
                if c_cur:
                    bs.current_period_name = c_cur
                    bs.previous_period_name = c_prev
                    if not bs.as_of_date and re.fullmatch(r"\d{2}/\d{2}/\d{4}", c_cur):
                        bs.as_of_date = c_cur
            elif context == "income_statement" and not is_.current_period_name:
                c_cur, c_prev = self._detect_column_headers(expanded_tokens, context)
                if c_cur:
                    is_.current_period_name = c_cur
                    is_.previous_period_name = c_prev

            # Kiểm tra dòng có chứa số liệu tài chính không
            has_numbers = False
            for tok in expanded_tokens[1:]:
                res = AccountingNumberNormalizer.parse(
                    tok, decimal_convention=self.decimal_convention, unit=unit
                )
                if res.is_valid and res.value is not None:
                    has_numbers = True
                    break

            if not has_numbers:
                # Dòng tên chỉ tiêu bị xuống dòng (ví dụ: "Dự phòng giảm giá chứng khoán...")
                if len(line) < 120 and not re.search(
                    r"BÁO CÁO|BẢNG CÂN ĐỐI|MẪU SỐ|NGÀY \d|ĐƠN VỊ TÍNH|Trang \d", line, re.I
                ):
                    pending_label = line
                else:
                    pending_label = ""
                continue

            # Nối nhãn bị ngắt từ dòng trước vào nhãn hiện tại
            if pending_label:
                l_idx = 0
                if len(expanded_tokens[0]) <= 3 and len(expanded_tokens) > 1 and len(expanded_tokens[1]) > 3:
                    l_idx = 1
                expanded_tokens[l_idx] = f"{pending_label} {expanded_tokens[l_idx]}".strip()
                pending_label = ""

            if len(expanded_tokens) >= 2:
                self._process_row_tokens(expanded_tokens, page_num, context, unit, bs, is_)

    def _parse_raw_table(
        self,
        table: List[List[Optional[str]]],
        page_num: int,
        context: str,
        unit: str,
        bs: BalanceSheet,
        is_: IncomeStatement,
    ) -> None:
        """Phân tích ma trận 2 chiều các ô bảng biểu do thư viện trích xuất (pdfplumber).

        Args:
            table (List[List[Optional[str]]]): Ma trận các dòng và cột trong bảng.
            page_num (int): Số trang chứa bảng.
            context (str): Ngữ cảnh báo cáo hiện tại.
            unit (str): Đơn vị tiền tệ.
            bs (BalanceSheet): Bảng cân đối kế toán đang ghi nhận.
            is_ (IncomeStatement): Báo cáo kết quả kinh doanh đang ghi nhận.
        """
        for row in table:
            if not row:
                continue
            clean_row = [str(cell).strip() if cell is not None else "" for cell in row]
            if any(clean_row):
                expanded_row = self._expand_cell_tokens(clean_row)
                # Kiểm tra tiêu đề cột thời kỳ nếu chưa xác định
                if context == "balance_sheet" and not bs.current_period_name:
                    c_cur, c_prev = self._detect_column_headers(expanded_row, context)
                    if c_cur:
                        bs.current_period_name = c_cur
                        bs.previous_period_name = c_prev
                        if not bs.as_of_date and re.fullmatch(r"\d{2}/\d{2}/\d{4}", c_cur):
                            bs.as_of_date = c_cur
                elif context == "income_statement" and not is_.current_period_name:
                    c_cur, c_prev = self._detect_column_headers(expanded_row, context)
                    if c_cur:
                        is_.current_period_name = c_cur
                        is_.previous_period_name = c_prev

                self._process_row_tokens(expanded_row, page_num, context, unit, bs, is_)

    def _process_row_tokens(
        self,
        row_cells: List[str],
        page_num: int,
        context: str,
        unit: str,
        bs: BalanceSheet,
        is_: IncomeStatement,
    ) -> None:
        """Phân tích các token của một dòng để nhận diện nhãn chỉ tiêu, mã số và giá trị số.

        Args:
            row_cells (List[str]): Các ô của dòng.
            page_num (int): Số thứ tự trang.
            context (str): Ngữ cảnh loại báo cáo.
            unit (str): Đơn vị tính tiền tệ.
            bs (BalanceSheet): Bảng cân đối kế toán.
            is_ (IncomeStatement): Báo cáo kết quả kinh doanh.
        """
        row_cells = self._expand_cell_tokens(row_cells)
        if not row_cells or len(row_cells) < 2:
            return

        # Không bóc tách chỉ tiêu từ phần Thuyết minh BCTC (Mẫu B 09 - DN)
        if context == "notes":
            return

        # Xác định cột chứa nhãn văn bản (thường là cột 0, hoặc cột 1 nếu cột 0 là số thứ tự)
        label_idx = 0
        if len(row_cells[0]) <= 3 and len(row_cells) > 1 and len(row_cells[1]) > 3:
            label_idx = 1

        raw_label = row_cells[label_idx]
        if not raw_label or raw_label.lower() in {"chỉ tiêu", "chi tieu", "tài sản", "nguồn vốn", "mã số"}:
            return

        # Tìm kiếm mã số chỉ tiêu (2-3 chữ số như 100, 110, 01, 10) và các giá trị số hợp lệ
        item_code: Optional[str] = None
        number_values: List[Decimal] = []

        for idx, cell in enumerate(row_cells):
            if idx == label_idx or (label_idx == 1 and idx == 0):
                continue
            cell_clean = cell.strip()
            if not cell_clean:
                continue

            # Kiểm tra ô là mã số chỉ tiêu độc lập (ví dụ: "100", "110", "01", "420a")
            if re.fullmatch(r"\d{2,3}[a-z]?", cell_clean, re.I) and item_code is None:
                item_code = cell_clean
                continue

            # Kiểm tra ô chứa mã số kèm theo ghi chú thuyết minh (ví dụ: "121 V.4(a)")
            code_prefix_match = re.fullmatch(r"(\d{2,3}[a-z]?)\s+([A-Za-z0-9_(). -]+)", cell_clean, re.I)
            if code_prefix_match and item_code is None:
                item_code = code_prefix_match.group(1)
                continue

            # Bỏ qua các ô không phải số (ví dụ: tham chiếu thuyết minh 'VI.1.', 'V.3.')
            norm_res = AccountingNumberNormalizer.parse(
                cell_clean, decimal_convention=self.decimal_convention, unit=unit
            )
            if norm_res.is_valid and norm_res.value is not None:
                number_values.append(norm_res.value)

        if not number_values:
            return

        # Nếu mã số chưa tách được, kiểm tra mã số dính ở cuối nhãn (ví dụ: công thức kèm mã)
        if item_code is None:
            trailing_match = re.search(r"\b(\d{2,3}[a-z]?)\b\s*$", raw_label, re.I)
            if trailing_match and ("=" in raw_label or any(op in raw_label for op in ["+", "-"])):
                item_code = trailing_match.group(1).strip()
                raw_label = raw_label[:trailing_match.start(1)].strip()

        # Loại bỏ các biểu thức công thức như (100 = 110 + 120...) hoặc {30 = 20 + ...} khỏi nhãn
        while re.search(r"\{[^{}]*\}|\([^()]*\)", raw_label):
            raw_label = re.sub(r"\{[^{}]*\}|\([^()]*\)", "", raw_label).strip()
        raw_label = re.sub(r"\(mang sang trang sau\)|\(mang t trang trưc\)", "", raw_label, flags=re.I).strip()

        # Sửa lỗi chính tả và chuẩn hóa nhãn bằng từ điển kế toán Việt Nam (Lexicon Corrector)
        corrected_label, is_corrected = FinancialLexiconCorrector.correct_label(
            raw_label=raw_label,
            item_code=item_code,
            context=context,
        )
        display_label = corrected_label if is_corrected else raw_label

        cur_val: Optional[Decimal] = number_values[0] if len(number_values) > 0 else None
        prev_val: Optional[Decimal] = number_values[1] if len(number_values) > 1 else None

        # Thực hiện ánh xạ ngữ nghĩa chỉ tiêu (Semantic Mapping)
        line_item = self.map_line_item(
            raw_label=display_label,
            item_code=item_code,
            cur_val=cur_val,
            prev_val=prev_val,
            unit=unit,
            source_page=page_num,
            context=context,
        )

        # Gán chỉ tiêu vào báo cáo tương ứng (ưu tiên giữ chỉ tiêu có độ tin cậy cao hơn)
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
        ocr_confidence: Optional[float] = None,
    ) -> LineItem:
        """Ánh xạ một dòng tài chính thành LineItem chuẩn mực bằng thuật toán ưu tiên 3 cấp.

        Thứ tự ưu tiên ánh xạ:
        1. Khớp chính xác Mã số chỉ tiêu TT200 (Code Exact Match) kèm kiểm tra mẫu phản diện.
        2. Khớp chính xác Nhãn chuẩn hóa (Normalized Label Match).
        3. Khớp Từ đồng nghĩa (Synonym Match) kết hợp lọc từ mơ hồ (Anti-patterns).
        Nếu không khớp mức nào, đánh dấu UNMAPPED để phục vụ kiểm tra thủ công.

        Args:
            raw_label (str): Tên nhãn chỉ tiêu trích xuất từ tài liệu.
            item_code (Optional[str]): Mã số chỉ tiêu (ví dụ: '100', '110', '01').
            cur_val (Optional[Any]): Giá trị số kỳ hiện tại (Decimal hoặc None).
            prev_val (Optional[Any]): Giá trị số kỳ trước (Decimal hoặc None).
            unit (str): Đơn vị tiền tệ.
            source_page (int): Trang chứa chỉ tiêu.
            context (str): Ngữ cảnh báo cáo ("balance_sheet", "income_statement", "unknown").
            ocr_confidence (Optional[float]): Độ tin cậy OCR nếu có.

        Returns:
            LineItem: Đối tượng chỉ tiêu tài chính đã chuẩn hóa kèm trạng thái và điểm tin cậy.
        """
        # Sửa lỗi chính tả mờ nhòe bằng từ điển kế toán
        corr_label, is_corr = FinancialLexiconCorrector.correct_label(
            raw_label=raw_label,
            item_code=item_code,
            context=context,
        )
        effective_label = corr_label if is_corr else raw_label
        cleaned_label = AccountingNumberNormalizer.clean_label(effective_label)
        unaccented_label = AccountingNumberNormalizer.strip_accents(cleaned_label)
        warnings: List[str] = []

        # Lựa chọn từ điển chuẩn dựa theo ngữ cảnh báo cáo
        canon_dict: Dict[str, Dict[str, Any]] = {}
        if context == "balance_sheet":
            canon_dict = BALANCE_SHEET_CANONICAL
        elif context == "income_statement":
            canon_dict = INCOME_STATEMENT_CANONICAL
        elif context == "notes":
            canon_dict = {}
        else:
            canon_dict = {**BALANCE_SHEET_CANONICAL, **INCOME_STATEMENT_CANONICAL}

        # Ưu tiên 1: Khớp chính xác Mã số chỉ tiêu (Exact Item Code Match)
        if item_code:
            clean_code = item_code.zfill(2)  # Chuẩn hóa ví dụ "1" -> "01"
            matching_keys: List[str] = []
            for c_key, c_meta in canon_dict.items():
                valid_codes = {c_meta["code"], c_meta["code"].zfill(2)}
                for ac in c_meta.get("alt_codes", []):
                    valid_codes.add(ac)
                    valid_codes.add(ac.zfill(2))
                if item_code in valid_codes or clean_code in valid_codes:
                    matching_keys.append(c_key)

            clean_candidates: List[str] = []
            conflict_candidates: List[str] = []

            for c_key in matching_keys:
                c_meta = canon_dict[c_key]
                antipatterns = c_meta.get("disambiguation_antipatterns", [])
                has_antipattern = any(
                    anti in unaccented_label or anti in cleaned_label for anti in antipatterns
                )
                if c_key == "total_assets" and ("khac" in unaccented_label or "khac" in cleaned_label):
                    has_antipattern = True
                if c_key == "financial_expenses" and ("doanh thu" in unaccented_label or "doanh thu" in cleaned_label):
                    has_antipattern = True
                if c_key == "financial_income" and ("chi phi" in unaccented_label or "chi phi" in cleaned_label):
                    has_antipattern = True

                if has_antipattern:
                    if not (c_key == "total_assets" and ("khac" in unaccented_label or "khac" in cleaned_label)):
                        conflict_candidates.append(c_key)
                else:
                    clean_candidates.append(c_key)

            if clean_candidates:
                c_key = clean_candidates[0]
                c_meta = canon_dict[c_key]
                std_lbl = c_meta.get("standard_label", effective_label)
                return LineItem(
                    raw_label=raw_label,
                    normalized_label=std_lbl,
                    canonical_key=c_key,
                    item_code=item_code,
                    current_period_value=cur_val,
                    previous_period_value=prev_val,
                    unit=unit,
                    source_page=source_page,
                    mapping_method=MappingMethod.CODE_EXACT,
                    mapping_status=MappingStatus.MAPPED,
                    confidence_score=0.98,
                    ocr_confidence=ocr_confidence,
                    mapping_confidence=0.98,
                    row_consistency=1.0,
                )

            if conflict_candidates and not clean_candidates:
                c_key = conflict_candidates[0]
                c_meta = canon_dict[c_key]
                return LineItem(
                    raw_label=raw_label,
                    normalized_label=effective_label,
                    canonical_key=c_key,
                    item_code=item_code,
                    current_period_value=cur_val,
                    previous_period_value=prev_val,
                    unit=unit,
                    source_page=source_page,
                    mapping_method=MappingMethod.CODE_EXACT,
                    mapping_status=MappingStatus.NEEDS_REVIEW,
                    confidence_score=0.40,
                    ocr_confidence=ocr_confidence,
                    mapping_confidence=0.50,
                    row_consistency=0.20,
                    warnings=[
                        f"Mâu thuẫn dòng: Mã số {item_code} ({c_meta['standard_label']}) xung đột với tên chỉ tiêu '{raw_label}'"
                    ],
                )

        # Ưu tiên 2: Khớp chính xác Tên nhãn chuẩn hóa (Exact Normalized Label Match)
        clean_code = item_code.zfill(2) if item_code else None
        for c_key, c_meta in canon_dict.items():
            valid_codes = {c_meta["code"], c_meta["code"].zfill(2)}
            for ac in c_meta.get("alt_codes", []):
                valid_codes.add(ac)
                valid_codes.add(ac.zfill(2))
            # Nếu có mã số và mã số khác biệt hoàn toàn với mã chuẩn của chỉ tiêu thì bỏ qua
            if item_code and item_code not in valid_codes and clean_code not in valid_codes:
                continue

            std_cleaned = AccountingNumberNormalizer.clean_label(c_meta["standard_label"])
            std_unaccented = AccountingNumberNormalizer.strip_accents(std_cleaned)
            if cleaned_label == std_cleaned or unaccented_label == std_unaccented:
                return LineItem(
                    raw_label=raw_label,
                    normalized_label=c_meta["standard_label"],
                    canonical_key=c_key,
                    item_code=item_code or c_meta["code"],
                    current_period_value=cur_val,
                    previous_period_value=prev_val,
                    unit=unit,
                    source_page=source_page,
                    mapping_method=MappingMethod.LABEL_EXACT,
                    mapping_status=MappingStatus.MAPPED,
                    confidence_score=0.95,
                    ocr_confidence=ocr_confidence,
                    mapping_confidence=0.95,
                    row_consistency=1.0 if item_code else 0.9,
                )

        # Ưu tiên 3: Khớp Từ đồng nghĩa kèm kiểm tra mẫu chống trùng lặp (Synonym Match)
        candidate_matches: List[Tuple[str, float]] = []

        for c_key, c_meta in canon_dict.items():
            valid_codes = {c_meta["code"], c_meta["code"].zfill(2)}
            for ac in c_meta.get("alt_codes", []):
                valid_codes.add(ac)
                valid_codes.add(ac.zfill(2))
            # Bỏ qua nếu mã số không khớp với mã của chỉ tiêu ứng viên
            if item_code and item_code not in valid_codes and clean_code not in valid_codes:
                continue

            # Kiểm tra mẫu chống trùng lặp (ví dụ: phân biệt ngắn hạn vs dài hạn, chi phí vs doanh thu)
            has_antipattern = any(
                anti in unaccented_label for anti in c_meta.get("disambiguation_antipatterns", [])
            )
            if c_key == "total_assets" and ("khac" in unaccented_label or "khac" in cleaned_label):
                has_antipattern = True
            if c_key == "financial_expenses" and ("doanh thu" in unaccented_label or "doanh thu" in cleaned_label):
                has_antipattern = True
            if c_key == "financial_income" and ("chi phi" in unaccented_label or "chi phi" in cleaned_label):
                has_antipattern = True
            if has_antipattern:
                continue

            for syn in c_meta["synonyms"]:
                syn_clean = AccountingNumberNormalizer.clean_label(syn)
                syn_unaccented = AccountingNumberNormalizer.strip_accents(syn_clean)
                if syn_clean == cleaned_label or syn_unaccented == unaccented_label:
                    candidate_matches.append((c_key, 0.90))
                    break

                # Không cho phép khớp với các từ tài chính chung chung như 'kinh doanh'
                if unaccented_label in GENERIC_FINANCIAL_WORDS or cleaned_label in GENERIC_FINANCIAL_WORDS:
                    continue

                if syn_unaccented in unaccented_label or syn_clean in cleaned_label:
                    candidate_matches.append((c_key, 0.85))
                    break
                elif unaccented_label in syn_unaccented and len(unaccented_label) >= 8:
                    # Yêu cầu trùng lặp ít nhất 70% số từ để ngăn chặn khớp từ con tùy tiện
                    syn_words = set(syn_unaccented.split())
                    lbl_words = set(unaccented_label.split())
                    if syn_words and (len(lbl_words & syn_words) / len(syn_words)) >= 0.70:
                        candidate_matches.append((c_key, 0.75))
                        break

        if len(candidate_matches) == 1:
            best_key, conf = candidate_matches[0]
            status = MappingStatus.MAPPED if conf >= 0.85 else MappingStatus.NEEDS_REVIEW
            final_code = item_code if item_code else None
            return LineItem(
                raw_label=raw_label,
                normalized_label=canon_dict[best_key].get("standard_label", effective_label),
                canonical_key=best_key,
                item_code=final_code,
                current_period_value=cur_val,
                previous_period_value=prev_val,
                unit=unit,
                source_page=source_page,
                mapping_method=MappingMethod.LABEL_SYNONYM,
                mapping_status=status,
                confidence_score=conf,
                ocr_confidence=ocr_confidence,
                mapping_confidence=conf,
                row_consistency=1.0 if item_code else 0.75,
                warnings=warnings,
            )
        elif len(candidate_matches) > 1:
            warnings.append(
                f"Multiple mapping candidates found ({[k for k, _ in candidate_matches]}); marked for review"
            )
            candidate_matches.sort(key=lambda x: x[1], reverse=True)
            top_key, top_conf = candidate_matches[0]
            final_code = item_code if item_code else None
            return LineItem(
                raw_label=raw_label,
                normalized_label=canon_dict[top_key].get("standard_label", effective_label),
                canonical_key=top_key,
                item_code=final_code,
                current_period_value=cur_val,
                previous_period_value=prev_val,
                unit=unit,
                source_page=source_page,
                mapping_method=MappingMethod.LABEL_SYNONYM,
                mapping_status=MappingStatus.NEEDS_REVIEW,
                confidence_score=top_conf * 0.8,
                ocr_confidence=ocr_confidence,
                mapping_confidence=top_conf,
                row_consistency=0.5,
                warnings=warnings,
            )

        # Trạng thái không thể ánh xạ (Unmapped)
        return LineItem(
            raw_label=raw_label,
            normalized_label=effective_label,
            canonical_key=None,
            item_code=item_code,
            current_period_value=cur_val,
            previous_period_value=prev_val,
            unit=unit,
            source_page=source_page,
            mapping_method=MappingMethod.UNMAPPED,
            mapping_status=MappingStatus.UNMAPPED,
            confidence_score=0.0,
            ocr_confidence=ocr_confidence,
            mapping_confidence=0.0,
            row_consistency=0.5 if item_code else 0.0,
            warnings=["No canonical financial key matched"],
        )

    # Các phương thức trích xuất siêu dữ liệu ủy quyền từ StatementMetadataExtractor
    @staticmethod
    def _detect_statement_type(text: str) -> str:
        """Nhận diện loại báo cáo tài chính của một trang văn bản.

        Args:
            text (str): Nội dung văn bản trang.

        Returns:
            str: "balance_sheet", "income_statement", "cash_flow", "notes", hoặc "unknown".
        """
        return StatementMetadataExtractor.detect_statement_type(text)

    @staticmethod
    def _detect_unit(text: str) -> str:
        """Nhận diện đơn vị tiền tệ báo cáo từ tiêu đề tài liệu.

        Args:
            text (str): Nội dung văn bản phần đầu tài liệu.

        Returns:
            str: Đơn vị tiền tệ (ví dụ: 'VND', 'triệu VND', 'nghìn USD').
        """
        return StatementMetadataExtractor.detect_unit(text)

    @staticmethod
    def _detect_as_of_date(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Bóc tách ngày lập báo cáo (DD/MM/YYYY) và niên độ tài chính.

        Args:
            text (str): Văn bản tiêu đề báo cáo.

        Returns:
            Tuple[Optional[str], Optional[int]]: (Chuỗi ngày định dạng DD/MM/YYYY, Năm tài chính).
        """
        return StatementMetadataExtractor.detect_as_of_date(text)

    @staticmethod
    def _detect_period_label(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Bóc tách nhãn thời kỳ báo cáo (ví dụ: 'Năm 2020', 'Quý 1/2026', '6 tháng 2024').

        Args:
            text (str): Văn bản tiêu đề báo cáo.

        Returns:
            Tuple[Optional[str], Optional[int]]: (Nhãn thời kỳ, Năm tài chính).
        """
        return StatementMetadataExtractor.detect_period_label(text)

    @staticmethod
    def _detect_column_headers(row_cells: List[str], context: str) -> Tuple[Optional[str], Optional[str]]:
        """Nhận diện tiêu đề cột kỳ hiện tại và kỳ trước từ một dòng bảng hoặc danh sách token.

        Args:
            row_cells (List[str]): Các ô trong dòng tiêu đề.
            context (str): Ngữ cảnh báo cáo ("balance_sheet" hoặc "income_statement").

        Returns:
            Tuple[Optional[str], Optional[str]]: (Tên cột kỳ hiện tại, Tên cột kỳ trước).
        """
        return StatementMetadataExtractor.detect_column_headers(row_cells, context)

    @classmethod
    def _detect_fiscal_year(cls, text: str) -> Optional[int]:
        """Nhận diện năm tài chính từ nội dung văn bản (ví dụ: 2020 hoặc 31/12/2020).

        Args:
            text (str): Nội dung văn bản.

        Returns:
            Optional[int]: Năm tài chính dạng số nguyên hoặc None nếu không tìm thấy.
        """
        return StatementMetadataExtractor.detect_fiscal_year(text)

    @staticmethod
    def _detect_company_name(text: str) -> Optional[str]:
        """Trích xuất tên công ty được kiểm toán, loại trừ các công ty kiểm toán độc lập.

        Args:
            text (str): Văn bản trang bìa hoặc tiêu đề báo cáo.

        Returns:
            Optional[str]: Tên công ty hoặc None nếu không nhận diện được.
        """
        return StatementMetadataExtractor.detect_company_name(text)
