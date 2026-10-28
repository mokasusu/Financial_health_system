"""Unit tests verifying full financial statement extraction for Vinamilk Form B 01a / B 02a."""
from decimal import Decimal
import pytest
from src.application.services.parsing_service import FinancialStatementParser
from src.domain.ratios.engine import FinancialRatioCalculator


@pytest.fixture
def parser():
    return FinancialStatementParser()


@pytest.fixture
def calculator():
    return FinancialRatioCalculator()


def test_vinamilk_statement_page_detection(parser):
    """Verify statement context detection on Form B 01a, B 02a, and B 03a."""
    b01_header = (
        "Công ty C phần Sữa Việt Nam và các công ty con\n"
        "Báo cáo tình hình tài chính hợp nhất tại ngày 31 tháng 3 năm 2026\n"
        "Mẫu B 01a  DN/HN\n"
        "(Ban hành theo Thông tư số 43/2026/TT-BTC ngày 20/4/2026 của Bộ Tài chính)"
    )
    b02_header = (
        "Công ty C phần Sữa Việt Nam và các công ty con\n"
        "Báo cáo kết quả hoạt động kinh doanh hợp nhất\n"
        "Mẫu B 02a  DN/HN\n"
        "(Ban hành theo Thông tư số 43/2026/TT-BTC ngày 20/4/2026 của Bộ Tài chính)"
    )
    b03_header = (
        "Công ty C phần Sữa Việt Nam và các công ty con\n"
        "Báo cáo lưu chuyển tiền tệ hợp nhất\n"
        "Mẫu B 03a  DN/HN\n"
        "(Ban hành theo Thông tư số 43/2026/TT-BTC ngày 20/4/2026 của Bộ Tài chính)"
    )

    assert parser._detect_statement_type(b01_header) == "balance_sheet"
    assert parser._detect_statement_type(b02_header) == "income_statement"
    assert parser._detect_statement_type(b03_header) == "cash_flow"


