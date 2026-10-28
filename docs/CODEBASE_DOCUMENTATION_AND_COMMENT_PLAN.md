# Kế Hoạch Bổ Sung Docstrings & Comments Toàn Diện Cho Hệ Thống (Clean Architecture)

## 1. Tóm Tắt Yêu Cầu (Understanding Summary)
* **Mục tiêu**: Bổ sung hệ thống Docstring (chuẩn Google Style tiếng Việt) và Inline Comments chất lượng cao cho toàn bộ mã nguồn `src/` và `app.py`.
* **Ý nghĩa & Mục đích**: Giúp mã nguồn minh bạch nghiệp vụ kế toán TT200/2014/TT-BTC, chuẩn hóa số học `Decimal`, giải thích rõ các giải thuật Regex, bóc tách bảng và AI commentary; phục vụ chuyển giao và mở rộng mã nguồn lâu dài.
* **Phạm vi áp dụng**:
  * Tầng 1 - Domain: `src/domain/` (Models, Accounting, Ratios, Assessment).
  * Tầng 2 - Application: `src/application/` (Interfaces, Services).
  * Tầng 3 - Infrastructure: `src/infrastructure/` (OCR, PDF, AI, Factories).
  * Tầng 4 - Presentation: `src/presentation/` (Controller, State, Styles, Formatters, Components).
  * Entry Point: `app.py`.
* **Ràng buộc cốt lõi**:
  * Giữ nguyên 100% logic thực thi, không thay đổi tên hàm/biến hay kiểu dữ liệu.
  * Đảm bảo 202/202 unit tests tiếp tục pass 100%.
* **Phi mục tiêu**: Không can thiệp vào thư mục kiểm thử `tests/`.

---

## 2. Giả Định & Nguyên Tắc Chú Thích (Assumptions & Rules)
1. **Google Style Python Docstrings**:
   * Mô tả tổng quan chức năng nghiệp vụ kế toán/tài chính.
   * `Args:` Tên tham số, kiểu dữ liệu, giải thích ý nghĩa và đơn vị đo lường (VND, %, lần...).
   * `Returns:` Kiểu dữ liệu trả về, cấu trúc dữ liệu và ý nghĩa kinh tế.
   * `Raises:` Các ngoại lệ có thể phát sinh nếu có.
   * `Note:` Lưu ý kiểm toán, xử lý ngoại lệ chia cho 0, số âm ngoặc đơn, bảo mật bộ nhớ (Zero File Retention).
2. **Inline Comments**:
   * Chỉ đặt trước các đoạn mã có độ phức tạp cao: các biểu thức Regex nhận diện ngày tháng/niên độ tài chính, giải thuật gom dòng OCR, thuật toán Resilient JSON Repair, v.v.
   * Tuyệt đối tránh comment hiển nhiên, rườm rà.

---

## 3. Nhật Ký Quyết Định Thiết Kế (Decision Log)

| STT | Quyết định | Các phương án đã cân nhắc | Lý do lựa chọn |
|---|---|---|---|
| 1 | Sử dụng chuẩn **Google Style Docstrings** tiếng Việt | Tự do `#`, NumPy Style, Sphinx reST | Tương thích cao với IDE (VSCode, PyCharm), hiển thị tooltip đẹp, rõ ràng giữa Args/Returns |
| 2 | Áp dụng cho toàn bộ `src/` và `app.py` | Chỉ áp dụng cho Domain & Application | Tạo sự đồng bộ chuyên nghiệp xuyên suốt toàn bộ 4 phân tầng của kiến trúc Clean Architecture |
| 3 | Chú trọng giải thích thuật ngữ kế toán TT200 & số học `Decimal` | Chỉ giải thích kỹ thuật lập trình thuần túy | Giúp lập trình viên và chuyên gia tài chính hiểu sâu bản chất nghiệp vụ kinh tế đằng sau từng dòng code |
| 4 | Thực hiện và kiểm thử độc lập theo từng phân tầng | Chỉnh sửa hàng loạt toàn bộ file cùng lúc | Giảm thiểu tối đa rủi ro gõ nhầm cú pháp; xác nhận 202 tests pass sau từng bước |

---

## 4. Thiết Kế Chi Tiết Theo Phân Tầng

