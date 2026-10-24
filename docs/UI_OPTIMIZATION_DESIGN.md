# BẢN THIẾT KẾ KỸ THUẬT: TỐI ƯU HÓA GIAO DIỆN NGƯỜI DÙNG (UI OPTIMIZATION DESIGN)

## 1. TỔNG QUAN & MỤC TIÊU (OVERVIEW & OBJECTIVES)

### 1.1 Vấn đề hiện tại
Giao diện người dùng trước đây bị phân mảnh:
- Chia cắt thành 5 Tab chính lớn, bên trong chứa 7 Tab con, 14 `st.expander` và nhiều `st.popover` lồng nhau.
- Người xem phải chuyển qua lại nhiều tab và click liên tục để nắm bắt thông tin.
- Xuất hiện nhiều thông tin thừa gây nhiễu: Mã Rule kỹ thuật (`rule_cr_01`, `rule_dta_01`), mã lỗi code, cột điểm tin cậy OCR số học từng dòng (`0.95`, `1.00`), các hộp cảnh báo pháp lý choán diện tích.
- Tách riêng Tab 5 chỉ để chứa 3 nút bấm xuất file.

### 1.2 Mục tiêu thiết kế
- **Bao quát thông tin**: Nắm trọn bức tranh sức khỏe tài chính trong 1 màn hình đầu tiên (Executive Dashboard).
- **Không xé lẻ vụn vặt**: Tái cấu trúc thành **3 Tab điều hành tập trung**.
- **Loại bỏ thông tin thừa**: Giữ lại các chỉ số và nhận định có ý nghĩa kinh tế, ẩn toàn bộ mã kỹ thuật nội bộ.
- **Bảo toàn 100% nghiệp vụ**: Giữ nguyên tính toán 14 tỷ số `Decimal`, kiểm định TT200, AI Gateway & Fallback, xuất JSON/CSV.

---

## 2. NHẬT KÝ QUYẾT ĐỊNH THIẾT KẾ (DECISION LOG)

| Mã Quyết Định | Nội Dung Quyết Định | Phương Án Lựa Chọn | Các Phương Án Đã Xem Xét | Lý Do Lựa Chọn & Giá Trị |
| :---: | :--- | :--- | :--- | :--- |
| **DEC-01** | Bố cục tổng thể hệ thống | **Mô hình 3 Tab Điều Hành Tập Trung (Executive Triad)** | - 1 trang cuộn dài (Single-page)<br>- Menu điều hướng Sidebar | Cân bằng hoàn hảo giữa góc nhìn bao quát cho lãnh đạo và khả năng đối chiếu số liệu chi tiết cho chuyên viên mà không quá tải cuộn trang. |
| **DEC-02** | Xử lý các nút xuất dữ liệu | **Tích hợp thanh thao tác nhanh trên đầu Tab 1** | Giữ riêng 1 Tab Xuất báo cáo | Tiện lợi, có thể tải báo cáo ngay lập tức mà không cần chuyển sang tab khác. |
| **DEC-03** | Trình bày 14 tỷ số tài chính | **Ma trận phân tích 14 chỉ số tập trung (Single Matrix Table)** | 4 tab con + 14 expander lồng nhau | Quan sát toàn diện 14 chỉ số trên cùng 1 bảng; lọc nhanh theo trạng thái An toàn/Theo dõi/Cảnh báo chỉ với 1 click. |
| **DEC-04** | Làm sạch bảng BCTC thô | **Ẩn cột điểm tin cậy OCR; chỉ gắn cờ dòng `NEEDS_REVIEW`** | Hiển thị đầy đủ mọi cột điểm tin cậy | Giảm nhiễu thị giác, tập trung sự chú ý của người dùng vào các dòng nghi ngờ hoặc có sai sót. |
| **DEC-05** | Loại bỏ thông tin thừa | **Xóa bỏ Rule ID, mã code kỹ thuật; thu gọn disclaimer xuống footer** | Giữ nguyên các hộp cảnh báo lớn | Tối ưu không gian hiển thị thông tin nghiệp vụ cốt lõi. |

---

