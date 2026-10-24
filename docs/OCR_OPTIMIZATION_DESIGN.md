# KẾ HOẠCH THIẾT KẾ CẢI TIẾN PIPELINE OCR CHO TÀI LIỆU BCTC SCAN
**Dự án:** Hệ thống Đánh giá Sức khỏe Tài chính Doanh nghiệp (Financial Health System)  
**Ngày lập:** 24/10/2026  
**Trạng thái:** Đã chốt phương án thiết kế (Design Approved)  

---

## 1. TỔNG QUAN & NGUYÊN NHÂN HIỆN TRẠNG (Root Cause Analysis)

### 1.1. Hiện trạng
Khi người dùng tải lên 1 file PDF báo cáo tài chính dạng scan (hoặc trang scan nhúng trong PDF), thời gian xử lý hiện tại mất **10 – 20 phút cho 1 trang duy nhất**.

### 1.2. Kết quả Chẩn đoán Kỹ thuật
1. **Phần cứng thực tế:** Máy tính sở hữu card đồ họa rời mạnh mẽ **`NVIDIA GeForce RTX 3050 Laptop GPU`** (4GB VRAM, Driver 592.27, hỗ trợ CUDA 13.1/12.x).
2. **Nguyên nhân phần mềm:**
   * Môi trường ảo `.venv` hiện tại đang cài đặt gói `paddlepaddle==3.3.1` (phiên bản **CPU thuần**). Hàm `paddle.device.is_compiled_with_cuda()` trả về `False`.
   * Hệ thống tự động fallback về `device='cpu'`.
   * **Hiệu ứng Vòng lặp N+1 (`ocr_with_layout`):** PP-Structure chia trang scan thành 40 - 80 vùng layout nhỏ, sau đó gọi lại `ocr_image()` cho từng ô nhỏ trên CPU. Mỗi ô mất 3-6s $\rightarrow$ tổng cộng 150 - 500s (8 - 15 phút).
   * **Mô hình quá nặng:** Đang dùng bản Large/Server (`PP-DocLayout_plus-L` và `PP-OCRv5_server_det`).
   * **Tập lệnh MKLDNN/oneDNN bị ép tắt:** Khiến phép toán số học CPU không được vector hóa AVX2.

---

## 2. THẨU HIỂU MỤC TIÊU & PHẠM VI (Understanding Lock)

* **Mục tiêu cốt lõi:**
  1. Kích hoạt GPU NVIDIA RTX 3050 (cài đặt `paddlepaddle-gpu` CUDA).
  2. Tái cấu trúc pipeline theo **Phương án 1 (Hybrid Single-Pass OCR + Selective Deep Table Engine)**.
  3. Xóa bỏ triệt để vòng lặp crop N+1, đưa thời gian xử lý xuống **2.5 – 4.5 giây / trang** (nhanh hơn hiện tại gấp 100 lần).
  4. Bảo toàn nguyên vẹn 4-5 cột dữ liệu bảng BCTC TT200 (*Tên chỉ tiêu, Mã số, Thuyết minh, Số cuối năm, Số đầu năm*).
  5. Đảm bảo an toàn bộ nhớ VRAM ($\le 2.5$GB trên mức trần 4GB) và cơ chế tự động Fallback sang CPU Fast-mode.
* **Mục tiêu loại trừ (Non-goals):**
  * Không thay đổi nghiệp vụ tính 14 chỉ số tài chính, phương trình kế toán TT200 và phần diễn giải OpenRouter AI.
  * Giữ nguyên giao diện người dùng và định dạng `DocumentExtractionResult` để không gây ảnh hưởng đến `FinancialStatementParser`.

---

## 3. CÁC GIẢ ĐỊNH & RÀNG BUỘC (Assumptions & Constraints)

1. **Giả định phần cứng:** Windows 11 64-bit, NVIDIA Driver 592.27, CUDA Driver 13.1 (tương thích ngược CUDA Toolkit 11.8 / 12.x).
2. **Giả định tài liệu:** Đối với PDF vector (Route A - Native text), giữ nguyên cơ chế bóc tách qua PyMuPDF (< 0.1s), không chạy qua OCR.
3. **Ràng buộc VRAM:** Không được để tiến trình chiếm dụng vượt quá 3.0GB VRAM để tránh hiện tượng Windows Out-Of-Memory (OOM).

