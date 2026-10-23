# Hệ Thống Tự Động Trích Xuất Dữ Liệu Báo Cáo Tài Chính & Đánh Giá Sức Khỏe Doanh Nghiệp Việt Nam

Dự án nghiên cứu và phát triển giải pháp ứng dụng Trí tuệ Nhân tạo (AI) và Khoa học Dữ liệu trong lĩnh vực Công nghệ Tài chính (FinTech), nhằm tự động hóa quy trình:
1. **Trích xuất dữ liệu Báo cáo tài chính (BCTC)**: Xử lý tài liệu dạng quét (scanned PDF/ảnh) và định dạng bảng biểu phức tạp của các doanh nghiệp niêm yết tại Việt Nam.
2. **Chuẩn hóa & Kiểm định dữ liệu**: Chuyển đổi dữ liệu thô sang lược đồ tài chính chuẩn mực kế toán Việt Nam (VAS / Thông tư 200).
3. **Đánh giá sức khỏe tài chính doanh nghiệp**: Tính toán các chỉ số thanh khoản, đòn bẩy, hiệu quả hoạt động, mô hình dự báo rủi ro kiệt quệ tài chính (Altman Z''-Score cho thị trường mới nổi) và kiểm định gian lận báo cáo (Beneish M-Score).

---

## 1. Cấu Trúc Thư Mục Dự Án

```text
Financial_health_system/
│
├── data/                       # Quản lý dữ liệu phân tầng
│   ├── raw/                    # Dữ liệu thô nguyên bản (không commit git)
│   ├── interim/                # Dữ liệu trung gian sau tiền xử lý sơ bộ
│   ├── processed/              # Dữ liệu cấu trúc sạch sẵn sàng phân tích
│   └── samples/                # Các mẫu dữ liệu nhỏ (1-5 file) phục vụ test & dev
│
├── notebooks/                  # Jupyter Notebooks phục vụ EDA và thử nghiệm
│   └── 01_data_exploration.ipynb # Notebook khảo sát metadata & cấu trúc dataset
│
├── src/                        # Mã nguồn ứng dụng (Module hóa theo Clean Architecture)
│   ├── __init__.py
│   ├── data/                   # Tải, streaming, parse và tiền xử lý dữ liệu
│   ├── ocr/                    # Nhận diện văn bản, cấu trúc bảng (Table Extraction)
│   ├── financial/              # Chỉ số tài chính, mô hình rủi ro (Z-score, M-score)
│   └── utils/                  # Tiện ích chung, xử lý đường dẫn tương thích Windows
│
├── tests/                      # Kiểm thử tự động (Unit test, Integration test)
│   ├── unit/
│   └── integration/
│
├── .gitignore                  # Cấu hình loại trừ file rác, dữ liệu lớn và cache Windows
├── requirements.txt            # Danh sách thư viện Python
└── README.md                   # Tài liệu hướng dẫn dự án
```

---

## 2. Các Bộ Dữ Liệu Khảo Sát (Hugging Face)

| Dataset | Mục đích sử dụng | Định dạng chính | Giấy phép | Cảnh báo tải |
|---|---|---|---|---|
| `vduydong/ocr_annual_financials` | BCTC hàng năm đã trích xuất OCR | `.txt`, `.png` | CC-BY-NC-4.0 | >18.000 file; chỉ lấy mẫu |
| `conghuy/ocr_financials_statements_2020_2025` | BCTC kiểm toán giai đoạn 2020 - 2025 | `.txt` | CC-BY-NC-4.0 | >22.000 file; chỉ lấy mẫu |
| `VietFinTabGroup/VietFinTab` | Cấu trúc bảng biểu BCTC tiếng Việt | `.json`, `.jpg` | CC-BY-NC-4.0 | >32.000 file; khảo sát nhãn |
| `AIGuruTinix/ViFinQA` | Hỏi đáp số liệu tài chính & QA BCTC | `.jsonl`, `.csv`, `.txt` | Đang cập nhật | Khảo sát `questions.jsonl` |
| `bsmock/FinTabNet.c` | Benchmark nhận diện cấu trúc bảng phức tạp | `.tar.gz` | CDLA-Permissive-2.0 | File nén >3.4 GB; **không tải trực tiếp** |

---

## 3. Hướng Dẫn Cài Đặt Trên Windows 10/11 (PowerShell)

