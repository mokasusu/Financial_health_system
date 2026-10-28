# Financial Health System 📊🇻🇳
### Hệ Thống Trích Xuất BCTC & Đánh Giá Sức Khỏe Doanh Nghiệp (TT200/2014/TT-BTC)

[![Python 3.10 - 3.13](https://img.shields.io/badge/Python-3.10_--_3.13-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/Dashboard-Streamlit-red.svg)](app.py)
[![OCR](https://img.shields.io/badge/OCR-PaddleOCR%20CUDA%20%7C%20GPU-green.svg)](src/infrastructure/ocr/)
[![AI](https://img.shields.io/badge/AI-OpenRouter%20%7C%20Multi--Model-purple.svg)](https://openrouter.ai/)
[![Precision](https://img.shields.io/badge/Arithmetic-Exact%20Decimal-success.svg)](src/domain/ratios/)
[![Architecture](https://img.shields.io/badge/Architecture-Clean%204--Layer-informational.svg)](docs/CLEAN_ARCHITECTURE_DESIGN_AND_PLAN.md)
[![Tests](https://img.shields.io/badge/Tests-202%20Passed%20(100%25)-brightgreen.svg)](tests/unit/)
[![Standard](https://img.shields.io/badge/Accounting-TT200%2F2014%2FTT--BTC-orange.svg)](https://thuvienphapluat.vn/)

**Financial Health System** là giải pháp phần mềm chuyên sâu tự động hóa quy trình phân tích Báo cáo tài chính (BCTC Hợp nhất và BCTC Riêng theo **Thông tư 200/2014/TT-BTC**). Hệ thống tiếp nhận tài liệu số hóa đa định dạng (PDF văn bản, PDF scan dạng ảnh hoặc ảnh chụp BCTC), tự động bóc tách số liệu qua mô hình thị giác máy học kết hợp OCR tăng tốc GPU, chuẩn hóa cấu trúc kế toán, kiểm định 4 đẳng thức cân đối kế toán, tính toán 14 tỷ số tài chính với số học `Decimal` tuyệt đối, và cung cấp nhận định điều hành chuyên sâu bằng Trí tuệ nhân tạo (AI Financial Interpreter) thông qua OpenRouter API.

> 🔒 **Quyền riêng tư & Zero File Retention**: Xử lý hoàn toàn trong bộ nhớ RAM (In-Memory Processing). Tuyệt đối không lưu trữ tệp người dùng tải lên ra ổ đĩa và giải phóng bộ nhớ ngay sau khi kết thúc phiên phân tích.

---

## 🚀 Tính Năng Cốt Lõi & Điểm Mới Nổi Bật

### 1. 🤖 Nhận Định Tài Chính Bằng AI Độc Lập (100% Authentic AI Commentary)
* **Không sử dụng nhận xét cấu hình sẵn (Zero Canned Commentary)**: Loại bỏ hoàn toàn các câu văn mẫu hoặc nhận xét luật cứng được viết sẵn. Mọi phân tích, đánh giá điểm mạnh, cảnh báo rủi ro và khuyến nghị chiến lược đều được suy luận trực tiếp và khách quan bởi mô hình AI dựa trên số liệu thực tế.
* **Tập trung vào 4 Chỉ số Tài chính Cốt lõi (Core Financial KPIs)**:
  * **Khả năng thanh toán hiện hành (Current Ratio)**: $\frac{\text{Tài sản ngắn hạn}}{\text{Nợ ngắn hạn}}$ (Đo lường thanh khoản ngắn hạn).
  * **Hệ số Nợ / Vốn CSH (Debt to Equity)**: $\frac{\text{Nợ phải trả}}{\text{Vốn CSH}}$ (Đo lường đòn bẩy tài chính và an toàn vốn).
  * **Tỷ suất sinh lời trên Tổng tài sản (ROA)**: $\frac{\text{Lợi nhuận sau thuế}}{\text{Tổng tài sản}}$ (Đo lường hiệu quả sinh lời trên tài sản).
  * **Tỷ suất sinh lời trên Vốn CSH (ROE)**: $\frac{\text{Lợi nhuận sau thuế}}{\text{Vốn CSH}}$ (Đo lường hiệu quả sinh lời cho cổ đông).
* **Hỗ trợ Meta-Model OpenRouter Free & Paid**: Tương thích hoàn hảo với model miễn phí `openrouter/free` (tự động định tuyến tối ưu đến các model miễn phí sẵn có như Nemotron, Cohere, Qwen...) cũng như các model thương mại cao cấp (Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro...).
* **Thuật toán Tự khôi phục JSON (Resilient JSON Repair)**: Khắc phục triệt để hiện tượng token bị ngắt giữa chừng ở các mô hình AI mã nguồn mở miễn phí, tự động cân bằng cấu trúc JSON và ngăn ngừa hoàn toàn lỗi `ResponseValidationError`.
* **Hot-Reloading Cấu hình**: Nhận diện thay đổi API Key và Model trong `.env` ngay lập tức tại thời điểm bấm phân tích mà không cần khởi động lại Streamlit server.

### 2. ⚡ Trích Xuất Siêu Tốc với PaddleOCR GPU & Tiền Xử Lý Ảnh OpenCV
* **Tự động nhận diện 3 tuyến tài liệu**:
  * **Tuyến 1**: PDF văn bản số (Native text) trích xuất tức thì qua PyMuPDF/pdfplumber.
  * **Tuyến 2**: PDF scan / tài liệu quét hình ảnh trích xuất qua PaddleOCR GPU.
  * **Tuyến 3**: PDF hỗn hợp (vừa có trang văn bản vừa có bảng biểu dạng ảnh scan).
* **Tiền xử lý hình ảnh chuyên sâu (`ImagePreprocessor`)**: Tự động xoay và cân chỉnh góc nghiêng (deskew), khử nhiễu và tăng cường độ tương phản (adaptive thresholding) với OpenCV trước khi đưa vào mô hình OCR.
* **Từ điển Kế toán Chuyên sâu (`FinancialLexiconCorrector`)**: Tự động sửa các lỗi chính tả đặc thù ngành kế toán phát sinh trong quá trình OCR văn bản tiếng Việt có dấu.
* **Bộ lọc Blacklist Hãng kiểm toán**: Tự động nhận diện và loại trừ các đơn vị kiểm toán độc lập hàng đầu (KPMG, PwC, Deloitte, Ernst & Young, Grant Thornton, BDO, A&C...) để tránh nhận diện nhầm đơn vị kiểm toán là doanh nghiệp lập báo cáo.

### 3. 📑 Chuẩn Hóa & Kiểm Định Cân Đối Kế Toán TT200
* **Nhận diện mẫu báo cáo kế toán chuẩn**: Bảng cân đối kế toán (Mẫu B01-DN) và Báo cáo Kết quả hoạt động kinh doanh (Mẫu B02-DN).
* **Chuẩn hóa định dạng số Việt Nam**: Nhận diện chuẩn xác dấu chấm phân cách hàng nghìn (`1.234.567`), dấu phẩy thập phân (`89`) và số âm trong ngoặc đơn kế toán `(45.000)`.
* **Tự động kiểm tra 4 đẳng thức cân đối kế toán trọng yếu**:
  1. $\text{Tổng tài sản} = \text{Tài sản ngắn hạn} + \text{Tài sản dài hạn}$
  2. $\text{Tổng nguồn vốn} = \text{Nợ phải trả} + \text{Vốn chủ sở hữu}$
  3. $\text{Tổng tài sản} = \text{Tổng nguồn vốn}$
  4. $\text{Lợi nhuận sau thuế} = \text{Lợi nhuận trước thuế} - \text{Chi phí thuế TNDN}$

### 4. 📐 Động Cơ 14 Tỷ Số Tài Chính `Decimal` Chính Xác Tuyệt Đối
* **Loại trừ hoàn toàn sai số làm tròn số thực**: Sử dụng kiểu dữ liệu `Decimal` của Python trong toàn bộ các phép tính tỷ số tài chính.
* **Bao phủ 4 nhóm tỷ số phân tích**:
  * **Nhóm Thanh khoản**: Khả năng thanh toán hiện hành, Khả năng thanh toán nhanh, Khả năng thanh toán tức thời.
  * **Nhóm Đòn bẩy tài chính**: Tỷ số Nợ / Vốn CSH, Nợ / Tổng tài sản, Đòn bẩy tài chính (FL).
  * **Nhóm Hiệu quả hoạt động**: Vòng quay hàng tồn kho, Kỳ thu tiền bình quân, Vòng quay tổng tài sản.
  * **Nhóm Khả năng sinh lời**: ROA, ROE, ROS (Biên lợi nhuận ròng), Biên lợi nhuận gộp.

### 5. 🖥️ Dashboard Streamlit Tinh Gọn & Xuất Báo Cáo Chuyên Nghiệp
* **Giao diện làm sạch tối ưu (Clean UI)**: Đã loại bỏ các khối cấu hình rườm rà và dữ liệu demo mẫu.
* **Hiển thị ngày tháng chính xác**: Các cột số liệu thể hiện chuẩn xác ngày/tháng/năm của từng kỳ kế toán (ví dụ: `31/12/2026`, `01/01/2026`, Năm 2026, Năm 2025) thay cho nhãn chung chung "kỳ trước", "kỳ sau".
* **Phân loại rủi ro trực quan**: Đánh giá theo thang 3 cấp độ chuẩn mực (`AN TOÀN / ĐẠT`, `THEO DÕI`, `CẢNH BÁO`).
* **Xuất báo cáo đa định dạng**: Hỗ trợ xuất dữ liệu ra file **JSON toàn diện** hoặc **CSV** chuẩn UTF-8 BOM hiển thị tiếng Việt hoàn hảo trên Microsoft Excel.

---

## 🏗️ Kiến Trúc Clean Architecture 4 Phân Tầng

```text
               ┌────────────────────────────────────────────────────────┐
               │                   Presentation Layer                   │
               │      Streamlit Controller, Components, Formatters      │
               └───────────────────────────┬────────────────────────────┘
                                           │ Calls
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │                   Application Layer                    │
               │   Services: Pipeline, Financial, Parsing, AI, Export   │
               │   Abstract Interfaces: IOCREngine, IAIClient, etc.     │
               └───────────────┬────────────────────────┬───────────────┘
                               │                        │
                    Implements │ Interfaces             │ Uses
                               ▼                        ▼
┌──────────────────────────────────────┐       ┌────────────────────────┐
│         Infrastructure Layer         │       │      Domain Layer      │
│  PaddleOCR GPU, PyMuPDF, OpenCV,     │       │  Entities, ValueObjs,  │
│  OpenRouter Client, ServiceFactory   │       │  Accounting Rules,     │
└──────────────────────────────────────┘       │  14 Ratios Decimal Eng,│
                                               │  Assessment Evaluator  │
                                               └────────────────────────┘
```

### 🔍 Làm Rõ Chức Năng Từng Phân Tầng & Từng Thành Phần

Hệ thống được thiết kế theo đúng nguyên lý **Clean Architecture** của Robert C. Martin (Uncle Bob), đảm bảo sự tách biệt rõ ràng giữa các mối quan tâm (Separation of Concerns), tính độc lập công nghệ và khả năng kiểm thử toàn diện:

#### 1. 🏛️ Tầng Domain (`src/domain/`) — Nghiệp vụ cốt lõi & Quy chuẩn kinh tế
* **Vai trò**: Là hạt nhân trung tâm của toàn bộ hệ thống, chứa các quy tắc nghiệp vụ tài chính, kế toán bất biến và các mô hình dữ liệu lõi. Tầng này **hoàn toàn độc lập**, không phụ thuộc vào bất kỳ framework, cơ sở dữ liệu, giao diện người dùng hay thư viện bên ngoài nào.
* **Các thành phần chính**:
  * **`models/` (Thực thể & Đối tượng giá trị - Entities & Value Objects)**:
    * `line_item.py` (`FinancialLineItem`, `StatementMetadata`): Đại diện cho một dòng chỉ tiêu kế toán với mã số TT200, tên chỉ tiêu, số dư đầu kỳ/cuối kỳ (kiểu `Decimal`), cờ cảnh báo `needs_review` và metadata kỳ báo cáo.
    * `bctc.py` (`BalanceSheet`, `IncomeStatement`, `FinancialReport`): Mô hình hóa trọn vẹn Bảng cân đối kế toán (Mẫu B01-DN), Báo cáo kết quả hoạt động kinh doanh (Mẫu B02-DN) và Báo cáo tài chính tổng hợp.
    * `ratios.py` (`RatioResult`, `FinancialRatioReport`): Chuẩn hóa cấu trúc kết quả tính toán 14 chỉ số tài chính, công thức áp dụng, đơn vị đo lường và trạng thái khả dụng.
    * `assessment.py` (`FinancialAssessment`, `HealthStatus`): Cấu trúc hồ sơ đánh giá sức khỏe tài chính doanh nghiệp với 3 mức độ rủi ro (`AN TOÀN / ĐẠT`, `THEO DÕI`, `CẢNH BÁO`).
    * `ai.py` & `ocr.py`: Cấu trúc trung gian lưu trữ kết quả nhận dạng ký tự quang học và nhận định chuyên sâu từ AI.
  * **`accounting/` (Quy chuẩn kế toán Việt Nam)**:
    * `canonical.py`: Bảng từ điển chuẩn hóa danh mục mã số và tên gọi các chỉ tiêu theo Thông tư 200/2014/TT-BTC.
    * `normalizer.py` (`AccountingNormalizer`): Chuẩn hóa chuỗi số, phân tách dấu chấm/phẩy theo quy cách Việt Nam, tự động nhận diện và chuyển đổi số âm trong ngoặc đơn `(1.234)` sang giá trị số âm `Decimal`.
    * `validator.py` (`AccountingValidator`): Kiểm định 4 đẳng thức cân đối kế toán bắt buộc (Tổng tài sản = Tổng nguồn vốn, Cân đối tài sản ngắn/dài hạn, Cân đối nợ phải trả/vốn CSH, Cân đối lợi nhuận trước thuế).
    * `lexicon.py` (`FinancialLexiconCorrector`): Thuật toán sửa lỗi chính tả OCR chuyên ngành tài chính - kế toán (nhận diện nhầm dấu, ký tự tương đồng).
    * `metadata_extractor.py`: Sử dụng biểu thức chính quy (Regex) thông minh để bóc tách ngày tháng niên độ kế toán (ví dụ: `31/12/2026`) và lọc bỏ tên các công ty kiểm toán/đơn vị độc lập.
  * **`ratios/engine.py` (`FinancialRatioCalculator`)**:
    * Động cơ tính toán độc lập 14 tỷ số tài chính then chốt thuộc 4 nhóm (Thanh khoản, Đòn bẩy tài chính, Hiệu quả hoạt động, Khả năng sinh lời). Sử dụng kiểu dữ liệu `Decimal` chính xác tuyệt đối, tự động xử lý an toàn ngoại lệ chia cho 0 hoặc vốn chủ sở hữu âm.
  * **`assessment/` (`thresholds.py`, `evaluator.py`)**:
    * Thiết lập hệ thống ngưỡng chuẩn ngành thị trường Việt Nam và thuật toán tự động chấm điểm, phân loại rủi ro sức khỏe tài chính doanh nghiệp.

---

#### 2. ⚙️ Tầng Application (`src/application/`) — Điều phối & Các trường hợp sử dụng (Use Cases)
* **Vai trò**: Đóng vai trò là cầu nối điều phối giữa giao diện người dùng và nghiệp vụ cốt lõi. Tầng này chứa toàn bộ luồng nghiệp vụ ứng dụng (Use Cases) và định nghĩa các giao diện trừu tượng theo nguyên lý **Đảo ngược phụ thuộc (Dependency Inversion Principle - DIP)**.
* **Các thành phần chính**:
  * **`interfaces/` (Giao diện trừu tượng / Protocols)**:
    * `pdf.py` (`IDocumentExtractor`): Giao diện chuẩn cho các bộ trích xuất nội dung từ tệp PDF/ảnh.
    * `ocr.py` (`IOCREngine`): Giao diện chuẩn cho các động cơ nhận dạng ký tự quang học OCR.
    * `ai.py` (`IAIClient`): Giao diện chuẩn cho việc giao tiếp với mô hình ngôn ngữ lớn (LLM).
  * **`services/` (Dịch vụ ứng dụng nghiệp vụ)**:
    * `pipeline_service.py` (`AnalysisPipelineService`): Nhạc trưởng điều phối toàn bộ chu trình phân tích E2E (Trích xuất $\rightarrow$ Bóc tách $\rightarrow$ Phân tích tài chính $\rightarrow$ Nhận định AI $\rightarrow$ Xuất báo cáo). Thực thi nghiêm ngặt nguyên tắc **Zero File Retention** (xử lý toàn bộ dữ liệu byte in-memory trong RAM).
    * `parsing_service.py` (`FinancialStatementParser`): Bóc tách cấu trúc bảng BCTC, phân trang, gom dòng và ánh xạ ngữ nghĩa 3 cấp độ ưu tiên (Khớp mã số chính xác $\rightarrow$ Khớp nhãn chuẩn $\rightarrow$ Khớp mờ khoảng cách Levenshtein).
    * `financial_service.py` (`FinancialAnalysisService`): Điều phối các bộ tính toán tỷ số, kiểm tra cân đối kế toán và tổng hợp hồ sơ sức khỏe tài chính.
    * `ai_service.py` (`AIInterpretationService`): Xây dựng prompt chuyên gia tài chính cấp cao (Senior Financial Analyst), gọi LLM, phục hồi JSON bị lỗi và lọc ảo giác số liệu (Hallucination Sanitization).
    * `export_service.py` (`ExportService`): Xuất dữ liệu phân tích ra tệp JSON chi tiết hoặc bảng tính CSV mã hóa UTF-8 BOM hiển thị tiếng Việt hoàn hảo trên Excel.

---

#### 3. 🔌 Tầng Infrastructure (`src/infrastructure/`) — Hạ tầng, Adapters & Công nghệ ngoài
* **Vai trò**: Chứa các triển khai cụ thể (Implementations) của các giao diện trừu tượng được Tầng Application định nghĩa, đồng thời tích hợp các thư viện bên thứ ba, driver phần cứng (GPU/CUDA) và các dịch vụ API bên ngoài.
* **Các thành phần chính**:
  * **`pdf/extractor.py` (`PDFExtractor`)**:
    * Kiến trúc định tuyến 3 tuyến tài liệu thông minh: Tuyến A (PDF văn bản số qua PyMuPDF), Tuyến B (PDF bản scan / ảnh qua OCR), Tuyến C (PDF hỗn hợp với giải thuật khử trùng lặp không gian dựa trên IoU).
  * **`ocr/paddle_engine.py` (`PaddleOCREngine`)**:
    * Động cơ OCR tối ưu hóa cho tiếng Việt dựa trên PaddleOCR. Hỗ trợ tăng tốc phần cứng GPU NVIDIA (CUDA), tự động chuyển đổi dự phòng (fallback) sang CPU an toàn; cơ chế trích xuất 1 lượt (Single-pass).
  * **`ocr/preprocessor.py` (`ImagePreprocessor`)**:
    * Bộ tiền xử lý hình ảnh sử dụng OpenCV: cân bằng sáng thích nghi (CLAHE), tăng cường độ sắc nét (Unsharp Mask) và tự động xoay nắn góc nghiêng (Deskew) trước khi đưa vào OCR.
  * **`ai/client.py` (`OpenRouterClient`)**:
    * Adapter kết nối với OpenRouter API. Tích hợp cơ chế tự động thử lại (Exponential Backoff), thuật toán sửa lỗi chuỗi JSON (Resilient JSON Repair) và bảo mật tuyệt đối che giấu khóa API Key trong logs.
  * **`factories.py` (`ServiceFactory`)**:
    * Bộ chứa Dependency Injection (DI Container) trung tâm của hệ thống, quản lý cơ chế nạp chậm (Lazy Import) giúp ứng dụng khởi động tức thì.

---

#### 4. 🖥️ Tầng Presentation (`src/presentation/`) & Entry Point (`app.py`) — Giao diện người dùng
* **Vai trò**: Phụ trách toàn bộ trải nghiệm tương tác của người dùng trên giao diện web Streamlit. Nhận yêu cầu từ người dùng, hiển thị trực quan các biểu đồ, bảng dữ liệu BCTC và cho phép chỉnh sửa tương tác trực tiếp.
* **Các thành phần chính**:
  * **`app.py`**: Điểm khởi chạy tối giản (Thin bootstrap entry point < 35 dòng code), khởi tạo controller và điều hướng luồng.
  * **`controller.py` (`StreamlitAnalysisController`)**: Bộ điều phối máy trạng thái giao diện 3 giai đoạn (Landing $\rightarrow$ Analyzing $\rightarrow$ Dashboard) và quản lý thanh tiến trình trực quan.
  * **`state.py` (`SessionStateManager`)**: Đóng gói và cô lập toàn bộ trạng thái phiên làm việc trong `st.session_state` (In-Memory), ngăn chặn xung đột dữ liệu giữa các lần tương tác.
  * **`styles.py`**: Hệ thống thiết kế Glassmorphism hiện đại (Frosted Glass), dark/light mode responsive tokens và hệ thống badges phân loại trạng thái rủi ro.
  * **`formatters.py`**: Các hàm định dạng số liệu tiền tệ (VND), tỷ số tài chính, tỷ lệ phần trăm (%) và chênh lệch kỳ báo cáo.
  * **`components/` (6 khối giao diện độc lập & có thể tái sử dụng)**:
    * `top_bar.py`: Header thương hiệu, metadata doanh nghiệp, trạng thái kiểm toán và nút phân tích lại.
    * `kpi_cards.py`: 4 thẻ chỉ số tài chính cốt lõi (Current Ratio, Debt/Equity, Net Margin, ROE) với mã màu rủi ro động.
    * `balance_checks.py`: Bảng kiểm định 4 đẳng thức cân đối kế toán & Ma trận phân tích 14 tỷ số.
    * `statement_tables.py`: Bảng dữ liệu tương tác cho Bảng cân đối kế toán (B01-DN) và Báo cáo KQKD (B02-DN), cho phép người dùng sửa đổi số liệu trực tiếp và bấm "Tái tính toán".
    * `ai_commentary.py`: Báo cáo nhận định tài chính chuyên sâu từ AI (Tóm tắt điều hành, Điểm mạnh, Rủi ro tiềm ẩn, Khuyến nghị chiến lược).
    * `export_panel.py`: Khối chức năng tải dữ liệu xuất ra tệp JSON hoặc bảng tính CSV.

---

## 📂 Cấu Trúc Thư Mục Dự Án (Clean Architecture)

```text
Financial_health_system/
├── app.py                                # Thin Entry Point Streamlit (<35 lines)
├── requirements.txt                      # Danh sách thư viện phụ thuộc
├── .env.example                          # File mẫu cấu hình biến môi trường
├── .env                                  # Cấu hình môi trường (API Key, Model - không commit)
├── src/                                  # Kiến trúc chuẩn 4 phân tầng Clean Architecture
│   ├── domain/                           # 1. Tầng Domain (Nghiệp vụ cốt lõi, độc lập)
│   │   ├── models/                       # Domain Entities & Value Objects (Pydantic, Decimal)
│   │   │   ├── bctc.py                   # BalanceSheet, IncomeStatement, FinancialReport
│   │   │   ├── line_item.py              # FinancialLineItem, StatementMetadata
│   │   │   ├── ratios.py                 # RatioResult, FinancialRatioReport
│   │   │   ├── assessment.py             # FinancialAssessment, RatioAssessment
│   │   │   ├── ai.py                     # AIInterpretationOutput, CoreKPIItem
│   │   │   └── ocr.py                    # DocumentExtractionResult, PageExtractionResult
│   │   ├── accounting/                   # Chuẩn hóa kế toán TT200 & Kiểm định cân đối
│   │   │   ├── canonical.py              # Mã số và tên chuẩn TT200
│   │   │   ├── normalizer.py             # Chuẩn hóa số học Việt Nam & số âm
│   │   │   ├── validator.py              # 4 đẳng thức cân đối kế toán
│   │   │   ├── lexicon.py                # FinancialLexiconCorrector
│   │   │   └── metadata_extractor.py     # Trích xuất metadata BCTC
│   │   ├── ratios/                       # Động cơ tính 14 tỷ số tài chính (Decimal)
│   │   │   └── engine.py                 # FinancialRatioCalculator
│   │   └── assessment/                   # Đánh giá sức khỏe & phân loại rủi ro
│   │       ├── thresholds.py             # Ngưỡng phân loại
│   │       └── evaluator.py              # FinancialHealthAssessor
│   ├── application/                      # 2. Tầng Application (Use cases & Điều phối)
│   │   ├── interfaces/                   # Các Interfaces trừu tượng (DIP)
│   │   │   ├── ocr.py                    # IOCREngine
│   │   │   ├── ai.py                     # IAIClient
│   │   │   └── pdf.py                    # IDocumentExtractor
│   │   └── services/                     # Ứng dụng nghiệp vụ
│   │       ├── pipeline_service.py       # AnalysisPipelineService điều phối E2E
│   │       ├── parsing_service.py        # FinancialStatementParser
│   │       ├── financial_service.py      # FinancialAnalysisService
│   │       ├── ai_service.py             # AIInterpretationService
│   │       └── export_service.py         # ExportService (CSV UTF-8 BOM, JSON)
│   ├── infrastructure/                   # 3. Tầng Infrastructure (Frameworks, Adapters)
│   │   ├── ocr/                          # PaddleOCR GPU Engine & OpenCV Deskew
│   │   │   ├── paddle_engine.py          # PaddleOCREngine (CUDA / CPU)
│   │   │   └── preprocessor.py           # ImagePreprocessor (OpenCV)
│   │   ├── pdf/                          # Trích xuất PDF số & Scanned
│   │   │   └── extractor.py              # PDFExtractor
│   │   ├── ai/                           # OpenRouter API Integration
│   │   │   └── client.py                 # OpenRouterClient (Resilient JSON Repair)
│   │   └── factories.py                  # ServiceFactory (Dependency Injection)
│   ├── presentation/                     # 4. Tầng Presentation (Giao diện Streamlit)
│   │   ├── controller.py                 # Streamlit UI flow controller
│   │   ├── state.py                      # Session state management
│   │   ├── styles.py                     # CSS Glassmorphism & Custom Badges
│   │   ├── formatters.py                 # Formatters tiền tệ, tỷ số, phần trăm
│   │   └── components/                   # Reusable UI Components
│   │       ├── top_bar.py                # Tiêu đề, badges trạng thái
│   │       ├── statement_tables.py       # Bảng B01-DN & B02-DN
│   │       ├── kpi_cards.py              # Thẻ 4 Core KPIs & 14 Tỷ số
│   │       ├── balance_checks.py         # 4 đẳng thức cân đối kế toán
│   │       ├── ai_commentary.py          # Khối nhận định AI độc lập
│   │       └── export_panel.py           # Panel tải JSON & CSV
│   └── utils/                            # Tiện ích bổ trợ chung
├── data/                                 # Dữ liệu phục vụ kiểm thử
│   └── samples/                          # BCTC mẫu demo (CTCP 32, Vinamilk...)
├── docs/                                 # Tài liệu kỹ thuật & kiến trúc
└── tests/                                # Bộ kiểm thử tự động toàn diện
    └── unit/                             # 202 Unit tests kiểm định toàn bộ hệ thống
```

---

## ⚡ Cài Đặt & Khởi Chạy Nhanh

### 1. Yêu cầu môi trường
* **Hệ điều hành**: Windows 10/11, Ubuntu/Linux hoặc macOS.
* **Phiên bản Python**: `Python 3.10` đến `Python 3.13` (Khuyến nghị `Python 3.11` hoặc `3.13`).
* **Phần cứng**: Tối thiểu 4GB RAM. Khuyến nghị máy có GPU NVIDIA (VRAM ≥ 4GB) để tăng tốc PaddleOCR tối đa.

### 2. Cài đặt môi trường ảo & Thư viện
```powershell
# Tạo môi trường ảo Python
python -m venv .venv

# Kích hoạt môi trường ảo (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Nâng cấp pip và cài đặt dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Cấu hình OpenRouter AI (Khuyến nghị)
Hệ thống sử dụng **OpenRouter AI Gateway** để tạo nhận định chuyên sâu từ 4 chỉ số tài chính cốt lõi.

1. Đăng ký tài khoản và tạo API Key miễn phí tại [OpenRouter.ai](https://openrouter.ai/keys).
2. Tạo file `.env` từ file mẫu:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Mở file `.env` và điền cấu hình:
   ```env
   # API Key lấy từ https://openrouter.ai/keys
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # Model sử dụng (Khuyến nghị dùng openrouter/free hoặc model tùy chọn)
   OPENROUTER_MODEL=openrouter/free
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   ```

> 💡 **Lưu ý**: Nếu chưa cấu hình `OPENROUTER_API_KEY`, hệ thống sẽ hiển thị bảng thông báo hướng dẫn cấu hình rõ ràng ngay trên Dashboard. Hệ thống tuân thủ nguyên tắc **không sử dụng nhận xét cấu hình sẵn / bịa đặt**.

### 4. Khởi chạy Dashboard
```powershell
streamlit run app.py
```
Truy cập trình duyệt tại địa chỉ: `http://localhost:8501`.

---

## 🏛️ Nguyên Tắc Thiết Kế Clean Architecture

Hệ thống được thiết kế theo mô hình **Pragmatic Clean Architecture** 4 phân tầng nghiêm ngặt với luồng phụ thuộc một chiều hướng tâm (Inward Dependency Rule):

1. **Domain Layer (`src/domain/`) - Trọng tâm nghiệp vụ**:
   * Độc lập hoàn toàn với framework, cơ sở dữ liệu và giao diện.
   * Số học kế toán chính xác tuyệt đối: 100% phép tính tỷ số tài chính sử dụng kiểu dữ liệu `Decimal` của Python (loại bỏ hoàn toàn sai số `IEEE 754` của kiểu số thực `float`).
   * Kiểm định 4 đẳng thức cân đối kế toán theo quy định chuẩn của **Thông tư 200/2014/TT-BTC**.

2. **Application Layer (`src/application/`) - Điều phối Use Cases**:
   * Chứa các Service cốt lõi: `AnalysisPipelineService` (điều phối luồng E2E), `FinancialStatementParser` (bóc tách bảng BCTC), `FinancialAnalysisService` (tính toán & đánh giá), `AIInterpretationService` (tổng hợp nhận định), `ExportService` (xuất JSON & CSV).
   * Áp dụng nguyên lý Đảo ngược phụ thuộc (**Dependency Inversion Principle - DIP**): Tầng ứng dụng chỉ phụ thuộc vào các Abstract Protocols (`IOCREngine`, `IAIClient`, `IDocumentExtractor`) tại `src/application/interfaces/`, không phụ thuộc trực tiếp vào bất kỳ thư viện OCR hay API client cụ thể nào.

3. **Infrastructure Layer (`src/infrastructure/`) - Hạ tầng & Thư viện ngoài**:
   * Triển khai chi tiết các Adapter kỹ thuật: `PaddleOCREngine` (tăng tốc GPU), `PDFExtractor` (PyMuPDF & pdfplumber), `OpenRouterClient` (HTTP streaming & Resilient JSON Repair).
   * `ServiceFactory` ([factories.py](file:///c:/Users/admin/Desktop/A_Ky1_Nam4/Cong_nghe_tai_chinh/Financial_health_system/src/infrastructure/factories.py)): Đóng vai trò bộ cung cấp phụ thuộc (Dependency Injection container) với cơ chế Lazy Import tối ưu thời gian khởi động ứng dụng.

4. **Presentation Layer (`src/presentation/`) - Giao diện người dùng**:
   * Phân chia module rõ ràng: Controller (`controller.py`), Quản lý Session State (`state.py`), Định dạng số liệu (`formatters.py`), Hệ thống giao diện trực quan Glassmorphism (`styles.py`), và các khối UI độc lập tại `components/`.
   * **Thin Entry Point**: File [app.py](file:///c:/Users/admin/Desktop/A_Ky1_Nam4/Cong_nghe_tai_chinh/Financial_health_system/app.py) chỉ đóng vai trò bootstrap khởi chạy (<35 dòng), ủy quyền toàn bộ điều hướng cho tầng Presentation.

---

## 🧩 Hướng Dẫn Mở Rộng Hệ Thống (Extension Guide)

### 1. Thêm Chỉ Số Tài Chính Mới
1. Khai báo key và metadata trong catalogue `RATIO_METADATA` tại `src/domain/ratios/engine.py`.
2. Bổ sung phương thức tính toán trả về `RatioResult` (sử dụng `Decimal`).
3. Đăng ký ngưỡng đánh giá an toàn / rủi ro tại `src/domain/assessment/thresholds.py`.

### 2. Thay Thế / Bổ Sung Nhà Cung Cấp AI (LLM Provider)
1. Tạo class triển khai adapter mới thỏa mãn interface `IAIClient` ([src/application/interfaces/ai.py](file:///c:/Users/admin/Desktop/A_Ky1_Nam4/Cong_nghe_tai_chinh/Financial_health_system/src/application/interfaces/ai.py)).
2. Đăng ký khởi tạo trong `ServiceFactory.create_ai_client()` tại `src/infrastructure/factories.py`.

### 3. Tích Hợp Động Cơ OCR Mới (Ví dụ: EasyOCR, Tesseract, v.v.)
1. Tạo adapter triển khai interface `IOCREngine` ([src/application/interfaces/ocr.py](file:///c:/Users/admin/Desktop/A_Ky1_Nam4/Cong_nghe_tai_chinh/Financial_health_system/src/application/interfaces/ocr.py)).
2. Đăng ký tại `ServiceFactory.create_ocr_engine()` tại `src/infrastructure/factories.py`.

---

## 🧪 Kiểm Thử Tự Động (Automated Testing)

Dự án duy trì bộ kiểm thử tự động toàn diện với **202 unit tests**, bảo đảm độ tin cậy từ tầng OCR, chuẩn hóa dữ liệu, số học `Decimal`, thuật toán khôi phục JSON cho AI đến tầng tích hợp giao diện.

Chạy toàn bộ test suite bằng `pytest`:

```powershell
pytest tests/unit/
```

Kết quả kiểm thử đạt chuẩn 100%:
```text
================= 202 passed, 2 warnings in ~65s =================
```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm

Hệ thống được phát triển phục vụ mục đích nghiên cứu, học thuật và hỗ trợ tra cứu trong lĩnh vực Công nghệ Tài chính (FinTech). Các kết quả tính toán và nhận định do Trí tuệ nhân tạo (AI) sinh ra **không cấu thành lời khuyên đầu tư chứng khoán, khuyến nghị mua bán tài sản hay quyết định thẩm định/phê duyệt tín dụng**. Người dùng tự chịu trách nhiệm đối với các quyết định kinh doanh và tài chính thực tế.