### Giai đoạn 1: Tầng Domain (`src/domain/`)
* **`models/`**:
  * `bctc.py`: Chú thích các thực thể kế toán `BalanceSheet`, `IncomeStatement`, `FinancialReport`.
  * `line_item.py`: Chú thích thực thể chỉ tiêu kế toán `FinancialLineItem`, `StatementMetadata`.
  * `ratios.py`: Chú thích `RatioResult`, `FinancialRatioReport`, các enum trạng thái tính toán.
  * `assessment.py`: Chú thích mô hình đánh giá rủi ro `FinancialAssessment`, `HealthStatus`.
  * `ai.py`: Chú thích các mô hình kết quả AI `AIInterpretationOutput`, `CoreKPIItem`.
  * `ocr.py`: Chú thích khung dữ liệu OCR `DocumentExtractionResult`, `PageExtractionResult`.
* **`accounting/`**:
  * `canonical.py`: Bảng từ điển chỉ tiêu chuẩn Thông tư 200/2014/TT-BTC.
  * `normalizer.py`: Giải thuật chuẩn hóa số học Việt Nam và số âm ngoặc đơn.
  * `validator.py`: Giải thích 4 đẳng thức cân đối kế toán bắt buộc.
  * `lexicon.py`: Thuật toán sửa lỗi chính tả OCR chuyên ngành kế toán.
  * `metadata_extractor.py`: Các biểu thức Regex bóc tách thời gian và bộ lọc blacklist đơn vị kiểm toán.
* **`ratios/engine.py`**:
  * 14 công thức tính toán tỷ số tài chính chính xác tuyệt đối bằng `Decimal`.
* **`assessment/`**:
  * `thresholds.py`: Hệ thống ngưỡng chuẩn ngành thị trường Việt Nam.
  * `evaluator.py`: Động cơ chấm điểm và phân loại rủi ro 3 cấp độ (An toàn, Theo dõi, Cảnh báo).

### Giai đoạn 2: Tầng Application (`src/application/`)
* **`interfaces/`**:
  * `ocr.py`, `ai.py`, `pdf.py`: Chú thích các Abstract Protocol theo nguyên lý Đảo ngược phụ thuộc (DIP).
* **`services/`**:
  * `pipeline_service.py`: Luồng phân tích E2E và cơ chế xử lý hoàn toàn trong RAM (Zero File Retention).
  * `parsing_service.py`: Giải thuật bóc tách bảng BCTC, phân trang và gom dòng dữ liệu.
  * `financial_service.py`: Điều phối tính toán tỷ số và đánh giá sức khỏe doanh nghiệp.
  * `ai_service.py`: Cấu trúc prompt AI Senior Financial Analyst và xử lý kết quả nhận định.
  * `export_service.py`: Định dạng xuất dữ liệu JSON và CSV UTF-8 BOM chuẩn cho Microsoft Excel.

### Giai đoạn 3: Tầng Infrastructure (`src/infrastructure/`)
* **`ocr/`**:
  * `paddle_engine.py`: Động cơ PaddleOCR GPU với cơ chế tự động fallback CPU an toàn.
  * `preprocessor.py`: Giải thuật tiền xử lý ảnh OpenCV (xoay ảnh, deskew, tăng độ tương phản).
* **`pdf/`**:
  * `extractor.py`: Định tuyến thông minh 3 tuyến tài liệu (Native PDF, Scanned PDF, Hỗn hợp).
* **`ai/`**:
  * `client.py`: OpenRouter Client, cơ chế Exponential Backoff và thuật toán Resilient JSON Repair.
* **`factories.py`**:
  * `ServiceFactory`: Bộ điều phối Dependency Injection trung tâm với cơ chế Lazy Import.

### Giai đoạn 4: Tầng Presentation (`src/presentation/`) & Entry Point
* **`presentation/`**:
  * `controller.py`: Bộ điều hướng luồng giao diện Streamlit và hiển thị tiến trình.
  * `state.py`: Quản lý và cách ly vòng đời Session State an toàn trong RAM.
  * `styles.py`: Hệ thống theme Glassmorphism và custom badges.
  * `formatters.py`: Hàm định dạng tiền tệ VND, tỷ lệ phần trăm và số lần.
  * `components/`: Toàn bộ 6 khối UI độc lập (`top_bar`, `statement_tables`, `kpi_cards`, `balance_checks`, `ai_commentary`, `export_panel`).
* **`app.py`**:
  * Thin bootstrap entry point (<35 dòng).

---

## 5. Quy Trình Thực Hiện & Kiểm Thử
1. Chạy cú pháp lint / compile trước khi lưu từng tệp.
2. Chạy `pytest tests/unit/` sau khi hoàn tất mỗi giai đoạn.
3. Kiểm tra bảo đảm giữ vững tỷ lệ pass **202 / 202 unit tests (100%)**.
