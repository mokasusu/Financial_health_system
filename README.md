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

### Bước 3: Đăng ký Kernel vào Jupyter
```powershell
python -m ipykernel install --user --name financial_health_env --display-name "Python 3.13 (Financial Health)"
```

### Bước 4: Khởi chạy Jupyter Notebook
```powershell
jupyter notebook notebooks/01_data_exploration.ipynb
# Hoặc mở trực tiếp file .ipynb trên VS Code và chọn kernel "Python 3.13 (Financial Health)"
```

---

## 4. Định Hướng Phát Triển Tiếp Theo

1. **Giai đoạn 1 (Hiện tại)**: Khảo sát Metadata và mẫu nhỏ các bộ dữ liệu, xác định schema dữ liệu mục tiêu.
2. **Giai đoạn 2**: Xây dựng Pipeline chuẩn hóa dữ liệu BCTC tiếng Việt (Bảng cân đối kế toán, Báo cáo kết quả kinh doanh, Báo cáo lưu chuyển tiền tệ).
3. **Giai đoạn 3**: Phát triển module tính toán chỉ số tài chính & bộ đánh giá sức khỏe (Financial Health Scoring).
4. **Giai đoạn 4**: Xây dựng bộ kiểm thử tự động (Unit & Integration Tests) đảm bảo tính toàn vẹn số học.
5. **Giai đoạn 5**: Thiết kế giao diện Dashboard phân tích với Streamlit.
