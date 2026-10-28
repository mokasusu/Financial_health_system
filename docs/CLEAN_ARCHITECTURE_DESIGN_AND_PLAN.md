# Kế Hoạch & Thiết Kế Kiến Trúc: Tái Cấu Trúc Toàn Diện Theo Clean Architecture
### Hệ Thống Trích Xuất BCTC & Đánh Giá Sức Khỏe Doanh Nghiệp (Circular 200 / TT200)

---

## 1. Tóm Tắt Mục Tiêu & Nhận Thức (Understanding Summary)
* **Những gì sẽ được xây dựng**: Tái cấu trúc toàn diện mã nguồn dự án sang mô hình **Clean Architecture 4 tầng chuẩn mực** (`domain`, `application`, `infrastructure`, `presentation`), loại bỏ hoàn toàn các "God files" (`parser.py` ~1.500 dòng, `assessment.py` ~1.000 dòng, `components.py` ~1.000 dòng, và `app.py` ~600 dòng).
* **Lý do tồn tại**: Giúp hệ thống dễ bảo trì, giải quyết nợ kỹ thuật, chia nhỏ trách nhiệm theo đúng nguyên lý Đơn trách nhiệm (SRP), và mở ra khả năng mở rộng cắm rút (Plug & Play) cho các chuẩn mực kế toán mới (TT133, IFRS) hoặc giao diện mới (FastAPI REST backend, CLI) trong tương lai.
* **Đối tượng phục vụ**: Nhà phát triển duy trì hệ thống, chuyên viên phân tích tài chính sử dụng Dashboard, và các client/service mở rộng sau này.
* **Chiến lược kiểm thử & Tương thích**: Thực hiện **Clean Break** — cập nhật đường dẫn import sạch sẽ, chuẩn xác trực tiếp trong toàn bộ **202 unit tests** và mã nguồn, loại bỏ hoàn toàn các file alias/re-export cũ. Toàn bộ 202 unit tests phải vượt qua 100% sau khi refactor.
* **Ràng buộc phi chức năng cốt lõi**:
  * **Zero File Retention**: Tuyệt đối không lưu tệp tải lên ra đĩa cứng, duy trì xử lý hoàn toàn trên RAM (`io.BytesIO`).
  * **Exact Decimal Arithmetic**: Toàn bộ tính toán tỷ số tài chính tiếp tục sử dụng kiểu `Decimal` của Python để triệt tiêu sai số làm tròn.
  * **DI thuần Python**: Sử dụng cơ chế Manual Dependency Injection / Factory Pattern nhẹ nhàng, không bổ sung thư viện container nặng nề bên thứ ba.
* **Mục tiêu ngoài phạm vi (Explicit Non-Goals)**:
  * Không thay đổi logic nghiệp vụ kế toán (giữ nguyên 4 đẳng thức cân đối TT200, 14 công thức tỷ số tài chính, thuật toán Fuzzy Lexicon Matching).
  * Không viết lại giao diện UI từ đầu (chỉ tách nhỏ và tổ chức lại các Streamlit components, CSS styles và view controllers).
  * Không can thiệp vào mô hình AI OpenRouter hay thuật toán Resilient JSON Repair.

---

## 2. Các Giả Định Được Thiết Lập (Assumptions)
1. Cấu trúc thư mục mới nằm hoàn toàn trong `src/`:
   * `src/domain/`: Thực thể nghiệp vụ, Value Objects, Luật kế toán TT200, Từ điển đối chiếu, Công thức tỷ số `Decimal`.
   * `src/application/`: Orchestrator use cases/services (`AnalysisPipelineService`, `StatementParsingService`, `FinancialAnalysisService`, `AIInterpretationService`, `ExportService`).
   * `src/infrastructure/`: Bộ chuyển đổi công nghệ bên ngoài (PaddleOCR GPU/CPU, OpenCV Preprocessor, PyMuPDF/pdfplumber, OpenRouter Client).
   * `src/presentation/`: Streamlit Dashboard, Controllers, Components tách nhỏ, Design System/Styles.
