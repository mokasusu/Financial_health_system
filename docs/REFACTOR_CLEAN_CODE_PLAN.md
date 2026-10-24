# Kế Hoạch Refactor & Dọn Dẹp Mã Nguồn (Clean Architecture & Minimal Runtime)

## 1. Tóm Tắt Mục Tiêu & Nhận Thức (Understanding Summary)
* **Mục tiêu**: Refactor toàn diện dự án **Financial Health System**, chỉ giữ lại những thành phần thực sự cần thiết để vận hành hệ thống, loại bỏ toàn bộ mã nguồn chết (dead code), imports thừa, thư viện dư thừa, và tệp/thư mục rác.
* **Đối tượng sử dụng**: Nhà phát triển duy trì hệ thống và người dùng cuối vận hành Dashboard Streamlit.
* **Ràng buộc cốt lõi**:
  * 184/184 unit test tiếp tục **PASS 100%**.
  * Ứng dụng Streamlit Dashboard khởi chạy ổn định, không lỗi import hay cú pháp.
  * Đảm bảo nguyên lý **Zero File Retention** (xử lý bộ nhớ in-memory hoàn toàn) và số học chính xác `Decimal`.
* **Những việc không làm**: Không sửa đổi công thức 14 chỉ số tài chính, logic cân đối kế toán TT200, prompt AI hoặc bổ sung tính năng mới.

---

## 2. Các Giả Định Kỹ Thuật (Assumptions)
1. Thư mục `data/samples/` (`conghuy_A32_2020_sample.txt`, `vduydong_A32_2017_sample.txt`, `code_stock.csv`) phục vụ tính năng nạp BCTC mẫu trên giao diện người dùng nên được giữ nguyên.
2. Thư mục `docs/` chứa tài liệu thiết kế kiến trúc các sprint trước được giữ lại làm tài liệu tham khảo cho dự án.
3. Toàn bộ `scripts/` (benchmark OCR, đánh giá AI Sprint 5) và `notebooks/` (khảo sát ban đầu) là tài nguyên thử nghiệm thời điểm phát triển, không tham gia vào luồng runtime của ứng dụng.

---

## 3. Nhật Ký Quyết Định (Decision Log)

| Quyết định | Các phương án đã cân nhắc | Lý do chọn |
| :--- | :--- | :--- |
| **Phạm vi giữ lại** | 1. Giữ scripts/notebooks nghiên cứu<br>2. Chỉ giữ code chạy hệ thống | **Chỉ giữ code chạy hệ thống**: Đảm bảo codebase tinh khiết, loại bỏ nợ kỹ thuật và gánh nặng bảo trì. |
| **Phương thức thực hiện** | Phương án 1 (3 giai đoạn) vs. Phương án 2 (Một lượt) vs. Phương án 3 (Xóa cả Docs) | **Phương án 1 (3 giai đoạn)**: Cô lập từng nhóm thay đổi, kiểm thử chốt chặn sau mỗi bước để bảo đảm an toàn tuyệt đối. |
| **Phụ thuộc requirements.txt** | 1. Giữ nguyên<br>2. Lược bỏ 5 gói không dùng | **Lược bỏ 5 gói không dùng** (`huggingface_hub`, `openpyxl`, `tabulate`, `ipykernel`, `notebook`) giúp môi trường nhẹ và sạch hơn. |
| **Xử lý `render_kpi_cards`** | 1. Giữ lại làm alias<br>2. Xóa bỏ hoàn toàn | **Xóa bỏ hoàn toàn**: Đã có `render_core_4_kpi_cards` thay thế, hàm cũ không còn bất kỳ lời gọi nào. |
| **Chốt chặn chất lượng** | 1. Chạy lướt app<br>2. Kiểm thử 184 unit tests 100% pass | **184 Unit tests pass 100%**: Cam kết không có bất kỳ hồi quy logic nào sau refactor. |

---

## 4. Thiết Kế & Kế Hoạch Thực Hiện Chi Tiết (Final Design & Implementation Plan)

### Giai đoạn 1: Dọn dẹp Tệp Ngoại Vi & Thư Mục Rác
1. **Xóa tệp PDF ở thư mục gốc**:
   - `BCTC_VNM_tr4_16.pdf`
2. **Xóa thư mục thử nghiệm & nghiên cứu**:
   - `scripts/benchmark_ocr.py` và `scripts/evaluate_sprint5_ai.py` -> Xóa toàn bộ thư mục `scripts/`.
   - `notebooks/01_data_exploration.ipynb` -> Xóa toàn bộ thư mục `notebooks/`.
3. **Dọn dẹp thư mục rỗng**:
   - Xóa `data/benchmark/`, `data/interim/`, `data/raw/`, `data/processed/`.
   - Xóa `tests/integration/` (chỉ chứa file rỗng).
4. **Cập nhật tiện ích hệ thống**:
   - Trong `src/utils/__init__.py`: Xóa bỏ dòng khai báo `NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"`.

### Giai đoạn 2: Tinh Giản Thư Viện & Xóa Dead Code
1. **Tinh giản `requirements.txt`**:
   - Lược bỏ: `huggingface_hub`, `openpyxl`, `tabulate`, `ipykernel`, `notebook`.
2. **Làm sạch `app.py`**:
   - Xóa imports không dùng: `render_kpi_cards`, `render_ratio_matrix`, `render_top_action_bar`.
   - Xóa dòng lệnh thừa: `st.set_page_state = getattr(st, "set_page_state", None)`.
   - Chuẩn hóa hàm `get_available_sample_options()`: Xóa các đường dẫn mẫu `tests/fixtures/samples/...` không tồn tại, chỉ giữ `data/samples/...`.
3. **Làm sạch `src/ui/components.py`**:
   - Xóa định nghĩa hàm cũ `render_kpi_cards()`.
   - Chuẩn hóa định danh hàm render ma trận tỷ số, loại bỏ import trùng.

### Giai đoạn 3: Kiểm Định Chốt Chặn (Verification Gate)
1. **Chạy toàn bộ unit tests**:
   - Thực thi `.\.venv\Scripts\python.exe -m pytest tests/unit/`.
   - Xác nhận 184/184 tests pass 100%.
2. **Khởi chạy và xác thực ứng dụng Streamlit**:
   - Xác thực `app.py` khởi chạy không lỗi.
   - Thử nghiệm tính năng nạp BCTC mẫu, hiển thị 4 KPI cards, ma trận 14 chỉ số, bảng cân đối kế toán TT200 và xuất dữ liệu JSON/CSV.