### Bước 1: Khởi tạo môi trường ảo Python 3.13
Mở PowerShell tại thư mục dự án và chạy:
```powershell
# Sử dụng Python 3.13 đã cài đặt trên máy
& "C:\Users\admin\AppData\Local\Programs\Python\Python313\python.exe" -m venv .venv

# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1
```
*(Nếu gặp lỗi chính sách thực thi PowerShell, mở quyền tạm thời bằng lệnh: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`)*

### Bước 2: Cài đặt các thư viện thiết yếu
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 3: Cấu hình biến môi trường
Tạo file `.env` từ `.env.example` (file `.env` được loại trừ khỏi Git để bảo mật):
```powershell
Copy-Item .env.example .env
```
Cấu hình các tham số cần thiết trong `.env`:
- `OPENROUTER_API_KEY`: Khóa API OpenRouter (nếu chưa có, hệ thống tự động kích hoạt Deterministic Fallback)
- `OPENROUTER_MODEL`: Mô hình AI mặc định (`google/gemma-4-31b-it:free`)
- `TESSERACT_CMD`: Đường dẫn tesseract executable nếu cần OCR tài liệu quét (mặc định Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

---

## 4. Khởi Chạy Dashboard Tương Tác (Sprint 6)

Chạy ứng dụng Streamlit trực tiếp từ môi trường ảo:
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Ứng dụng sẽ tự động mở trên trình duyệt tại địa chỉ mặc định: `http://localhost:8501`.

### 4.1. Quy trình Phân tích (End-to-End Pipeline)
1. **Tải dữ liệu lên hoặc chọn mẫu có sẵn**:
   - Chọn mẫu BCTC kiểm toán sẵn có (CTCP 32 năm 2020 hoặc 2017) để kiểm thử nhanh mà không cần tải file.
   - Hoặc tải tệp BCTC của doanh nghiệp (PDF, ảnh PNG/JPG/JPEG, hoặc file TXT chuẩn hóa).
2. **Trích xuất thông tin (Extraction)**:
   - Module `PDFExtractor` tự động phân loại trang PDF văn bản số (Native text) hoặc trang quét cần OCR Tesseract (tiếng Việt `vie+eng`).
3. **Chuẩn hóa & Ánh xạ ngữ nghĩa (Parsing & Mapping)**:
   - `FinancialStatementParser` nhận diện Bảng Cân đối kế toán (B01-DN) và Báo cáo Kết quả Kinh doanh (B02-DN), ánh xạ theo mã số và danh mục từ đồng nghĩa Thông tư 200/2014/TT-BTC.
4. **Kiểm định tính cân đối kế toán (TT200 Validation)**:
   - `FinancialValidator` kiểm tra đẳng thức tổng tài sản = tổng nguồn vốn, cân đối doanh thu, chi phí, lợi nhuận.
5. **Tính toán 14 Chỉ số Tài chính (Ratio Engine)**:
   - `FinancialRatioCalculator` sử dụng số học `Decimal` chính xác, xử lý an toàn mẫu số 0, vốn CSH âm và số dư bình quân.
6. **Đánh giá Sức khỏe & Cảnh báo Rủi ro (Health Assessment)**:
   - `FinancialHealthAssessor` phân loại trạng thái (`ADEQUATE`, `WATCH`, `ALERT`, `NO_BENCHMARK`, `UNDEFINED`) và phát cảnh báo rủi ro có bằng chứng số liệu.
7. **Nhận định Chuyên sâu AI & Fallback**:
   - `AIFinancialInterpreter` tạo báo cáo điều hành chuyên sâu qua mô hình Gemma 4 (OpenRouter). Nếu API không sẵn sàng hoặc thiếu key, hệ thống tự động chuyển sang cơ chế **Deterministic Fallback** bảo đảm dịch vụ hoạt động liên tục.
8. **Xuất báo cáo (Export)**:
   - Tải báo cáo phân tích toàn diện dạng **JSON** hoặc danh mục 14 tỷ số và cảnh báo dạng **CSV** (hỗ trợ tiếng Việt UTF-8 BOM).

### 4.2. Cơ chế AI Interpretation và Deterministic Fallback
- Khi có `OPENROUTER_API_KEY`: Mô hình LLM phân tích chuyên sâu dựa trên số liệu đã kiểm chứng bởi Python (Ground truth), ngăn chặn hiện tượng ảo giác (hallucination).
- Khi **không có API key** hoặc kết nối API gián đoạn: Hệ thống tự động chuyển đổi trong 0 giây sang bộ nhận định xác định (Deterministic Rule Engine), tổng hợp điểm mạnh, rủi ro và khuyến nghị từ 14 tỷ số mà không làm dừng ứng dụng.

---

## 5. Chạy Kiểm Thử Tự Động (Test Suite)

Chạy toàn bộ 124 kiểm thử tự động (Unit & Integration tests):
```powershell
.\.venv\Scripts\python.exe -m pytest -v tests/
```
Chạy nhanh (quiet mode):
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## 6. Giới Hạn Cần Lưu Ý (Known Limitations)

1. **Ngưỡng sàng lọc minh họa**: Các ngưỡng phân loại rủi ro (thanh khoản, đòn bẩy) là ngưỡng sàng lọc quy tắc ban đầu, không đại diện cho chuẩn mực pháp lý hay chuẩn ngành cố định cho mọi lĩnh vực.
2. **Dữ liệu đơn kỳ**: BCTC 1 năm đơn lẻ chưa phản ánh đầy đủ chu kỳ mùa vụ hoặc xu hướng trung dài hạn.
3. **Mô hình AI miễn phí**: Mô hình `google/gemma-4-31b-it:free` trên OpenRouter có thể chịu giới hạn tốc độ (rate limit) trong giờ cao điểm. Trong trường hợp đó, hệ thống sẽ tự động kích hoạt Deterministic Fallback an toàn.
