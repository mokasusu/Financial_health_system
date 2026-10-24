# Thiết Kế Chi Tiết: Nâng Cấp Độ Chính Xác Nhận Diện Chỉ Tiêu BCTC (OCR Text Quality Enhancement)

## 1. Tóm Tắt Mục Tiêu & Yêu Cầu (Understanding Summary)
* **Vấn đề cần giải quyết:** Mô hình OCR nhận diện văn bản tiếng Việt trên các báo cáo tài chính scan/ảnh thường bị thiếu dấu, nuốt ký tự hoặc sai sót chữ cái (ví dụ: `Tài sn ngn hn`, `Li nhun thun t hot đng kinh doanh`, `VN CH S HU`,...). Điều này gây khó nhìn trên bảng dữ liệu và làm giảm tỷ lệ tự động nhận diện chỉ tiêu chuẩn.
* **Giải pháp tổng thể:** Triển khai **Kiến trúc Pipeline Hai Lớp (Two-Stage Pipeline)**:
  1. *Lớp 1 (Tiền xử lý ảnh thích ứng):* Nâng độ phân giải `ocr_dpi` từ 150 lên 200 DPI, bổ sung CLAHE cân bằng sáng cục bộ và bộ lọc làm nét Unsharp Masking giúp làm rõ nét các dấu thanh tiếng Việt trước khi vào PaddleOCR.
  2. *Lớp 2 (Bộ sửa lỗi chính tả & Chuẩn hóa từ điển kế toán):* Xây dựng `FinancialLexiconCorrector` dựa trên danh mục 60 chỉ tiêu chuẩn của Bảng cân đối kế toán & Báo cáo kết quả kinh doanh (TT200 / TT43 / VAS), sử dụng so khớp mờ (Fuzzy String Matching / Levenshtein Distance) để tự động sửa các lỗi chính tả OCR về tên chuẩn tiếng Việt có dấu đầy đủ.
* **Hiển thị giao diện:** Tên chỉ tiêu chuẩn hóa được điền trực tiếp lên bảng tương tác `st.data_editor`, cho phép người dùng click chỉnh sửa nếu có nhu cầu trước khi bấm tính toán 4 chỉ số KPI.
* **Ràng buộc hiệu năng:** Thời gian xử lý đạt mức cân bằng tối ưu **1.5 – 3 giây/trang**, xử lý offline hoàn toàn trên máy cục bộ (CPU/GPU), không phụ thuộc API ngoài.
* **Phạm vi ngoài lề (Non-goals):** Không can thiệp sửa từ vựng các ghi chú tự do dài trong Bản thuyết minh BCTC; không khóa cứng dữ liệu người dùng.

---

## 2. Giả Định (Assumptions)
1. Bộ danh mục chuẩn hóa dựa trên các chỉ tiêu cốt lõi của Thông tư 200/2014/TT-BTC và Thông tư 43/2026/TT-BTC.
2. Nâng DPI lên 200 là điểm tối ưu dung hòa giữa độ sắc nét ký tự và tốc độ inference của PaddleOCR.
3. Khi độ tương đồng ký tự với từ khóa chuẩn vượt ngưỡng tin cậy an toàn, việc tự động sửa nhãn mang lại trải nghiệm chuyên nghiệp cho người dùng.

---

## 3. Nhật Ký Quyết Định (Decision Log)

| Mã Quyết định | Nội dung quyết định | Các phương án xem xét | Lý do lựa chọn |
| :--- | :--- | :--- | :--- |
| **DEC-01** | Phạm vi: Kết hợp Tiền xử lý ảnh nhẹ + Sửa từ vựng bằng Từ điển Kế toán | Chỉ tiền xử lý ảnh / Chỉ sửa text / Kết hợp cả hai / Dùng AI LLM | Đảm bảo vừa nâng chất lượng đọc của OCR, vừa có lưới an toàn sửa chữ tuyệt đối cho thuật ngữ tài chính. |
| **DEC-02** | Giới hạn thời gian xử lý: 1.5 – 3 giây/trang | < 1.5s / 1.5 – 3s / 3 – 6s | Đảm bảo trải nghiệm người dùng trên Streamlit mượt mà, không bị nghẽn khi tải PDF nhiều trang. |
| **DEC-03** | Phạm vi từ điển: Tập trung chuẩn hóa 60 chỉ tiêu chính CĐKT & KQKD | 60 chỉ tiêu chính vs Toàn bộ từ vựng mở rộng | Tránh sửa nhầm các diễn giải chi tiết đặc thù của doanh nghiệp, tập trung 100% vào các chỉ tiêu cốt lõi để tính tỷ số. |
| **DEC-04** | Trình bày UI: Hiển thị trực tiếp Tên chuẩn hóa tiếng Việt trên `st.data_editor` | Ghi đè nhãn chuẩn vs Hiển thị song song nhãn gốc | Bảng số liệu sạch đẹp, chuyên nghiệp, người dùng vẫn có thể click sửa nếu muốn. |
| **DEC-05** | Ngưỡng tương đồng mờ: 60% khi có mã số, 75% khi không có mã số | Cố định 80% / Phân tầng theo mã số | Có mã số giúp thu hẹp ngữ cảnh nên chỉ cần 60% tương đồng; không có mã số cần 75% để chống sửa nhầm. |
| **DEC-06** | Cơ chế an toàn (Safety Guard): Chặn sửa nếu vi phạm antipatterns cốt lõi | So khớp tự do vs So khớp kèm luật loại trừ | Bảo vệ các chỉ tiêu dễ nhầm lẫn như ngắn hạn/dài hạn, phải thu/phải trả. |