---

## 4. NHẬT KÝ QUYẾT ĐỊNH (Decision Log)

| Quyết định | Phương án thay thế đã xét | Lý do lựa chọn |
| :--- | :--- | :--- |
| **Q1. Cải tiến kết hợp GPU + Tái cấu trúc Code** | Chỉ tối ưu CPU hoặc chỉ cài GPU giữ code cũ | Đạt tốc độ cực đại (< 3s/trang) và triệt tiêu tận gốc lỗi vòng lặp $N+1$ |
| **Q2. Chọn Phương án 1 (Kiến trúc Hai Tầng)** | Phương án 2 (PP-Structure nặng) hoặc Phương án 3 (Heuristic thuần) | Cân bằng hoàn hảo giữa tốc độ vượt trội (2–4s) và độ chính xác bảng biểu TT200 |
| **Q3. Quản lý VRAM động ($\le 2.5$GB) + Fallback CPU** | Ép buộc 100% GPU hoặc bắt người dùng chọn thủ công | Đảm bảo an toàn bộ nhớ cho RTX 3050 4GB và ứng dụng không bao giờ bị dừng đột ngột |

---

## 5. THIẾT KẾ KIẾN TRÚC CHI TIẾT (Detailed Architecture)

```
                       [ Upload PDF / Scan Image ]
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ 1. Device & VRAM Manager                               │
       │    - Kiểm tra CUDA RTX 3050                            │
       │    - Giới hạn cấp phát VRAM tối đa 2.5GB               │
       └────────────────────────────┬───────────────────────────┘
                                    │
             ┌──────────────────────┴─────────────────────┐
             ▼ (GPU sẵn sàng)                             ▼ (Thiếu VRAM / Không GPU)
┌────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ 2. GPU Accelerated Pipeline            │   │ 3. CPU Fast-Mode Fallback Pipeline     │
│                                        │   │                                        │
│  [Tầng 1: Single-pass OCR (~1.0s)]     │   │  • Single-pass OCR nhẹ trên CPU (~8s)  │
│  • Chạy toàn trang 1 lần duy nhất      │   │  • Chạy 1 lần duy nhất cho toàn trang  │
│  • Trích xuất Text + Bounding Boxes    │   │  • Heuristic reading order clustering  │
│                                        │   └───────────────────┬────────────────────┘
│  [Tầng 2: Selective Table Engine]      │                       │
│  • SLANet chỉ trích xuất lưới ô bảng   │                       │
│  • Khớp nối không gian (Spatial IoU)   │                       │
│    vào các ô mà KHÔNG re-run OCR       │                       │
└───────────────────┬────────────────────┘                       │
                    │                                            │
                    └────────────────────┬───────────────────────┘
                                         │
                                         ▼
       ┌────────────────────────────────────────────────────────┐
       │ 4. Output Normalizer & Parser Handoff                  │
       │    - Chuẩn hóa thành chuỗi Tab-separated (`\t`)        │
       │    - Trả về DocumentExtractionResult tương thích 100%  │
       │    - Ghi log thời gian & Badge chẩn đoán phần cứng     │
       └────────────────────────────────────────────────────────┘
```

### 5.1. Module 1: `DeviceManager` & `VRAMManager`
* Quản lý trạng thái thiết bị:
  ```python
  class DeviceManager:
      @classmethod
      def get_optimal_device(cls) -> str:
          # Kiểm tra CUDA và device_count
          if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
              return "gpu:0"
          return "cpu"
          
      @classmethod
      def release_memory(cls):
          if paddle.device.is_compiled_with_cuda():
              paddle.device.cuda.empty_cache()
          gc.collect()
  ```

### 5.2. Module 2: `SinglePassOCREngine` (Tầng 1)
* Nhận dạng ảnh toàn trang trong 1 lần suy luận duy nhất (Single-pass):
  * Input: Ảnh mảng BGR $(H, W, 3)$
  * Output: Danh sách các khối văn bản `[ { "text": str, "bbox": [x1, y1, x2, y2], "confidence": float } ]`
  * Thời gian thực thi: **~0.8 – 1.2 giây** trên RTX 3050.

