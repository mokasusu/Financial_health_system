"""Semantic parser and line item mapping for Vietnamese financial statements (Circular 200)."""
from decimal import Decimal
import difflib
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
        "synonyms": ["tai san ngan han", "tsnh", "tai san luu dong", "a tai san ngan han", "tai sn ngn hn", "tai sn ngn han"],
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
        "synonyms": [
            "dau tu tai chinh ngan han",
            "dau tu ngan han",
            "cac khoan dau tu tai chinh ngan han",
        ],
        "disambiguation_antipatterns": ["dai han", "chung khoan", "du phong", "dao han"],
    },
    "trading_securities": {
        "code": "121",
        "standard_label": "Chứng khoán kinh doanh",
        "synonyms": [
            "chung khoan kinh doanh",
            "ckkd",
        ],
        "disambiguation_antipatterns": ["du phong", "dao han"],
    },
    "provision_trading_securities": {
        "code": "122",
        "standard_label": "Dự phòng giảm giá chứng khoán kinh doanh",
        "synonyms": [
            "du phong giam gia chung khoan kinh doanh",
            "du phong giam gia chung khoan",
            "du phong ckkd",
        ],
        "disambiguation_antipatterns": [],
    },
    "held_to_maturity_investments": {
        "code": "123",
        "standard_label": "Đầu tư nắm giữ đến ngày đáo hạn",
        "synonyms": [
            "dau tu nam giu den ngay dao han",
            "nam giu den ngay dao han",
        ],
        "disambiguation_antipatterns": ["kinh doanh", "chung khoan"],
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
        "synonyms": ["tai san dai han", "tsdh", "tai san co dinh va dau tu dai han", "b tai san dai han", "tai sn dai hn"],
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
        "alt_codes": ["280"],
        "standard_label": "Tổng cộng tài sản",
        "synonyms": [
            "tong cong tai san",
            "tong tai san",
            "tong cong tai san 270",
            "tong cong tai san 280",
            "tong tai san 280",
        ],
        "disambiguation_antipatterns": ["nguon von", "ngan han", "dai han khac", "dai hn khac", "khac"],
    },
    "liabilities": {
        "code": "300",
        "standard_label": "Nợ phải trả",
        "synonyms": ["no phai tra", "tong no phai tra", "c no phai tra", "n phi tra", "n phai tra"],
        "disambiguation_antipatterns": ["von chu so huu", "ngan han", "dai han"],
    },
    "current_liabilities": {
        "code": "310",
        "standard_label": "Nợ ngắn hạn",
        "synonyms": ["no ngan han", "n ngn hn", "n ngan han"],
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
        "synonyms": [
            "von chu so huu",
            "vcsh",
            "d von chu so huu",
            "von chu so hu",
            "vn ch s hu",
            "von chu",
        ],
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
            "doanh thu thun v ban hang va cung cp dch v",
        ],
        "disambiguation_antipatterns": ["chua giam tru"],
    },
    "cost_of_goods_sold": {
        "code": "11",
        "standard_label": "Giá vốn hàng bán",
        "synonyms": [
            "gia von hang ban",
            "gia von",
            "gia vn hang ban va dch v cung cp",
            "gia von hang ban va dich vu cung cap",
        ],
        "disambiguation_antipatterns": [],
    },
    "gross_profit": {
        "code": "20",
        "standard_label": "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
        "synonyms": [
            "loi nhuan gop ve ban hang va cung cap dich vu",
            "loi nhuan gop",
            "lai gop",
            "li nhun gp v ban hang va cung cp dch v",
        ],
        "disambiguation_antipatterns": ["thuan", "truoc thue", "sau thue"],
    },
    "financial_income": {
        "code": "21",
        "alt_codes": ["22"],
        "standard_label": "Doanh thu hoạt động tài chính",
        "synonyms": [
            "doanh thu hoat dong tai chinh",
            "doanh thu tai chinh",
            "doanh thu hot dng tai chinh",
        ],
        "disambiguation_antipatterns": ["chi phi"],
    },
    "financial_expenses": {
        "code": "22",
        "alt_codes": ["23"],
        "standard_label": "Chi phí tài chính",
        "synonyms": ["chi phi tai chinh"],
        "disambiguation_antipatterns": ["lai vay", "doanh thu", "di vay"],
    },
    "interest_expenses": {
        "code": "23",
        "alt_codes": ["24"],
        "standard_label": "Chi phí lãi vay",
        "synonyms": [
            "chi phi lai vay",
            "trong do chi phi lai vay",
            "lai vay",
            "trong do chi phi di vay",
            "chi phi di vay",
        ],
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
            "li nhun thun t hot dng kinh doanh",
            "li nhun thun tu hoat dong kinh doanh",
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
            "li nhun k toan trưc thu",
            "li nhun ke toan truoc thue",
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
            "li nhun sau thu tndn",
            "li nhun sau thu",
        ],
        "disambiguation_antipatterns": ["truoc thue", "gop"],
    },
}