def test_vinamilk_balance_sheet_and_income_statement_full_extraction(parser, calculator):
    """Verify complete financial items extraction and ratio calculation on Vinamilk data."""
    sample_text = """
===== PAGE 4 =====
Công ty C phần Sữa Việt Nam và các công ty con
Báo cáo tình hình tài chính hợp nhất tại ngày 31 tháng 3 năm 2026
Mẫu B 01a  DN/HN
Mã số\tThuyết minh\t31/3/2026\t1/1/2026
Tài sản ngắn hạn (100 = 110 + 120 + 130 + 140 + 150 + 160) 100\t38.757.016.956.726\t36.249.794.729.810
Tiền và các khoản tương đương tiền\t110\tV.1\t2.077.596.293.461\t1.794.879.718.871
Các khoản đầu tư tài chính ngắn hạn\t120\t23.002.417.266.337\t21.891.390.273.656
Các khoản phải thu ngắn hạn\t130\t5.591.443.574.678\t5.489.574.577.332
Hàng tồn kho\t140\tV.5\t7.399.150.703.886\t6.529.979.921.580

===== PAGE 5 =====
Công ty C phần Sữa Việt Nam và các công ty con
Báo cáo tình hình tài chính hợp nhất tại ngày 31 tháng 3 năm 2026 (tiếp theo)
Mẫu B 01a  DN/HN
Tài sản dài hạn (200 = 210 + 220 + 230 + 240 + 250 + 260 + 270) 200\t16.671.994.170.443\t17.062.575.987.491
Tài sản cố định\t220\t11.345.204.839.583\t11.573.477.183.374

===== PAGE 6 =====
Công ty C phần Sữa Việt Nam và các công ty con
Báo cáo tình hình tài chính hợp nhất tại ngày 31 tháng 3 năm 2026 (tiếp theo)
Mẫu B 01a  DN/HN
Tài sản dài hạn khác\t270\t2.003.654.299.617\t2.049.361.473.261
TỔNG TÀI SẢN (280 = 100 + 200)\t280\t55.429.011.127.169\t53.312.370.717.301

===== PAGE 7 =====
Công ty C phần Sữa Việt Nam và các công ty con
Báo cáo tình hình tài chính hợp nhất tại ngày 31 tháng 3 năm 2026 (tiếp theo)
Mẫu B 01a  DN/HN
NỢ PHẢI TRẢ (300 = 310 + 330)\t300\t18.740.931.850.130\t18.829.355.431.194
Nợ ngắn hạn\t310\t18.456.942.372.620\t18.520.286.019.795
Nợ dài hạn\t330\t283.989.477.510\t309.069.411.399
VỐN CHỦ SỞ HỮU\t400\tV.21\t36.688.079.277.039\t34.483.015.286,107
TỔNG CỘNG NGUỒN VỐN (440 = 300 + 400)\t440\t|55.429.011.127.169\t53.312.370.717.301

===== PAGE 8 =====
Công ty C phần Sữa Việt Nam và các công ty con
Báo cáo kết quả hoạt động kinh doanh hợp nhất
Mẫu B 02a  DN/HN
Doanh thu bán hàng và cung cấp dịch vụ\t01\tVI.1\t16.177.992.148.783\t12.988.447.508.846
Các khoản giảm trừ doanh thu\t02\tVI.1\t29.334.277.160\t30.899.523.580
Doanh thu thuần về bán hàng và cung cấp dịch vụ\t10\tVI.1\t16.148.657.871.623\t12.957.547.985.266
Giá vốn hàng bán và dịch vụ cung cấp\t11\tVI.2\t9.252.731.827.546\t7.763.216.215.319
Lợi nhuận gộp về bán hàng và cung cấp dịch vụ\t20\t6.895.926.044.077\t5.194.331.769.947
Doanh thu hoạt động tài chính\t22\tVI.3\t386.473.829.446\t366.337.215.645
Chi phí tài chính\t23\tVI.4\t154.556.282.718\t41.765.368.480
Trong đó: Chi phí đi vay\t24\t118.301.437.284\t75.155.207.673
Chi phí bán hàng\t25\tVI.5\t3.724.703.172.095\t3.169.757.183.300
Chi phí quản lý doanh nghiệp\t26\tVI.6\t459.769.658.861\t430.929.441.463
Lợi nhuận thuần từ hoạt động kinh doanh {30 = 20 + (22 - 23) - (25 + 26) + 27} 30\t2.991.830.566.118\t1.934.406.046.749
Lợi nhuận kế toán trước thuế (50 = 30 + 40)\t50\t3.014.396.468.576\t1.951.296.195.523
Chi phí thuế TNDN hiện hành\t51\tVI.10\t508.834.009.350\t326.819.068.821
Lợi nhuận sau thuế TNDN (60 = 50 - 51 - 52) (mang sang trang sau) 60\t2.458.221.002.532\t1.587.273.268.054
"""

    report = parser.parse(sample_text, source_name="BCTC_VNM_tr4_16.pdf")

    # Assert Balance Sheet items mapped accurately
    assert report.balance_sheet.items["current_assets"].current_period_value == Decimal("38757016956726")
    assert report.balance_sheet.items["total_assets"].current_period_value == Decimal("55429011127169")
    assert report.balance_sheet.items["total_assets"].item_code == "280"
    assert report.balance_sheet.items["liabilities"].current_period_value == Decimal("18740931850130")
    assert report.balance_sheet.items["current_liabilities"].current_period_value == Decimal("18456942372620")
    assert report.balance_sheet.items["equity"].current_period_value == Decimal("36688079277039")
    assert report.balance_sheet.items["equity"].previous_period_value == Decimal("34483015286107")
    assert report.balance_sheet.items["total_equity_and_liabilities"].current_period_value == Decimal("55429011127169")

    # Assert Income Statement items mapped accurately
    assert report.income_statement.items["gross_revenue"].current_period_value == Decimal("16177992148783")
    assert report.income_statement.items["net_revenue"].current_period_value == Decimal("16148657871623")
    assert report.income_statement.items["cost_of_goods_sold"].current_period_value == Decimal("9252731827546")
    assert report.income_statement.items["gross_profit"].current_period_value == Decimal("6895926044077")
    assert report.income_statement.items["financial_income"].current_period_value == Decimal("386473829446")
    assert report.income_statement.items["financial_expenses"].current_period_value == Decimal("154556282718")
    assert report.income_statement.items["interest_expenses"].current_period_value == Decimal("118301437284")
    assert report.income_statement.items["operating_profit"].current_period_value == Decimal("2991830566118")
    assert report.income_statement.items["net_profit_before_tax"].current_period_value == Decimal("3014396468576")
    assert report.income_statement.items["net_profit_after_tax"].current_period_value == Decimal("2458221002532")

    # Calculate and verify 4 Core KPIs
    ratios = calculator.calculate_all(report)
    cr = ratios.ratios["current_ratio"]
    de = ratios.ratios["debt_to_equity"]
    roa = ratios.ratios["roa"]
    roe = ratios.ratios["roe"]

    assert cr.value is not None
    assert round(float(cr.value), 2) == 2.10

    assert de.value is not None
    assert round(float(de.value), 2) == 0.51

    assert roa.value is not None
    assert round(float(roa.value), 4) == 0.0452

    assert roe.value is not None
    assert round(float(roe.value), 4) == 0.0691