## 3. KIẾN TRÚC GIAO DIỆN CHI TIẾT (DETAILED UI ARCHITECTURE)

```mermaid
flowchart TD
    App[app.py: Streamlit Dashboard]
    App --> Header[Top Action Bar: Meta tags + Nút Tải JSON/CSV]
    App --> Tabs{3 Tab Điều Hành}

    subgraph Tab 1: Tổng Quan & Nhận Định Điều Hành
        Tabs --> T1[Tab 1]
        T1 --> KPI[4 Thẻ KPI: Thanh toán, Nợ/TS, NPM, ROE]
        T1 --> Banner[Biểu Ngữ Sức Khỏe Tổng Thể & Số Lượng Cảnh Báo]
        T1 --> AIBox[Executive Summary: Tóm tắt AI / Fallback]
        T1 --> ColGrid[Bảng 2 Cột: Điểm Mạnh Nổi Bật vs Rủi Ro Trọng Yếu]
        T1 --> Recs[Khuyến Nghị Hành Động Thiết Thực]
        T1 --> Warnings[Danh Sách Cảnh Báo Rủi Ro - Không có Rule ID]
    end

    subgraph Tab 2: Ma Trận 14 Chỉ Số Tài Chính
        Tabs --> T2[Tab 2]
        T2 --> Filter[Bộ Lọc Nhanh: Tất Cả | Cảnh Báo | Cần Theo Dõi | An Toàn]
        T2 --> Matrix[Bảng Ma Trận 14 Chỉ Số Phân 4 Nhóm:<br>Thanh Khoản, Cơ Cấu Vốn, Hiệu Quả, Sinh Lời]
    end

    subgraph Tab 3: Dữ Liệu BCTC & Kiểm Định TT200
        Tabs --> T3[Tab 3]
        T3 --> Switcher[Bộ Chọn: Bảng CĐKT B01 | Kết Quả KD B02 | Kiểm Định TT200]
        T3 --> StmtTable[Bảng Kế Toán Sạch: Chỉ Cảnh Báo Dòng Cần Rà Soát]
        T3 --> AuditCard[Thẩm Định 4 Đẳng Thức TT200: Đạt / Lệch kèm Độ Lệch VND]
    end
```

---

## 4. CHI TIẾT CÁC THÀNH PHẦN (COMPONENT SPECIFICATIONS)

### 4.1 Tab 1: Tổng Quan & Nhận Định Điều Hành
* **Top Action Bar**:
  - Tên doanh nghiệp & Năm tài chính.
  - 2 nút download: `[📥 Tải Báo Cáo JSON]` và `[📊 Tải 14 Tỷ Số CSV]`.
* **4 Executive KPI Cards**:
  - `current_ratio`: Hệ số thanh toán hiện hành (TSNH / Nợ ngắn hạn).
  - `debt_to_assets`: Hệ số nợ trên tổng tài sản (Nợ phải trả / Tổng tài sản).
  - `net_profit_margin`: Biên lợi nhuận ròng (LNST / Doanh thu thuần).
  - `roe`: Sinh lời trên VCSH (LNST / VCSH bình quân).
  - Huy hiệu màu tương ứng: Xanh (Adequate), Vàng (Watch), Đỏ (Alert).
* **Overall Health Banner**:
  - Đánh giá tổng hợp: An toàn / Có điểm cần lưu ý / Rủi ro cao.
  - Đếm số lượng cảnh báo theo mức độ: Nghiêm trọng, Cao, Trung bình, Thấp.
* **Executive AI Summary**:
  - Khối nhận định toàn diện có đường viền ngọc lục bảo.
  - Hiển thị nhãn nguồn gốc: `[🤖 AI INTERPRETATION (Gemma 4)]` hoặc `[⚙️ DETERMINISTIC FALLBACK]`.
* **2-Column Comparative Analysis**:
  - Cột 1: Điểm mạnh tài chính (tên điểm mạnh, căn cứ số liệu, ý nghĩa kinh tế).
  - Cột 2: Rủi ro trọng yếu (tên rủi ro, mức độ nghiêm trọng, căn cứ số liệu, tác động).