GENERIC_FINANCIAL_WORDS = {
    "kinh doanh", "ngan han", "dai han", "khac", "chi phi",
    "doanh thu", "thu nhap", "loi nhuan", "tai san", "nguon von",
    "tien", "thue", "du phong", "dau tu", "phai thu", "phai tra"
}


class FinancialLexiconCorrector:
    """Fuzzy lexicon corrector for Vietnamese financial statement line items.

    Fixes dropped accents, OCR transcription errors, and missing tone marks
    to map raw text to canonical Vietnamese financial statement names (Circular 200 / VAS).
    """

    CODE_THRESHOLD = 0.58
    GLOBAL_THRESHOLD = 0.72

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
        """Fuzzy-correct raw OCR line item label against standard Vietnamese accounting terminology.

        Args:
            raw_label: Raw string line label extracted by OCR.
            item_code: Extracted line code (e.g. '100', '110', '01', '30') if detected.
            context: Document context ('balance_sheet', 'income_statement', or 'unknown').

        Returns:
            Tuple of (corrected_label, is_corrected_bool).
        """
        cls._ensure_initialized()
        cleaned_raw = AccountingNumberNormalizer.clean_label(raw_label)
        unaccented_raw = AccountingNumberNormalizer.strip_accents(cleaned_raw)

        if not unaccented_raw or len(unaccented_raw) < 3:
            return raw_label, False

        # Phase 1: Guided by item_code if present
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

        # Phase 2: Global Fuzzy Match
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
        """Alias for correct_label."""
        return cls.correct_label(raw_label, item_code, context)


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

        # Step 1: Detect Document metadata (unit, fiscal year, company name, dates)
        full_text = "\n".join(text for _, text, _ in pages_to_process)
        detected_unit = self._detect_unit(full_text)
        company_name = self._detect_company_name(full_text)
        detected_as_of_date, detected_year = self._detect_as_of_date(full_text)
        detected_period, is_year = self._detect_period_label(full_text)
        fiscal_year = detected_year or is_year or self._detect_fiscal_year(full_text)

        balance_sheet.currency = detected_unit
        income_statement.currency = detected_unit

        # Step 2: Process pages and detect statement context
        current_context = "unknown"

        for page_num, text, tables in pages_to_process:
            page_context = self._detect_statement_type(text)
            if page_context != "unknown":
                current_context = page_context

            # If page is balance_sheet, refine as_of_date and fiscal_year from page header
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

        final_as_of = balance_sheet.as_of_date or detected_as_of_date
        final_period = income_statement.period or detected_period
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
        """Expand row tokens where multiple columns or numbers were combined into one string.

        E.g.:
          - '21.354.863.600.460 23.260.088.671.767' -> ['21.354.863.600.460', '23.260.088.671.767']
          - '121 V.4(a)' -> ['121', 'V.4(a)']
          - '(849.021.293) (920.681.738)' -> ['(849.021.293)', '(920.681.738)']
        """
        expanded: List[str] = []
        for cell in row_cells:
            cell_str = cell.strip()
            if not cell_str:
                continue

            # Explanatory formula strings (e.g. '100 = 110 + 120 + ...') should not be broken up
            if any(op in cell_str for op in ["=", "+"]):
                expanded.append(cell_str)
                continue

            parts = [p.strip() for p in cell_str.split(" ") if p.strip()]
            if len(parts) > 1:
                is_num_or_code = [
                    bool(
                        re.fullmatch(r"\(?[\d.,]+[A-Za-z]?\)?", p)
                        or re.fullmatch(r"[IVXLCDM]+\.\d+.*", p, re.I)
                        or re.fullmatch(r"\d{2,3}", p)
                    )
                    for p in parts
                ]
                # Only split if all parts look like numbers/codes/notes or clean 2-element code+note/amount
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
        """Parse raw text lines and embedded HTML <table> rows."""
        # 1. Check for HTML table rows: <tr><td>...</td></tr>
        tr_matches = re.findall(r"<tr>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL)
        if tr_matches:
            for tr_content in tr_matches:
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr_content, flags=re.IGNORECASE | re.DOTALL)
                clean_tds = [re.sub(r"<[^>]+>", "", td).strip() for td in tds]
                if clean_tds:
                    expanded_tds = self._expand_cell_tokens(clean_tds)
                    # Check for table header column dates/periods if not yet recognized
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

        # 2. Plain text line processing
        lines = text.splitlines()
        pending_label = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue

            tokens = [t.strip() for t in re.split(r"\t+|\s{2,}", line) if t.strip()]
            if not tokens:
                continue

            expanded_tokens = self._expand_cell_tokens(tokens)

            # Check if this line is a table header row (e.g. Mã số \t Thuyết minh \t 31/3/2026 \t 1/1/2026)
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

            # Check if this line contains any numeric values
            has_numbers = False
            for tok in expanded_tokens[1:]:
                res = AccountingNumberNormalizer.parse(
                    tok, decimal_convention=self.decimal_convention, unit=unit
                )
                if res.is_valid and res.value is not None:
                    has_numbers = True
                    break

            if not has_numbers:
                # Incomplete label line (e.g. "Dự phòng giảm giá chứng khoán")
                if len(line) < 120 and not re.search(
                    r"BÁO CÁO|BẢNG CÂN ĐỐI|MẪU SỐ|NGÀY \d|ĐƠN VỊ TÍNH|Trang \d", line, re.I
                ):
                    pending_label = line
                else:
                    pending_label = ""
                continue

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
        """Parse a 2D matrix of cells extracted by pdfplumber."""
        for row in table:
            if not row:
                continue
            clean_row = [str(cell).strip() if cell is not None else "" for cell in row]
            if any(clean_row):
                expanded_row = self._expand_cell_tokens(clean_row)
                # Check for table header column dates/periods if not yet recognized
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
        """Analyze row tokens, identify label, item code, and numeric values."""
        row_cells = self._expand_cell_tokens(row_cells)
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

            # Check if cell is an item code e.g. "100", "110", "01", "420a"
            if re.fullmatch(r"\d{2,3}[a-z]?", cell_clean, re.I) and item_code is None:
                item_code = cell_clean
                continue

            # Check if cell starts with item code followed by note ref e.g. "121 V.4(a)"
            code_prefix_match = re.fullmatch(r"(\d{2,3}[a-z]?)\s+([A-Za-z0-9_(). -]+)", cell_clean, re.I)
            if code_prefix_match and item_code is None:
                item_code = code_prefix_match.group(1)
                continue

            # Filter out non-numeric cells (e.g. note references like 'VI.1.', 'V.3.')
            norm_res = AccountingNumberNormalizer.parse(
                cell_clean, decimal_convention=self.decimal_convention, unit=unit
            )
            if norm_res.is_valid and norm_res.value is not None:
                number_values.append(norm_res.value)

        if not number_values:
            return

        # If item_code was not in a separate cell, look for trailing code in raw_label (e.g. attached to formula)
        if item_code is None:
            trailing_match = re.search(r"\b(\d{2,3}[a-z]?)\b\s*$", raw_label, re.I)
            if trailing_match and ("=" in raw_label or any(op in raw_label for op in ["+", "-"])):
                item_code = trailing_match.group(1).strip()
                raw_label = raw_label[:trailing_match.start(1)].strip()

        # Clean formula patterns e.g. (100 = 110 + 120...) or {30 = 20 + ...} from raw_label
        while re.search(r"\{[^{}]*\}|\([^()]*\)", raw_label):
            raw_label = re.sub(r"\{[^{}]*\}|\([^()]*\)", "", raw_label).strip()
        raw_label = re.sub(r"\(mang sang trang sau\)|\(mang t trang trưc\)", "", raw_label, flags=re.I).strip()

        # Spell correction and normalization using Vietnamese Accounting Lexicon
        corrected_label, is_corrected = FinancialLexiconCorrector.correct_label(
            raw_label=raw_label,
            item_code=item_code,
            context=context,
        )
        display_label = corrected_label if is_corrected else raw_label

        cur_val = number_values[0] if len(number_values) > 0 else None
        prev_val = number_values[1] if len(number_values) > 1 else None

        # Perform Semantic Mapping
        line_item = self.map_line_item(
            raw_label=display_label,
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
        ocr_confidence: Optional[float] = None,
    ) -> LineItem:
        """Map a line item to a canonical key using prioritized rules and cross-checking."""
        # Fuzzy spelling correction if raw_label needs fixing
        corr_label, is_corr = FinancialLexiconCorrector.correct_label(
            raw_label=raw_label,
            item_code=item_code,
            context=context,
        )
        effective_label = corr_label if is_corr else raw_label
        cleaned_label = AccountingNumberNormalizer.clean_label(effective_label)
        unaccented_label = AccountingNumberNormalizer.strip_accents(cleaned_label)
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

        # Priority 2: Exact Normalized Label Match
        clean_code = item_code.zfill(2) if item_code else None
        for c_key, c_meta in canon_dict.items():
            valid_codes = {c_meta["code"], c_meta["code"].zfill(2)}
            for ac in c_meta.get("alt_codes", []):
                valid_codes.add(ac)
                valid_codes.add(ac.zfill(2))
            # If item_code is present and explicitly differs from canonical key code, skip!
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

        # Priority 3: Synonym Match with Disambiguation Anti-Patterns Check
        candidate_matches: List[Tuple[str, float]] = []

        for c_key, c_meta in canon_dict.items():
            valid_codes = {c_meta["code"], c_meta["code"].zfill(2)}
            for ac in c_meta.get("alt_codes", []):
                valid_codes.add(ac)
                valid_codes.add(ac.zfill(2))
            # If item_code is present and explicitly differs from canonical key code, skip!
            if item_code and item_code not in valid_codes and clean_code not in valid_codes:
                continue

            # Check anti-patterns first to avoid false positives (e.g. short-term vs long-term)
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

                # Disallow matching standalone generic financial keywords like 'kinh doanh'
                if unaccented_label in GENERIC_FINANCIAL_WORDS or cleaned_label in GENERIC_FINANCIAL_WORDS:
                    continue

                if syn_unaccented in unaccented_label or syn_clean in cleaned_label:
                    candidate_matches.append((c_key, 0.85))
                    break
                elif unaccented_label in syn_unaccented and len(unaccented_label) >= 8:
                    # Require at least 70% word overlap to prevent arbitrary sub-word matches
                    syn_words = set(syn_unaccented.split())
                    lbl_words = set(unaccented_label.split())
                    if syn_words and (len(lbl_words & syn_words) / len(syn_words)) >= 0.70:
                        candidate_matches.append((c_key, 0.75))
                        break

        if len(candidate_matches) == 1:
            best_key, conf = candidate_matches[0]
            status = MappingStatus.MAPPED if conf >= 0.85 else MappingStatus.NEEDS_REVIEW
            # Do NOT invent item_code if not verified from OCR or label exact
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

        # Unmapped
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

    @staticmethod
    def _detect_statement_type(text: str) -> str:
        """Detect which financial statement a page text belongs to."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        header_lines = lines[:20]
        header_text = "\n".join(header_lines)
        header_unaccented = AccountingNumberNormalizer.strip_accents(header_text).upper()

        # If it's a Table of Contents (Mục lục), do not misidentify as statement
        if "MUC LUC" in header_unaccented or "TABLE OF CONTENTS" in header_unaccented:
            return "unknown"

        # Exclude management/audit/directors reports from statement detection
        if any(k in header_unaccented for k in [
            "BAO CAO KIEM TOAN", "BAO CAO CUA BAN DIEU HANH", "BAN DIEU HANH", "BAN KIEM SOAT", "Y KIEN KIEM TOAN"
        ]):
            return "unknown"

        # Filter out statutory footer disclaimer from header text before checking Notes
        # e.g. 'Cac thuyet minh dinh kem la bo phan hop thanh...'
        filtered_unaccented = "\n".join([
            l for l in header_unaccented.splitlines()
            if not any(k in l for k in ["DINH KEM", "HOP THANH", "BO PHAN"])
        ])

        # Check Balance Sheet / Báo cáo tình hình tài chính / Bảng cân đối kế toán
        if (
            re.search(r"\bB\s*01[a-z]?\b", header_text, re.I)
            or "CAN DOI KE TOAN" in filtered_unaccented
            or "BAO CAO TINH HINH TAI CHINH" in filtered_unaccented
            or ("TINH HINH TAI CHINH" in filtered_unaccented and ("TAI NGAY" in filtered_unaccented or "MA SO" in filtered_unaccented))
        ):
            return "balance_sheet"

        # Check Income Statement / Kết quả kinh doanh
        if (
            re.search(r"\bB\s*02[a-z]?\b", header_text, re.I)
            or "KET QUA HOAT DONG KINH DOANH" in filtered_unaccented
            or "KET QUA KINH DOANH" in filtered_unaccented
            or ("KT QU" in filtered_unaccented and "KINH DOANH" in filtered_unaccented)
            or ("HOT DNG KINH DOANH" in filtered_unaccented and "BAO CAO" in filtered_unaccented)
        ):
            return "income_statement"

        # Check Cash Flow / Lưu chuyển tiền tệ
        if (
            re.search(r"\bB\s*03[a-z]?\b", header_text, re.I)
            or "LUU CHUYEN TIEN TE" in filtered_unaccented
            or "LUU CHUYN TIN T" in filtered_unaccented
            or "LUU CHUYEN TIEN" in filtered_unaccented
        ):
            return "cash_flow"

        # Check Notes / Thuyết minh (B 09 - DN)
        if (
            re.search(r"\bB\s*09[a-z]?\b", header_text, re.I)
            or "BAN THUYET MINH" in filtered_unaccented
            or "THUYET MINH BAO CAO TAI CHINH" in filtered_unaccented
        ):
            return "notes"

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
    def _detect_as_of_date(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract explicit reporting date (DD/MM/YYYY) and fiscal year from statement text."""
        text_clean = text.replace("\r", " ").replace("\n", " ")

        # 1. Tại ngày DD tháng MM năm YYYY
        m = re.search(r"(?:tại\s+ngày|ngày)\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 2. kết thúc (vào) ngày DD tháng MM năm YYYY
        m = re.search(r"kết\s+thúc\s+(?:vào\s+)?ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 3. Tại ngày / kết thúc ngày DD/MM/YYYY
        m = re.search(r"(?:tại\s+ngày|kết\s+thúc\s+ngày|ngày|tại)\s*[:\-]?\s*(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 4. As at / As of DD Month YYYY or DD/MM/YYYY
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

        m_asof = re.search(r"as\s+(?:at|of)\s*[:\-]?\s*(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if m_asof:
            d, mo, y = int(m_asof.group(1)), int(m_asof.group(2)), int(m_asof.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 5. Cho năm tài chính kết thúc ngày 31/12/YYYY
        m = re.search(r"(?:cho\s+năm\s+tài\s+chính|năm\s+tài\s+chính).*?(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                return f"{d:02d}/{mo:02d}/{y}", y

        # 6. Look for standard reporting date 31/12/YYYY or 30/06/YYYY or 31/03/YYYY
        m = re.search(r"\b(3[01]|0[1-9]|[12]\d)[/-](0[1-9]|1[0-2])[/-]((?:19|20)\d{2})\b", text_clean)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if f"{d:02d}/{mo:02d}/{y}" != "22/12/2014":
                return f"{d:02d}/{mo:02d}/{y}", y

        return None, None

    @staticmethod
    def _detect_period_label(text: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract period label e.g. 'Năm 2020', 'Quý 1/2026', '6 tháng 2024'."""
        text_clean = text.replace("\r", " ").replace("\n", " ")

        # 1. Quý X/YYYY
        m_q = re.search(r"quý\s*(\d|\b[IVXLCDM]+\b)[/-]?\s*(?:năm\s*)?((?:19|20)\d{2})", text_clean, re.I)
        if m_q:
            q_num = m_q.group(1)
            y = int(m_q.group(2))
            return f"Quý {q_num}/{y}", y

        # 2. 6 tháng đầu năm YYYY / Bán niên YYYY
        m_semi = re.search(r"(?:6\s+tháng\s+(?:đầu\s+năm\s+)?|bán\s+niên\s*)((?:19|20)\d{2})", text_clean, re.I)
        if m_semi:
            y = int(m_semi.group(1))
            return f"6 tháng {y}", y

        # 3. Cho năm tài chính kết thúc ngày DD/MM/YYYY
        m_end = re.search(r"kết\s+thúc\s+(?:vào\s+)?ngày\s+(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})", text_clean, re.I)
        if not m_end:
            m_end = re.search(r"kết\s+thúc\s+(?:vào\s+)?ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+((?:19|20)\d{2})", text_clean, re.I)
        if m_end:
            d, mo, y = int(m_end.group(1)), int(m_end.group(2)), int(m_end.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                if d == 31 and mo == 12:
                    return f"Năm {y}", y
                return f"Kỳ kết thúc {d:02d}/{mo:02d}/{y}", y

        # 4. Năm YYYY (specifically in header)
        m_yr = re.search(r"\bnăm\s+((?:19|20)\d{2})\b", text_clean, re.I)
        if m_yr:
            y = int(m_yr.group(1))
            if y != 2014:  # ignore circular 200 year
                return f"Năm {y}", y

        return None, None

    @staticmethod
    def _detect_column_headers(row_cells: List[str], context: str) -> Tuple[Optional[str], Optional[str]]:
        """Identify current and previous period column headers from a table row or token list."""
        row_text = " ".join(str(c).strip() for c in row_cells if c is not None)
        if not row_text.strip():
            return None, None

        l_row = row_text.lower()
        # Ignore obvious statement title lines unless it contains table columns like 'mã số'
        if any(t in l_row for t in ["báo cáo", "báo cáo tài chính", "bộ tài chính", "thông tư", "ban hành", "mẫu số", "mẫu b"]):
            if not ("mã số" in l_row and re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", row_text)):
                return None, None

        # 1. Search for explicit date pairs e.g. 31/12/2020 and 01/01/2020 or 31/3/2026 and 1/1/2026
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

        # 2. Search for explicit year tokens e.g. Năm 2020 / Năm 2019
        years = re.findall(r"\bnăm\s+((?:19|20)\d{2})\b", row_text, re.I)
        if len(years) >= 2:
            return f"Năm {years[0]}", f"Năm {years[1]}"
        elif len(years) == 1 and context == "income_statement":
            if any(k in l_row for k in ["chỉ tiêu", "mã số", "thuyết minh", "đơn vị tính"]):
                y = int(years[0])
                if y != 2014:
                    return f"Năm {y}", f"Năm {y - 1}"

        # 3. Search for Quý tokens e.g. Quý 1/2026 / Quý 1/2025
        q_matches = re.findall(r"quý\s*(\d|\b[IVXLCDM]+\b)[/-]?\s*(?:năm\s*)?((?:19|20)\d{2})", row_text, re.I)
        if len(q_matches) >= 2:
            return f"Quý {q_matches[0][0]}/{q_matches[0][1]}", f"Quý {q_matches[1][0]}/{q_matches[1][1]}"

        # 4. Standard Vietnamese period descriptors
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
    def _detect_fiscal_year(cls, text: str) -> Optional[int]:
        """Detect fiscal year from statements e.g. 2020 or 31/12/2020."""
        # 1. Try extracting from as_of_date
        _, y = cls._detect_as_of_date(text)
        if y:
            return y
        # 2. Try extracting from period label e.g. 'Năm 2020' or 'Quý 1/2026'
        _, y = cls._detect_period_label(text)
        if y:
            return y
        # 3. Fallback regex, ignoring statutory 2014 from TT200/2014
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
    def _detect_company_name(text: str) -> Optional[str]:
        """Extract target audited company name, skipping auditing firms."""
        matches = re.findall(r"(?:CÔNG TY|CONG TY)\s+[A-Z0-9À-Ỹ\s\.\-]+(?:\n|$)", text, re.IGNORECASE)
        for m in matches:
            clean = m.strip()
            if not any(k in clean.upper() for k in [
                "KIỂM TOÁN", "KIEM TOAN", "AUDIT", "TNHH KIỂM TOÁN",
                "KPMG", "PWC", "DELOITTE", "ERNST & YOUNG", "PRICEWATERHOUSECOOPERS",
                "GRANT THORNTON", "BDO", "A&C",
            ]):
                return clean
        return matches[0].strip() if matches else None