2. File `app.py` ở root chỉ đóng vai trò là điểm kích hoạt (entry point) mỏng nhẹ của Streamlit (<30 dòng), toàn bộ luồng điều phối nghiệp vụ (`execute_pipeline`, quản lý session state) sẽ được chuyển giao cho tầng Application & Presentation Controllers.
3. Không làm suy giảm hiệu năng xử lý (thời gian chạy test suite ~60-70s và tốc độ OCR/AI giữ nguyên).

---

## 3. Nhật Ký Quyết Định (Decision Log)

| Quyết Định | Nội Dung Quyết Định | Các Phương Án Đã Cân Nhắc | Lý Do Lựa Chọn |
| :--- | :--- | :--- | :--- |
| **D1: Mục tiêu** | Tái cấu trúc toàn diện 4 tầng theo Clean Architecture, xóa bỏ các "God files" (`parser.py`, `assessment.py`, `components.py`, `app.py`). | Refactor cục bộ tầng data; Mở rộng API; Plugin pattern. | Giải quyết triệt để nợ kỹ thuật (tech debt), phân tách rõ ràng trách nhiệm theo SRP. |
| **D2: Tương thích** | Clean Break: Cập nhật trực tiếp đường dẫn import mới trong mã nguồn và toàn bộ 202 unit tests. | Giữ alias qua `__init__.py`; Phased migration. | Giữ codebase tinh gọn, không để lại code thừa (dead code) hay gánh nặng duy trì hai hệ thống import. |
| **D3: Kiến trúc** | Clean Architecture 4 tầng thực dụng (Domain, Application, Infrastructure, Presentation). | Strict Hexagonal (Ports & Adapters); Modular In-Place. | Đảm bảo tính độc lập của nghiệp vụ kế toán, mở rộng cao mà không rườm rà (tuân thủ YAGNI). |
| **D4: Dependency Injection** | Manual Dependency Injection & Service Factory thuần Python. | Framework DI ngoài (`dependency-injector`); Service Locator tĩnh. | Nhẹ, dễ debug, không thêm dependency ngoài, tương thích tự nhiên với Streamlit và Pytest. |

---

## 4. Thiết Kế Kiến Trúc Chi Tiết (Detailed Architecture Design)