* **Khuyến nghị chiến lược**: Các đề xuất hành động thực tế.
* **Danh sách Cảnh báo Rủi ro**: Hiển thị rõ tiêu đề, căn cứ số liệu và khuyến nghị xử lý; ẩn hoàn toàn các trường kỹ thuật `code` và `rule_id`.

### 4.2 Tab 2: Ma Trận 14 Chỉ Số Tài Chính (Consolidated Ratio Matrix)
* **Bộ lọc nhanh (Filter Control)**:
  - Cho phép người dùng lọc tức thời các dòng theo trạng thái (`Tất cả`, `Cảnh báo`, `Cần theo dõi`, `An toàn`).
* **Bảng Ma Trận Tổng Hợp**:
  - Phân chia thành 4 nhóm rõ rệt:
    1. *Khả năng thanh toán*: `current_ratio`, `quick_ratio`, `cash_ratio`.
    2. *Cơ cấu vốn & Đòn bẩy*: `debt_to_assets`, `debt_to_equity`, `equity_ratio`.
    3. *Hiệu quả hoạt động*: `total_asset_turnover`, `inventory_turnover`, `receivables_turnover`, `days_sales_outstanding`.
    4. *Khả năng sinh lời*: `gross_profit_margin`, `operating_profit_margin`, `net_profit_margin`, `roe`.
  - Cột dữ liệu:
    - `Nhóm`: Tên nhóm tài chính.
    - `Chỉ số`: Tên tiếng Việt và công thức vắn tắt.
    - `Giá trị`: Định dạng chuẩn (`2.45 lần`, `15.30%`, `45 ngày`).
    - `Trạng thái`: Huy hiệu màu sắc rõ nét.
    - `Ngưỡng an toàn`: Giá trị mốc tham chiếu.
    - `Ý nghĩa & Đánh giá`: Câu diễn giải kinh tế trực tiếp.
* Loại bỏ toàn bộ `st.expander` và `st.popover` đơn lẻ.

### 4.3 Tab 3: Dữ Liệu BCTC & Kiểm Định TT200
* **Bộ chuyển đổi biểu mẫu**:
  - Radio ngang hoặc pills chọn nhanh giữa B01-DN, B02-DN và Bảng kiểm định TT200.
* **Bảng Kế toán B01-DN & B02-DN**:
  - Các cột: `Mã số TT200` | `Chỉ tiêu kế toán` | `Kỳ này` | `Kỳ trước`.
  - Không hiển thị cột điểm tin cậy số học (`0.95`, `1.00`).
  - Dòng có trạng thái `NEEDS_REVIEW` được hiển thị biểu tượng cảnh báo `⚠️` màu hổ phách.
* **Kiểm định Cân đối Kế toán TT200**:
  - Biểu ngữ tổng kết: Số phép kiểm tra đạt / tổng số phép kiểm tra.
  - Bảng thẩm định 4 phương trình kế toán với biểu tượng trạng thái trực quan: `✅ ĐẠT` hoặc `❌ LỆCH`, kèm số tiền chênh lệch (VND) và dung sai cho phép.

---

## 5. KẾ HOẠCH TRIỂN KHAI (IMPLEMENTATION ROADMAP)

1. **Giai đoạn 1**: Cập nhật `src/ui/styles.py` để bổ sung các lớp CSS cho bộ lọc ma trận, nút xuất nhanh top action bar và bảng ma trận chỉ số.
2. **Giai đoạn 2**: Cập nhật `src/ui/components.py`:
   - Tinh gọn `render_header` và tích hợp `render_export_quick_actions`.
   - Viết mới `render_ratio_matrix` thay thế cho `render_ratio_analysis` cũ.
   - Làm sạch `render_financial_statements` (bỏ cột điểm tin cậy, làm nổi bật `NEEDS_REVIEW`).
   - Cập nhật `render_health_assessment` và `render_ai_interpretation` thành khối tổng quan thống nhất.
3. **Giai đoạn 3**: Cập nhật `app.py` để tích hợp cấu trúc 3 Tab mới.
4. **Giai đoạn 4**: Chạy kiểm thử tự động `pytest tests/` xác minh không gây hồi quy (regression) và kiểm tra giao diện thực tế.