---

## 4. Đặc Tả Thiết Kế Chi Tiết (Detailed Architecture & Components)

### 4.1. Tiền xử lý ảnh nâng cao (`src/ocr/image_preprocessor.py` & `src/ocr/pdf_extractor.py`)
* `ocr_dpi` trong `PDFExtractor` được đặt mặc định là `200`.
* Bổ sung phương thức `enhance_document_text(img: np.ndarray) -> np.ndarray`:
  - Chuyển ảnh sang kênh độ sáng `L` trong không gian LAB.
  - Áp dụng CLAHE (`clipLimit=2.0`, `tileGridSize=(8, 8)`).
  - Áp dụng Unsharp Mask: $I_{\text{sharp}} = 1.3 \times I_{\text{orig}} - 0.3 \times \text{GaussianBlur}(I, \sigma=2.0)$.

### 4.2. Bộ Chuẩn hóa Từ điển Kế toán (`FinancialLexiconCorrector` trong `src/data/parser.py`)
* Xây dựng từ điển `STANDARD_FINANCIAL_LEXICON` bao gồm:
  - Bảng cân đối kế toán: Mã 100, 110, 111, 112, 120, 121, 122, 123, 130, 131, 132, 135, 136, 140, 141, 142, 150, 200, 210, 220, 221, 222, 223, 227, 228, 229, 250, 260, 270, 280, 300, 310, 311, 312, 320, 330, 338, 400, 411, 412, 420, 440,...
  - Báo cáo kết quả kinh doanh: Mã 01, 02, 10, 11, 20, 21, 22, 23, 24, 25, 26, 30, 31, 32, 40, 50, 51, 52, 60,...
* Phương thức `correct_label(raw_label: str, item_code: Optional[str], context: str) -> Tuple[str, bool]`:
  - Làm sạch dấu câu, biểu thức công thức.
  - Tính điểm tương đồng mờ (`difflib.SequenceMatcher`).
  - Kiểm tra các antipatterns (`dai han` vs `ngan han`, `phai thu` vs `phai tra`, `khac`).
  - Trả về `(standard_label, is_corrected)` nếu vượt ngưỡng tin cậy.

### 4.3. Tích hợp Bảng dữ liệu Streamlit (`src/ui/components.py`)
* Khi tạo bảng DataFrame cho `st.data_editor` thông qua `build_statement_dataframes()`:
  - Cột `"Tên chỉ tiêu"` được hiển thị bằng `normalized_label` (hoặc `standard_label` chuẩn tiếng Việt).
  - Người dùng có thể click đúp sửa số liệu hoặc tên chỉ tiêu trực tiếp trên bảng.

---

## 5. Chiến Lược Kiểm Thử (Testing Strategy)
1. **Unit test sửa lỗi từ điển:** Tạo các test case kiểm tra chuỗi OCR sai dấu điển hình:
   - `"Tài sn ngn hn"` $\rightarrow$ `"Tài sản ngắn hạn"`
   - `"Li nhun thun t hot đng kinh doanh"` $\rightarrow$ `"Lợi nhuận thuần từ hoạt động kinh doanh"`
   - `"Doanh thu hot đng tài chính"` $\rightarrow$ `"Doanh thu hoạt động tài chính"`
   - `"VN CH S HU"` $\rightarrow$ `"Vốn chủ sở hữu"`
2. **Unit test chống sửa nhầm (Anti-false positive):** Kiểm tra các trường hợp vi phạm antipattern không bị sửa sai.
3. **Regression Test:** Đảm bảo toàn bộ 167 unit tests hiện có tiếp tục vượt qua 100%.