### 4.1. Sơ Đồ Cấu Trúc Thư Mục Mới
```text
src/
├── domain/                                 # TẦNG 1: NGHIỆP VỤ LÕI (Không phụ thuộc I/O, UI, Third-party)
│   ├── __init__.py
│   ├── models/                             # Pydantic Schemas & DTOs
│   │   ├── __init__.py
│   │   ├── bctc.py                         # FinancialReport, BalanceSheet, IncomeStatement, CashFlowStatement
│   │   ├── line_item.py                    # LineItem, MappingMethod, MappingStatus
│   │   ├── ratios.py                       # RatioItem, FinancialRatios, RatioCategory
│   │   ├── assessment.py                   # AssessmentStatus, WarningSeverity, KPIAssessment
│   │   ├── ai.py                           # CoreFinancialKPIs, AICommentary, ModelInfo
│   │   └── ocr.py                          # OCRPageData, OCRWord, DocumentExtractionResult
│   ├── accounting/                         # Nghiệp vụ kế toán Thông tư 200/2014/TT-BTC
│   │   ├── __init__.py
│   │   ├── canonical.py                    # BALANCE_SHEET_CANONICAL, INCOME_STATEMENT_CANONICAL
│   │   ├── lexicon.py                      # FinancialLexiconCorrector (Fuzzy OCR matching)
│   │   ├── metadata_extractor.py           # Đơn vị tiền tệ, Niên độ, Ngày báo cáo, Blacklist kiểm toán
│   │   ├── normalizer.py                   # AccountingNumberNormalizer (Số học kế toán VN)
│   │   └── validator.py                    # AccountingValidator (4 đẳng thức cân đối kế toán TT200)
│   ├── ratios/                             # Động cơ tính toán 14 tỷ số tài chính
│   │   ├── __init__.py
│   │   └── engine.py                       # RatioEngine (Toàn bộ phép tính bằng Decimal)
│   └── assessment/                         # Đánh giá sức khỏe tài chính & phân loại rủi ro
│       ├── __init__.py
│       ├── thresholds.py                   # Bảng ngưỡng tham chiếu ngành & thị trường VN
│       ├── evaluator.py                    # Đánh giá chi tiết từng chỉ số & 4 core KPIs
│       └── scoring.py                      # Thuật toán tính điểm sức khỏe tài chính 0-100
│
├── application/                            # TẦNG 2: ĐIỀU PHỐI USE CASES & SERVICES
│   ├── __init__.py
│   ├── interfaces/                         # Khai báo Abstract Protocols
│   │   ├── __init__.py
│   │   ├── ocr.py                          # Protocol IOCREngine
│   │   ├── ai.py                           # Protocol IAIClient
│   │   └── pdf.py                          # Protocol IDocumentExtractor
│   └── services/                           # Use Case Services
│       ├── __init__.py
│       ├── pipeline_service.py             # AnalysisPipelineService (trước đây nằm trong app.py)
│       ├── parsing_service.py              # FinancialStatementParser (tách từ parser.py)
│       ├── financial_service.py            # FinancialAnalysisService (kết nối Ratio + Assessment)
│       ├── ai_service.py                   # AIInterpretationService (Prompting + JSON Repair)
│       └── export_service.py               # ExportService (CSV UTF-8 BOM, JSON export)
│
├── infrastructure/                         # TẦNG 3: CÔNG NGHỆ BÊN NGOÀI & I/O
│   ├── __init__.py
│   ├── ocr/                                # OCR Engine
│   │   ├── __init__.py
│   │   ├── paddle_engine.py                # PaddleOCREngine (CUDA/CPU)
│   │   └── preprocessor.py                 # OpenCV ImagePreprocessor (deskew, contrast)
│   ├── pdf/                                # PDF Extractor
│   │   ├── __init__.py
│   │   └── extractor.py                    # PDFExtractor (PyMuPDF, pdfplumber routing)
│   ├── ai/                                 # OpenRouter AI Client
│   │   ├── __init__.py
│   │   ├── client.py                       # OpenRouterClient (HTTP, hot-reloading env)
│   │   └── json_repair.py                  # Resilient JSON Repair Engine
│   └── factories.py                        # ServiceFactory (Wiring DI cho PipelineService)
│
└── presentation/                           # TẦNG 4: GIAO DIỆN NGƯỜI DÙNG (STREAMLIT)
    ├── __init__.py
    └── streamlit/
        ├── __init__.py
        ├── state.py                        # Quản lý Streamlit Session State
        ├── styles.py                       # CSS Design System & Theme
        ├── formatters.py                   # Format số liệu & hiển thị nhãn ngày tháng
        ├── components/                     # Components chia nhỏ theo chức năng
        │   ├── __init__.py
        │   ├── kpi_cards.py                # 4 thẻ chỉ số tài chính cốt lõi
        │   ├── statement_tables.py         # Bảng số liệu B01-DN & B02-DN
        │   ├── balance_checks.py           # Khối kiểm định 4 đẳng thức kế toán
        │   ├── ai_commentary.py            # Khối nhận định AI chuyên sâu
        │   └── export_panel.py             # Bộ công cụ xuất báo cáo CSV/JSON
        └── controller.py                   # Streamlit Controller (Nhận upload, gọi PipelineService)

app.py                                      # Điểm kích hoạt Streamlit mỏng gọn (<30 dòng)
```

---

## 5. Kế Hoạch Triển Khai 5 Giai Đoạn (Implementation Roadmap)

### Giai đoạn 1: Xây Dựng Tầng Domain & Phân Rã God Files
1. Tạo cấu trúc thư mục `src/domain/`.
2. Di chuyển và chuẩn hóa `src/domain/models/`:
   - `bctc.py`, `line_item.py` (từ `src/data/schema.py`).
   - `ratios.py` (từ `src/financial/assessment_models.py`).
   - `ai.py` (từ `src/financial/ai_models.py`).
   - `ocr.py` (từ `src/ocr/models.py`).
