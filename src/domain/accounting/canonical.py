"""Từ điển danh mục chuẩn hóa chỉ tiêu Báo cáo tài chính theo Thông tư 200/2014/TT-BTC.

Module này cung cấp:
- BALANCE_SHEET_CANONICAL: Bảng ánh xạ mã số (100, 110, 200, 300, 400...), tên chuẩn,
  từ đồng nghĩa tiếng Việt (không dấu và có dấu) và từ phản mẫu (disambiguation_antipatterns)
  cho Bảng Cân Đối Kế Toán (Mẫu B01-DN).
- INCOME_STATEMENT_CANONICAL: Bảng ánh xạ cho Báo Cáo Kết Quả Hoạt Động Kinh Doanh (Mẫu B02-DN)
  (Mã số 01, 02, 10, 11, 20, 21, 22, 23, 25, 26, 30, 50, 51, 60...).
- GENERIC_FINANCIAL_WORDS: Tập hợp các từ vựng kế toán chung để tính toán điểm tương đồng.
"""
from typing import Any, Dict

# Từ điển chuẩn hóa Bảng Cân Đối Kế Toán (Mẫu B01-DN)
BALANCE_SHEET_CANONICAL: Dict[str, Dict[str, Any]] = {
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

INCOME_STATEMENT_CANONICAL: Dict[str, Dict[str, Any]] = {
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