### 5.3. Module 3: `SelectiveTableReconstructor` (Tầng 2)
* Khi phát hiện bảng BCTC:
  1. Chỉ gọi mô hình cấu trúc bảng `SLANet` trên vùng bảng để lấy danh sách các ô (Cells).
  2. Sử dụng thuật toán so khớp tâm tọa độ (Point-in-Polygon / Center-in-Bbox) để đưa từ ngữ đã nhận diện từ Tầng 1 vào từng ô tương ứng.
  3. Ghép nối thành các dòng văn bản ngăn cách bằng tab (`\t`) cho các cột: `Chỉ tiêu \t Mã số \t Thuyết minh \t Số cuối năm \t Số đầu năm`.
  4. Thời gian thực thi: **~1.5 – 2.0 giây**.

---

## 6. CHIẾN LƯỢC QUẢN LÝ LỖI & PHÒNG VỆ (Resilience Strategy)

1. **Circuit Breaker khi OOM:** Bọc khối suy luận GPU trong `try...except (paddle.framework.core.EnforceNotMet, RuntimeError)`. Nếu gặp lỗi tràn bộ nhớ, ngay lập tức giải phóng cache GPU và gọi hàm `cpu_fallback_extract()`.
2. **Khử xoay tự động:** Kích hoạt `use_angle_cls=True` với mô hình xoay nhẹ `ch_ppocr_mobile_v2.0_cls` để tự động dựng thẳng các trang scan bị chụp nghiêng.
3. **Bảo toàn số âm kế toán:** Giữ nguyên các ký tự đóng mở ngoặc đơn `(15.000.000)` hoặc dấu trừ `-15.000.000`.

---

## 7. KẾ HOẠCH TRIỂN KHAI THEO GIAI ĐOẠN (Implementation Roadmap)

* **Giai đoạn 1: Môi trường & Thư viện GPU (CUDA Setup)**
  * Cài đặt `paddlepaddle-gpu` (phiên bản build tương thích CUDA 11.8/12.x trên Windows).
  * Kiểm tra và xác nhận `paddle.device.is_compiled_with_cuda() == True`.
* **Giai đoạn 2: Tái cấu trúc `PaddleOCREngine` (Single-pass + Spatial Table)**
  * Viết lại hàm `ocr_with_layout()` trong `src/ocr/paddle_engine.py`.
  * Thay thế vòng lặp crop cũ bằng bộ so khớp không gian (Spatial IoU Matcher).
  * Tích hợp dọn dẹp bộ nhớ GPU tự động `release_memory()`.
* **Giai đoạn 3: Tối ưu hóa Tiền xử lý & Cấu hình DPI trong `pdf_extractor.py`**
  * Đặt mức DPI chuẩn 150 cho trang scan để đạt tỉ lệ vàng giữa tốc độ và độ sắc nét.
  * Tắt các thuật toán khử nhiễu phi tuyến nặng khi ảnh đã đủ độ tương phản.
* **Giai đoạn 4: Kiểm thử Benchmark & Cập nhật UI Streamlit**
  * Chạy lại `scripts/benchmark_ocr.py` trên 5 bộ dữ liệu kiểm chuẩn.
  * Bổ sung Badge hiển thị thiết bị và tốc độ OCR trên Sidebar của `app.py`.

---

## 8. TIÊU CHUẨN NGHIỆM THU (Acceptance Criteria)

| Tiêu chí đánh giá | Hiện trạng cũ | Mục tiêu nghiệm thu mới |
| :--- | :--- | :--- |
| **Thời gian quét 1 trang scan TT200** | **600 – 1200 giây (10–20 phút)** | **$\le 4.5$ giây** |
| **Thiết bị tính toán** | CPU (100% tải, nóng máy) | **GPU (NVIDIA RTX 3050)** |
| **Độ chính xác số liệu BCTC TT200** | Khá | **$\ge 98\%$** |
| **Bộ nhớ VRAM tiêu thụ** | 0 MB (do không dùng) | **$\le 2.5$ GB** (an toàn cho card 4GB) |
| **Trang PDF văn bản số (Native text)** | ~0.05s | **$< 0.1$ giây** (bảo toàn) |