3. Phân tách `src/data/parser.py` sang `src/domain/accounting/`:
   - `canonical.py`: Chứa `BALANCE_SHEET_CANONICAL`, `INCOME_STATEMENT_CANONICAL`.
   - `lexicon.py`: Chứa `FinancialLexiconCorrector`.
   - `metadata_extractor.py`: Chứa logic phát hiện ngày tháng, năm tài chính, đơn vị tiền tệ, blacklist kiểm toán.
   - `normalizer.py`: Di chuyển `AccountingNumberNormalizer`.
   - `validator.py`: Di chuyển `AccountingValidator`.
4. Di chuyển `ratios.py` sang `src/domain/ratios/engine.py`.
5. Phân tách `src/financial/assessment.py` sang `src/domain/assessment/`:
   - `thresholds.py`: Bảng ngưỡng thị trường.
   - `evaluator.py`: Đánh giá rủi ro chỉ số.
   - `scoring.py`: Tính điểm sức khỏe tài chính.

### Giai đoạn 2: Xây Dựng Tầng Infrastructure & Factory
1. Tạo thư mục `src/infrastructure/`.
2. Di chuyển `src/ocr/paddle_engine.py` và `image_preprocessor.py` sang `infrastructure/ocr/`.
3. Di chuyển `src/ocr/pdf_extractor.py` sang `infrastructure/pdf/`.
4. Di chuyển `src/financial/openrouter_client.py` và module JSON repair sang `infrastructure/ai/`.
5. Tạo `src/infrastructure/factories.py` với `ServiceFactory.create_pipeline_service()`.

### Giai đoạn 3: Xây Dựng Tầng Application (Use Cases)
1. Tạo thư mục `src/application/`.
2. Định nghĩa các interface/protocols trong `application/interfaces/`.
3. Tạo các use case services:
   - `parsing_service.py`: Tách phần còn lại của `FinancialStatementParser`.
   - `financial_service.py`: Điều phối tính tỷ số và đánh giá sức khỏe.
   - `ai_service.py`: Điều phối tạo prompt AI và gọi OpenRouter.
   - `export_service.py`: Di chuyển từ `src/ui/export.py`.
   - `pipeline_service.py`: Trích xuất `execute_pipeline` từ `app.py`.

### Giai đoạn 4: Xây Dựng Tầng Presentation & Tối Giản `app.py`
1. Tạo thư mục `src/presentation/streamlit/`.
2. Phân rã `src/ui/components.py` thành:
   - `components/kpi_cards.py`
   - `components/statement_tables.py`
   - `components/balance_checks.py`
   - `components/ai_commentary.py`
   - `components/export_panel.py`
3. Di chuyển `styles.py`, `formatters.py` và xây dựng `state.py`.
4. Viết `controller.py` xử lý luồng giao diện Streamlit.
5. Thu gọn `app.py` về dưới 30 dòng, chỉ khởi chạy `controller.run_app()`.

### Giai đoạn 5: Clean Break Import trong 202 Unit Tests & Dọn Dẹp
1. Cập nhật các đường dẫn `import` trong toàn bộ 20 file test ở `tests/unit/`:
   - `test_ai_interpreter.py`
   - `test_assessment.py`
   - `test_date_and_header_extraction.py`
   - `test_financial_lexicon_corrector.py`
   - `test_image_preprocessor.py`
   - `test_normalizer.py`
   - `test_ocr_models.py`
   - `test_openrouter_client.py`
   - `test_paddle_engine.py`
   - `test_paddle_pdf_integration.py`
   - `test_parser.py`
   - `test_pdf_extractor.py`
   - `test_ratios.py`
   - `test_row_alignment_and_mapping.py`
   - `test_ui_export_and_integration.py`
   - `test_ui_formatters.py`
   - `test_ui_interactive_editing.py`
   - `test_validator.py`
   - `test_vinamilk_extraction.py`
2. Xóa các thư mục cũ đã được thay thế: `src/data/`, `src/financial/`, `src/ocr/`, `src/ui/`.
3. Chạy `.\.venv\Scripts\pytest tests/unit/` đảm bảo **202/202 unit tests PASS 100%**.
4. Kiểm tra smoke test khởi chạy giao diện Streamlit.
