"""Lớp bao bọc PaddleOCR và PP-Structure cho trích xuất tài liệu tài chính Tiếng Việt.

Cung cấp khả năng nhận dạng ký tự quang học (OCR), phân tích bố cục trang (layout detection),
và cấu trúc bảng biểu kèm cơ chế lọc nhiễu thông minh (loại bỏ con dấu, logo, số trang đơn thuần,
nhưng bảo lưu các tiêu đề chứa siêu dữ liệu tài chính trọng yếu) và gom nhóm văn bản theo dòng đọc tự nhiên.
"""
import gc
import inspect
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Cấu hình đường dẫn DLL Windows cho NVIDIA CUDA runtime nếu cài đặt trong môi trường ảo
if os.name == "nt":
    try:
        import sys
        site_pkg = Path(sys.prefix) / "Lib" / "site-packages"
        nvidia_dir = site_pkg / "nvidia"
        if nvidia_dir.is_dir():
            for bin_dir in nvidia_dir.glob("*/bin"):
                if bin_dir.is_dir():
                    try:
                        os.add_dll_directory(str(bin_dir))
                    except Exception:
                        pass
                    os.environ["PATH"] = str(bin_dir) + os.path.pathsep + os.environ.get("PATH", "")
        paddle_libs = site_pkg / "paddle" / "libs"
        if paddle_libs.is_dir():
            try:
                os.add_dll_directory(str(paddle_libs))
            except Exception:
                pass
            os.environ["PATH"] = str(paddle_libs) + os.path.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

# Thiết lập cờ môi trường PaddlePaddle để ngăn ngừa lỗi oneDNN PIR unsupported attribute
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")

import cv2
import numpy as np
from PIL import Image

from src.domain.models.ocr import LayoutRegion

logger = logging.getLogger(__name__)


class PaddleOCREngineError(Exception):
    """Ngoại lệ phát sinh khi xảy ra lỗi không thể khắc phục trong PaddleOCREngine."""
    pass


# Các loại vùng bị coi là nhiễu trừ khi chứa siêu dữ liệu tài chính quan trọng
EXCLUDED_REGION_TYPES = {"header", "footer", "figure", "seal", "stamp", "logo", "reference", "page_number"}

# Mẫu regex nhận diện siêu dữ liệu tài chính Tiếng Việt quan trọng trong đầu trang/chân trang
FINANCIAL_METADATA_PATTERNS = [
    r"\bvn[dđ]\b",
    r"đ[oồ]ng",
    r"tri[eệ]u",
    r"t[yỷ]",
    r"ngh[iì]n",
    r"đ[oơ]n\s*v[iị]\s*t[ií]nh",
    r"k[yỳ]\s*(?:k[eế]t\s*th[uú]c|k[eế]\s*to[aá]n)",
    r"n[aă]m\s*t[aà]i\s*ch[ií]nh",
    r"ng[aà]y\s*\d{1,2}\s*th[aá]ng\s*\d{1,2}",
    r"qu[yý]\s*[1234]",
    r"b[aả]ng\s*c[aâ]n\s*đ[oố]i",
    r"k[eế]t\s*qu[aả]\s*kinh\s*doanh",
    r"l[uư]u\s*chuy[eể]n\s*ti[eề]n\s*t[eệ]",
    r"thuy[eế]t\s*minh",
    r"t[aà]i\s*s[aả]n",
    r"ngu[oồ]n\s*v[oố]n",
    r"n[oợ]\s*ph[aả]i\s*tr[aả]",
    r"v[oố]n\s*ch[uủ]",
    r"doanh\s*thu",
    r"l[oợ]i\s*nhu[aậ]n",
    r"chi\s*ph[ií]",
    r"gi[aá]\s*v[oố]n",
]

FORM_TITLE_PATTERNS = [
    r"m[aẫ]u\s*s[oố]",
    r"b\s*0[1239]",
    r"tt\s*200",
    r"200/2014",
    r"tt-btc",
]

_FINANCIAL_RE = re.compile("|".join(FINANCIAL_METADATA_PATTERNS), re.IGNORECASE)
_FORM_TITLE_RE = re.compile("|".join(FORM_TITLE_PATTERNS), re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:trang\s*\d+(?:\s*/\s*\d+)?|page\s*\d+(?:\s*(?:of|/)\s*\d+)?|\d+|\s*-\s*\d+\s*-\s*)\s*$",
    re.IGNORECASE,
)
_FINANCIAL_CODE_OR_NUM_RE = re.compile(
    r"\b(?:100|110|120|130|140|150|200|300|400|01|10|20)\b|\d{1,3}(?:\.\d{3})+"
)


# Từ điển lưu trữ các phiên bản động cơ đơn thể (singleton) theo bộ khóa cấu hình
_SHARED_ENGINES: Dict[Tuple[str, bool, bool, bool, bool, int], "PaddleOCREngine"] = {}
_SHARED_PADDLE_ENGINE: Optional["PaddleOCREngine"] = None


def get_shared_paddle_engine(
    use_gpu: bool = True,
    lang: str = "vi",
    use_angle_cls: bool = True,
    enable_layout: bool = True,
    use_table_recognition: bool = False,
    text_det_limit_side_len: int = 960,
    **kwargs: Any,
) -> "PaddleOCREngine":
    """Lấy hoặc tạo một phiên bản singleton PaddleOCREngine duy nhất tương ứng với cấu hình.

    Đảm bảo việc tái sử dụng trọng số mô hình đã nạp trong bộ nhớ, tránh tốn VRAM/RAM khi khởi tạo nhiều lần.

    Args:
        use_gpu (bool): Cho phép tăng tốc phần cứng GPU CUDA nếu khả dụng.
        lang (str): Mã ngôn ngữ mô hình OCR ('vi').
        use_angle_cls (bool): Tự động xoay nhận diện dòng chữ nghiêng 90/180/270 độ.
        enable_layout (bool): Kích hoạt phân tích cấu trúc trang PP-Structure.
        use_table_recognition (bool): Bật nhận diện ô bảng chuyên sâu.
        text_det_limit_side_len (int): Giới hạn kích thước cạnh ảnh cho phát hiện văn bản.
        **kwargs (Any): Các tham số bổ sung khác.

    Returns:
        PaddleOCREngine: Đối tượng động cơ PaddleOCR dùng chung.
    """
    global _SHARED_ENGINES, _SHARED_PADDLE_ENGINE
    key = (lang, use_gpu, use_angle_cls, enable_layout, use_table_recognition, text_det_limit_side_len)
    if key not in _SHARED_ENGINES:
        engine = PaddleOCREngine(
            use_gpu=use_gpu,
            lang=lang,
            use_angle_cls=use_angle_cls,
            enable_layout=enable_layout,
            use_table_recognition=use_table_recognition,
            text_det_limit_side_len=text_det_limit_side_len,
            **kwargs,
        )
        _SHARED_ENGINES[key] = engine
        if _SHARED_PADDLE_ENGINE is None:
            _SHARED_PADDLE_ENGINE = engine
    return _SHARED_ENGINES[key]


def reset_shared_paddle_engine() -> None:
    """Xóa bỏ các phiên bản động cơ dùng chung để giải phóng tài nguyên bộ nhớ (hữu ích cho unit test)."""
    global _SHARED_ENGINES, _SHARED_PADDLE_ENGINE
    _SHARED_ENGINES.clear()
    _SHARED_PADDLE_ENGINE = None


class PaddleOCREngine:
    """Lớp bao bọc cấp sản xuất cho PaddleOCR + PP-Structure tối ưu cho Báo cáo Tài chính Việt Nam.

    Attributes:
        use_gpu (bool): Cờ yêu cầu sử dụng GPU.
        lang (str): Ngôn ngữ nhận dạng.
        use_angle_cls (bool): Phân loại góc nghiêng dòng chữ.
        enable_layout (bool): Phân tích bố cục trang.
        use_table_recognition (bool): Nhận dạng bảng cấu trúc.
        text_det_limit_side_len (int): Giới hạn kích thước ảnh đầu vào.
        active_device (Optional[str]): Thiết bị phần cứng thực tế đang chạy ("gpu:0" hoặc "cpu").
        layout_status (str): Trạng thái của động cơ phân tích bố cục.
    """

    def __init__(
        self,
        use_gpu: bool = True,
        lang: str = "vi",
        use_angle_cls: bool = True,
        enable_layout: bool = True,
        use_table_recognition: bool = False,
        text_det_limit_side_len: int = 960,
        ocr_engine: Optional[Any] = None,
        structure_engine: Optional[Any] = None,
    ) -> None:
        """Khởi tạo đối tượng động cơ PaddleOCREngine.

        Args:
            use_gpu (bool): Cho phép dùng GPU (tự động chuyển CPU nếu CUDA không sẵn sàng).
            lang (str): Mã ngôn ngữ nhận dạng OCR (mặc định 'vi').
            use_angle_cls (bool): Tự động phát hiện và xoay chỉnh hướng dòng chữ.
            enable_layout (bool): Bật phân tích khối bố cục bằng PP-Structure.
            use_table_recognition (bool): Bật mô hình nhận diện ô bảng (mặc định False).
            text_det_limit_side_len (int): Giới hạn chiều dài ảnh phát hiện văn bản.
            ocr_engine (Optional[Any]): Động cơ OCR truyền sẵn (phục vụ mocking test).
            structure_engine (Optional[Any]): Động cơ layout truyền sẵn.
        """
        self.use_gpu: bool = use_gpu
        self.lang: str = lang
        self.use_angle_cls: bool = use_angle_cls
        self.enable_layout: bool = enable_layout
        self.use_table_recognition: bool = use_table_recognition
        self.text_det_limit_side_len: int = text_det_limit_side_len
        self._ocr_engine: Optional[Any] = ocr_engine
        self._structure_engine: Optional[Any] = structure_engine
        self._cuda_available: Optional[bool] = None

        # Trạng thái chẩn đoán và thực thi
        self.active_device: Optional[str] = None
        self.effective_config: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.layout_status: str = "uninitialized"

    def is_available(self) -> bool:
        """Kiểm tra xem các thư viện PaddlePaddle và PaddleOCR đã được cài đặt trong môi trường chưa.

        Returns:
            bool: True nếu đã cài đặt đầy đủ, False nếu chưa.
        """
        try:
            import paddle  # noqa: F401
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    def _check_cuda(self) -> bool:
        """Phát hiện xem phần cứng GPU CUDA có thực sự hoạt động trong PaddlePaddle không.

        Returns:
            bool: True nếu PaddlePaddle biên dịch có CUDA và tìm thấy ít nhất 1 GPU.
        """
        if self._cuda_available is not None:
            return self._cuda_available

        try:
            import paddle
            cuda_compiled = bool(getattr(paddle.device, "is_compiled_with_cuda", lambda: False)())
            dev_count = int(getattr(paddle.device.cuda, "device_count", lambda: 0)())
            self._cuda_available = cuda_compiled and (dev_count > 0)
        except Exception as e:
            logger.debug("CUDA check error: %s", e)
            self._cuda_available = False

        return self._cuda_available

    def release_memory(self) -> None:
        """Giải phóng bộ nhớ đệm VRAM của GPU và kích hoạt gom rác Python Garbage Collector."""
        try:
            import paddle
            if hasattr(paddle.device, "cuda") and hasattr(paddle.device.cuda, "empty_cache"):
                paddle.device.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()

    def _get_ocr_engine(self) -> Any:
        """Khởi tạo lười (lazy loading) phiên bản PaddleOCR với thiết bị phần cứng tối ưu.

        Returns:
            Any: Phiên bản PaddleOCR sẵn sàng nhận diện.

        Raises:
            RuntimeError: Nếu chưa cài đặt PaddleOCR.
            PaddleOCREngineError: Nếu khởi tạo thất bại.
        """
        if self._ocr_engine is not None:
            return self._ocr_engine

        if not self.is_available():
            raise RuntimeError("PaddlePaddle or PaddleOCR is not installed.")

        from paddleocr import PaddleOCR

        # Xác định thiết bị thực tế
        cuda_ok = self.use_gpu and self._check_cuda()
        device_str = "gpu:0" if cuda_ok else "cpu"
        if self.use_gpu and not cuda_ok:
            logger.warning(
                "GPU acceleration requested (use_gpu=True), but PaddlePaddle has no CUDA support. Running on CPU (device='cpu')."
            )

        self.active_device = device_str
        logger.info("Initializing PaddleOCR (lang=%s, device=%s)...", self.lang, device_str)

        init_kwargs: Dict[str, Any] = {
            "text_detection_model_name": "PP-OCRv5_server_det",
            "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
            "use_doc_unwarping": False,
            "use_doc_orientation_classify": self.use_angle_cls,
            "use_textline_orientation": self.use_angle_cls,
            "text_det_limit_side_len": self.text_det_limit_side_len,
            "enable_mkldnn": False,
            "device": device_str,
        }

        try:
            self._ocr_engine = PaddleOCR(**init_kwargs)
            self.effective_config = init_kwargs.copy()
        except TypeError as te:
            # Cơ chế dự phòng cho PaddleOCR 2.x cũ dùng use_gpu
            logger.warning("PaddleOCR modern initialization failed (%s); trying legacy parameter format...", te)
            legacy_kwargs = {
                "lang": self.lang,
                "use_gpu": cuda_ok,
                "use_angle_cls": self.use_angle_cls,
            }
            try:
                self._ocr_engine = PaddleOCR(**legacy_kwargs)
                self.effective_config = legacy_kwargs.copy()
            except Exception as e2:
                self.last_error = f"Legacy PaddleOCR initialization failed: {e2}"
                logger.error("All PaddleOCR initialization attempts failed: %s", e2, exc_info=True)
                raise PaddleOCREngineError(f"Failed to initialize PaddleOCR: {e2}") from e2
        except Exception as exc:
            self.last_error = f"PaddleOCR initialization failed: {exc}"
            logger.error("PaddleOCR initialization failed: %s", exc, exc_info=True)
            raise PaddleOCREngineError(f"Failed to initialize PaddleOCR: {exc}") from exc

        return self._ocr_engine

    def _get_structure_engine(self) -> Optional[Any]:
        """Khởi tạo lười phiên bản PP-Structure phục vụ nhận diện bố cục trang văn bản.

        Returns:
            Optional[Any]: Phiên bản PPStructure hoặc None nếu không khả dụng.
        """
        if self._structure_engine is not None:
            return self._structure_engine

        if not self.is_available():
            self.layout_status = "unavailable"
            return None

        try:
            try:
                from paddleocr import PPStructureV3 as PPStructureClass
            except ImportError:
                from paddleocr import PPStructure as PPStructureClass

            cuda_ok = self.use_gpu and self._check_cuda()
            device_str = "gpu:0" if cuda_ok else "cpu"

            logger.info(
                "Initializing PP-Structure engine (lang=%s, device=%s, use_table=%s)...",
                self.lang,
                device_str,
                self.use_table_recognition,
            )
            kwargs = {
                "lang": self.lang,
                "use_table_recognition": self.use_table_recognition,
                "use_seal_recognition": False,
                "use_formula_recognition": False,
                "use_chart_recognition": False,
                "use_doc_unwarping": False,
                "device": device_str,
                "enable_mkldnn": False,
            }
            try:
                self._structure_engine = PPStructureClass(**kwargs)
            except (TypeError, ValueError):
                legacy_struct_kwargs = {
                    "lang": self.lang,
                    "use_table_recognition": self.use_table_recognition,
                    "use_seal_recognition": False,
                }
                self._structure_engine = PPStructureClass(**legacy_struct_kwargs)
            self.layout_status = "uninitialized"
        except Exception as err:
            self.last_error = f"PP-Structure initialization failed: {err}"
            logger.warning("Failed to initialize PP-Structure layout engine: %s", err)
            self._structure_engine = None
            self.layout_status = "unavailable"

        return self._structure_engine

    def to_bgr_array(self, image_input: Union[Path, str, np.ndarray, Image.Image]) -> np.ndarray:
        """Chuyển đổi các định dạng ảnh đầu vào đa dạng thành mảng numpy BGR chuẩn mực.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh nguồn.

        Returns:
            np.ndarray: Mảng ảnh numpy 3 kênh BGR.

        Raises:
            ValueError: Khi không đọc được ảnh hoặc kích thước mảng không hợp lệ.
            TypeError: Khi kiểu dữ liệu đầu vào không được hỗ trợ.
        """
        if isinstance(image_input, (str, Path)):
            path_str = str(image_input)
            img = cv2.imread(path_str)
            if img is None:
                raise ValueError(f"Could not read image file: {path_str}")
            return img
        elif isinstance(image_input, Image.Image):
            rgb = np.array(image_input.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                return cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
            elif image_input.ndim == 3:
                return image_input.copy()
            else:
                raise ValueError(f"Invalid image array shape: {image_input.shape}")
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    @staticmethod
    def _sanitize_confidence(val: Any) -> float:
        """Chuẩn hóa điểm tin cậy về giá trị số thực trong đoạn [0.0, 1.0].

        Args:
            val (Any): Giá trị điểm tin cậy thô.

        Returns:
            float: Điểm tin cậy đã làm sạch và làm tròn 4 chữ số thập phân.
        """
        if val is None:
            return 1.0
        try:
            sc = float(val)
            if math.isnan(sc) or math.isinf(sc):
                return 0.0
            if sc > 1.0 and sc <= 100.0:
                sc = sc / 100.0
            return max(0.0, min(1.0, round(sc, 4)))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _extract_valid_bbox(poly_or_box: Any) -> Optional[Tuple[float, float, float, float]]:
        """Xác thực và bóc tách tọa độ hộp bao (ymin, xmin, ymax, xmax) từ đa giác hoặc hộp chữ nhật.

        Args:
            poly_or_box (Any): Danh sách điểm đa giác hoặc danh sách 4 tọa độ hộp bao.

        Returns:
            Optional[Tuple[float, float, float, float]]: (ymin, xmin, ymax, xmax) hoặc None nếu không hợp lệ.
        """
        if poly_or_box is None:
            return None
        try:
            if hasattr(poly_or_box, "tolist"):
                poly_or_box = poly_or_box.tolist()

            if not isinstance(poly_or_box, (list, tuple)) or len(poly_or_box) == 0:
                return None

            # Trường hợp A: Hộp chữ nhật 4 phần tử [xmin, ymin, xmax, ymax]
            if len(poly_or_box) == 4 and isinstance(poly_or_box[0], (int, float)):
                x1, y1, x2, y2 = [float(v) for v in poly_or_box]
                if any(math.isnan(v) or math.isinf(v) for v in (x1, y1, x2, y2)):
                    return None
                ymin = min(y1, y2)
                ymax = max(y1, y2)
                xmin = min(x1, x2)
                xmax = max(x1, x2)
                if ymax - ymin < 0.5 or xmax - xmin < 0.5:
                    return None
                return (ymin, xmin, ymax, xmax)

            # Trường hợp B: Danh sách các đỉnh đa giác [[x, y], [x, y], ...]
            if len(poly_or_box) >= 3:
                xs = []
                ys = []
                for pt in poly_or_box:
                    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                        return None
                    px, py = float(pt[0]), float(pt[1])
                    if math.isnan(px) or math.isnan(py) or math.isinf(px) or math.isinf(py):
                        return None
                    xs.append(px)
                    ys.append(py)

                ymin = min(ys)
                ymax = max(ys)
                xmin = min(xs)
                xmax = max(xs)
                if ymax - ymin < 0.5 or xmax - xmin < 0.5:
                    return None
                return (ymin, xmin, ymax, xmax)

            return None
        except Exception:
            return None

    @staticmethod
    def _cluster_boxes_into_lines(
        items_with_box: List[Tuple[Tuple[float, float, float, float], str, float]]
    ) -> Tuple[List[str], List[float]]:
        """Gom nhóm các hộp chữ nhật OCR theo phương ngang thành các dòng bảng phân cách bởi tab.

        Đặc điểm thuật toán:
        - Độc lập với thứ tự OCR trả về (sắp xếp tất định theo tọa độ y, sau đó x).
        - Xử lý các dòng có kích thước phông chữ khác nhau dựa trên tỷ lệ chồng lấn dọc tương đối.
        - Nghiêm ngặt ngăn chặn gộp các dòng chỉ tiêu tài chính liền kề nếu độ chồng lấn dọc < 45%.
        - Nối các từ trong cùng một cụm bằng dấu cách (' ') và phân cách các cột tài chính bằng tab ('\\t').

        Args:
            items_with_box (List[Tuple[Tuple[float, float, float, float], str, float]]):
                Danh sách các phần tử dạng ((ymin, xmin, ymax, xmax), text, confidence).

        Returns:
            Tuple[List[str], List[float]]: (Danh sách chuỗi dòng văn bản, Điểm tin cậy tương ứng).
        """
        if not items_with_box:
            return [], []

        # Sắp xếp ưu tiên theo tọa độ tâm y, sau đó đến tọa độ xmin
        sorted_items = sorted(
            items_with_box,
            key=lambda it: ((it[0][0] + it[0][2]) / 2.0, it[0][1]),
        )

        lines: List[List[Tuple[Tuple[float, float, float, float], str, float]]] = []

        for item in sorted_items:
            box, _, _ = item
            ymin, _, ymax, _ = box
            y_center = (ymin + ymax) / 2.0
            h = max(1.0, ymax - ymin)

            best_line_idx = -1
            best_overlap_ratio = 0.0

            for l_idx, line in enumerate(lines):
                # Tính toán khoảng bao phủ dọc của dòng hiện tại
                line_ymins = [b[0][0] for b in line]
                line_ymaxs = [b[0][2] for b in line]
                line_heights = [max(1.0, b[0][2] - b[0][0]) for b in line]
                med_line_h = float(np.median(line_heights))

                # Ngăn ngừa các khối quá cao (như con dấu bắc qua nhiều dòng) bị gộp vào dòng bình thường
                if h > 2.2 * med_line_h or med_line_h > 2.2 * h:
                    continue

                min_l = min(line_ymins)
                max_l = max(line_ymaxs)
                line_y_center = (sum(line_ymins) + sum(line_ymaxs)) / (2.0 * len(line))

                # Tính toán phần giao cắt dọc
                v_overlap = max(0.0, min(ymax, max_l) - max(ymin, min_l))
                overlap_ratio = v_overlap / min(h, med_line_h)

                # Phải chồng lấn ít nhất 45% chiều cao và độ lệch tâm không vượt quá 60% chiều cao
                if overlap_ratio >= 0.45 and abs(y_center - line_y_center) <= min(h, med_line_h) * 0.60:
                    if overlap_ratio > best_overlap_ratio:
                        best_overlap_ratio = overlap_ratio
                        best_line_idx = l_idx

            if best_line_idx >= 0:
                lines[best_line_idx].append(item)
            else:
                lines.append([item])

        # Sắp xếp các dòng từ trên xuống dưới theo trung bình ymin
        lines.sort(key=lambda line: float(np.mean([it[0][0] for it in line])))

        out_texts: List[str] = []
        out_scores: List[float] = []

        def _is_num_or_code(text: str) -> bool:
            t = text.strip()
            return bool(re.match(r"^[\(\[]?-?\d+[\.,\d]*[\)\]\*#S]*$", t))

        for line in lines:
            # Sắp xếp các từ trong dòng từ trái sang phải theo xmin
            line.sort(key=lambda it: it[0][1])

            # Tính toán khoảng cách cột dựa trên chiều cao trung vị dòng
            heights = [max(1.0, it[0][2] - it[0][0]) for it in line]
            med_h = float(np.median(heights)) if heights else 15.0
            col_gap_threshold = max(10.0, med_h * 0.75)

            line_tokens: List[str] = []
            prev_xmax: Optional[float] = None
            prev_txt: str = ""

            for it in line:
                box, txt, _ = it
                xmin, xmax = box[1], box[3]
                clean_txt = txt.strip()
                if not clean_txt:
                    continue

                if prev_xmax is None:
                    line_tokens.append(clean_txt)
                else:
                    gap = xmin - prev_xmax
                    both_numbers = _is_num_or_code(prev_txt) and _is_num_or_code(clean_txt)
                    either_number = _is_num_or_code(prev_txt) or _is_num_or_code(clean_txt)

                    if both_numbers and gap >= 3.0:
                        # Hai số tài chính liền kề bắt buộc là hai cột tách biệt
                        line_tokens.append("\t" + clean_txt)
                    elif either_number and gap >= max(6.0, med_h * 0.45):
                        # Chuyển tiếp giữa tên chỉ tiêu và số tiền
                        line_tokens.append("\t" + clean_txt)
                    elif gap >= col_gap_threshold:
                        # Khoảng cách cột rõ rệt
                        line_tokens.append("\t" + clean_txt)
                    else:
                        # Từ trong cùng một cụm từ hoặc ô
                        line_tokens.append(" " + clean_txt)

                prev_xmax = max(prev_xmax or xmax, xmax)
                prev_txt = clean_txt

            if line_tokens:
                line_str = "".join(line_tokens).strip()
                line_str = re.sub(r"\t+", "\t", line_str)
                line_score = float(np.mean([it[2] for it in line]))
                out_texts.append(line_str)
                out_scores.append(round(line_score, 4))

        return out_texts, out_scores

    def _parse_ocr_raw_result(self, raw_result: Any) -> Tuple[List[str], List[float]]:
        """Bóc tách các dòng văn bản và điểm tin cậy từ đầu ra thô của PaddleOCR.

        Args:
            raw_result (Any): Kết quả thô từ động cơ OCR.

        Returns:
            Tuple[List[str], List[float]]: (Danh sách dòng văn bản, Danh sách điểm tin cậy).
        """
        texts, scores, _, _ = self._parse_ocr_raw_result_detailed(raw_result)
        return texts, scores

    def _parse_ocr_raw_result_detailed(
        self, raw_result: Any
    ) -> Tuple[
        List[str],
        List[float],
        List[Tuple[Tuple[float, float, float, float], str, float]],
        List[Tuple[str, float]],
    ]:
        """Phân tích chi tiết kết quả OCR thô thành các mục có tọa độ hộp bao và không có tọa độ.

        Args:
            raw_result (Any): Dữ liệu thô từ PaddleOCR (dạng danh sách, từ điển hoặc đối tượng chuyên biệt).

        Returns:
            Tuple[List[str], List[float], List[Tuple[...]], List[Tuple[...]]]:
                (Dòng văn bản đã gom nhóm, Điểm tin cậy, Phần tử có hộp bao, Phần tử không hộp bao).
        """
        texts: List[str] = []
        scores: List[float] = []
        items_with_box: List[Tuple[Tuple[float, float, float, float], str, float]] = []
        unboxed_items: List[Tuple[str, float]] = []

        if raw_result is None:
            return texts, scores, items_with_box, unboxed_items

        if not isinstance(raw_result, (list, tuple, dict)) and not hasattr(raw_result, "keys"):
            logger.warning("Unsupported OCR raw_result type: %s", type(raw_result))
            self.last_error = f"Unsupported raw_result type: {type(raw_result)}"
            return texts, scores, items_with_box, unboxed_items

        # Xử lý kết quả trả về dạng danh sách nhiều trang hoặc một trang
        items: List[Any] = []
        if isinstance(raw_result, (list, tuple)):
            if len(raw_result) == 1 and isinstance(raw_result[0], (list, tuple)):
                items = list(raw_result[0])
            else:
                items = list(raw_result)
        elif isinstance(raw_result, dict) or hasattr(raw_result, "keys"):
            items = [raw_result]

        for item in items:
            if item is None:
                continue

            # Trường hợp kiểu từ điển (OCRResult)
            if isinstance(item, dict) or hasattr(item, "keys"):
                rec_texts = item.get("rec_texts")
                rec_scores = item.get("rec_scores")
                polys = item.get("rec_polys") or item.get("dt_polys") or item.get("rec_boxes")

                if isinstance(rec_texts, list) and rec_texts:
                    for idx, t in enumerate(rec_texts):
                        t_str = str(t).strip() if t is not None else ""
                        if not t_str:
                            continue

                        raw_sc = rec_scores[idx] if (isinstance(rec_scores, list) and idx < len(rec_scores)) else 1.0
                        sc = self._sanitize_confidence(raw_sc)

                        box = None
                        if polys is not None and isinstance(polys, (list, tuple, np.ndarray)) and idx < len(polys):
                            box = self._extract_valid_bbox(polys[idx])

                        if box is not None:
                            items_with_box.append((box, t_str, sc))
                        else:
                            unboxed_items.append((t_str, sc))
                    continue

                # Dự phòng cho khối văn bản đơn lẻ
                text = item.get("rec_text") or item.get("text") or ""
                raw_score = item.get("rec_score") or item.get("confidence") or item.get("score")
                sc = self._sanitize_confidence(raw_score)
                box = None
                raw_box = item.get("bbox") or item.get("poly")
                if raw_box is not None:
                    box = self._extract_valid_bbox(raw_box)

                if str(text).strip():
                    t_str = str(text).strip()
                    if box is not None:
                        items_with_box.append((box, t_str, sc))
                    else:
                        unboxed_items.append((t_str, sc))
                    continue

            # Đầu ra PaddleOCR truyền thống: [ [ [x1,y1],... ], (text, score) ]
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                poly = item[0]
                val = item[1]
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    t_raw, sc_raw = val[0], val[1]
                    t_str = str(t_raw).strip() if t_raw is not None else ""
                    if t_str:
                        sc = self._sanitize_confidence(sc_raw)
                        box = self._extract_valid_bbox(poly)
                        if box is not None:
                            items_with_box.append((box, t_str, sc))
                        else:
                            unboxed_items.append((t_str, sc))
                elif isinstance(val, str):
                    t_str = val.strip()
                    if t_str:
                        box = self._extract_valid_bbox(poly)
                        if box is not None:
                            items_with_box.append((box, t_str, 1.0))
                        else:
                            unboxed_items.append((t_str, 1.0))
                continue

        # Gom nhóm các mục có hộp bao thành các dòng hoàn chỉnh
        if items_with_box:
            clustered_texts, clustered_scores = self._cluster_boxes_into_lines(items_with_box)
            texts.extend(clustered_texts)
            scores.extend(clustered_scores)

        # Giữ nguyên các phần tử không có hộp bao để không làm thất thoát dữ liệu
        if unboxed_items:
            for u_text, u_score in unboxed_items:
                texts.append(u_text)
                scores.append(u_score)

        return texts, scores, items_with_box, unboxed_items

    def ocr_image_detailed(
        self,
        image_input: Union[Path, str, np.ndarray, Image.Image],
        lang: Optional[str] = None,
    ) -> Tuple[
        str,
        float,
        List[Tuple[Tuple[float, float, float, float], str, float]],
        List[Tuple[str, float]],
    ]:
        """Thực hiện OCR toàn bộ ảnh trong một lượt và trả về văn bản hợp nhất kèm chi tiết hộp bao.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh đầu vào.
            lang (Optional[str]): Ngôn ngữ ghi đè nếu có.

        Returns:
            Tuple[str, float, List[Tuple[...]], List[Tuple[...]]]:
                (Văn bản hợp nhất, Điểm tin cậy trung bình, Các mục có hộp bao, Các mục không hộp bao).
        """
        img = self.to_bgr_array(image_input)
        if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
            return "", 0.0, [], []

        ocr_engine = self._get_ocr_engine()
        try:
            if hasattr(ocr_engine, "predict"):
                raw_res = ocr_engine.predict(img)
            elif hasattr(ocr_engine, "ocr"):
                raw_res = ocr_engine.ocr(img)
            else:
                raw_res = ocr_engine(img)
        except Exception as exc:
            self.last_error = f"PaddleOCR execution failed: {exc}"
            logger.error("PaddleOCR execution failed: %s", exc, exc_info=True)
            return "", 0.0, [], []

        texts, scores, items_with_box, unboxed_items = self._parse_ocr_raw_result_detailed(raw_res)
        if not texts:
            return "", 0.0, items_with_box, unboxed_items

        merged_text = "\n".join(texts)
        avg_confidence = round(float(np.mean(scores)), 4) if scores else 0.0
        return merged_text, avg_confidence, items_with_box, unboxed_items

    def ocr_image(
        self,
        image_input: Union[Path, str, np.ndarray, Image.Image],
        lang: Optional[str] = None,
    ) -> Tuple[str, float]:
        """Thực hiện OCR toàn bộ ảnh và trả về văn bản kết hợp kèm điểm tin cậy trung bình.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh cần OCR.
            lang (Optional[str]): Ngôn ngữ ghi đè.

        Returns:
            Tuple[str, float]: (Văn bản nhận diện được, Điểm tin cậy trung bình).
        """
        img = self.to_bgr_array(image_input)
        if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
            return "", 0.0

        ocr_engine = self._get_ocr_engine()
        try:
            if hasattr(ocr_engine, "predict"):
                raw_res = ocr_engine.predict(img)
            elif hasattr(ocr_engine, "ocr"):
                raw_res = ocr_engine.ocr(img)
            else:
                raw_res = ocr_engine(img)
        except Exception as exc:
            self.last_error = f"PaddleOCR execution failed: {exc}"
            logger.error("PaddleOCR execution failed: %s", exc, exc_info=True)
            return "", 0.0

        texts, scores = self._parse_ocr_raw_result(raw_res)
        if not texts:
            return "", 0.0

        merged_text = "\n".join(texts)
        avg_confidence = round(float(np.mean(scores)), 4) if scores else 0.0
        return merged_text, avg_confidence

    def analyze_layout(
        self,
        image_input: Union[Path, str, np.ndarray, Image.Image],
    ) -> List[LayoutRegion]:
        """Phân tích bố cục trang tài liệu và nhận diện các khối ngữ nghĩa bằng PP-Structure.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh tài liệu.

        Returns:
            List[LayoutRegion]: Danh sách các vùng bố cục kèm cờ chọn lọc (included).
        """
        img = self.to_bgr_array(image_input)
        structure_engine = self._get_structure_engine()
        if structure_engine is None:
            self.layout_status = "unavailable"
            return []

        try:
            if hasattr(structure_engine, "predict"):
                raw_layout = structure_engine.predict(img)
            else:
                raw_layout = structure_engine(img)
            self.layout_status = "success"
        except Exception as exc:
            self.layout_status = "failed"
            self.last_error = f"PP-Structure layout detection error: {exc}"
            logger.warning("PP-Structure layout detection error: %s", exc, exc_info=True)
            return []

        if not raw_layout:
            self.layout_status = "empty"
            return []

        # Làm phẳng cấu trúc phân cấp khối từ các phiên bản PaddleOCR / PaddleX 3.x
        blocks_to_process: List[Any] = []
        if isinstance(raw_layout, list):
            for entry in raw_layout:
                if isinstance(entry, dict) and "parsing_res_list" in entry:
                    blocks_to_process.extend(entry["parsing_res_list"])
                elif hasattr(entry, "parsing_res_list"):
                    blocks_to_process.extend(getattr(entry, "parsing_res_list"))
                else:
                    blocks_to_process.append(entry)
        elif hasattr(raw_layout, "parsing_res_list"):
            blocks_to_process.extend(getattr(raw_layout, "parsing_res_list"))
        elif isinstance(raw_layout, dict) and "parsing_res_list" in raw_layout:
            blocks_to_process.extend(raw_layout["parsing_res_list"])
        elif hasattr(raw_layout, "__iter__") and not isinstance(raw_layout, (list, tuple)):
            blocks_to_process = list(raw_layout)
        else:
            blocks_to_process = [raw_layout]

        if not blocks_to_process:
            self.layout_status = "empty"
            return []

        regions: List[LayoutRegion] = []
        h_img, w_img = img.shape[:2]

        for block in blocks_to_process:
            if block is None:
                continue

            region_type = "text"
            raw_bbox = [0, 0, w_img, h_img]
            block_text = ""
            block_html = ""
            conf = 0.90

            if isinstance(block, dict):
                region_type = str(block.get("type") or block.get("label") or "text").lower()
                raw_bbox = block.get("bbox", raw_bbox)

                content = block.get("content")
                res = block.get("res")
                if content:
                    block_text = str(content).strip()
                elif isinstance(res, dict):
                    block_html = res.get("html", "")
                    if "text" in res:
                        block_text = str(res["text"]).strip()
                elif isinstance(res, list):
                    lines = []
                    confs = []
                    for line in res:
                        if isinstance(line, dict):
                            t = line.get("text", "")
                            c = line.get("confidence", 0.0)
                            if t.strip():
                                lines.append(t.strip())
                                confs.append(float(c))
                    block_text = "\n".join(lines)
                    conf = float(np.mean(confs)) if confs else 0.0
            else:
                label = getattr(block, "label", getattr(block, "type", "text"))
                region_type = str(label).lower() if label else "text"
                raw_bbox = getattr(block, "bbox", raw_bbox)
                content = getattr(block, "content", None)
                if content:
                    block_text = str(content).strip()

            # Giới hạn và làm sạch tọa độ hộp bao
            try:
                x1 = max(0, min(int(round(float(raw_bbox[0]))), w_img))
                y1 = max(0, min(int(round(float(raw_bbox[1]))), h_img))
                x2 = max(x1, min(int(round(float(raw_bbox[2]))), w_img))
                y2 = max(y1, min(int(round(float(raw_bbox[3]))), h_img))
                bbox = (x1, y1, x2, y2)
            except Exception:
                bbox = (0, 0, w_img, h_img)

            # Quyết định Giữ lại / Loại trừ vùng:
            # 1. Các vùng không phải nhiễu (bảng biểu, văn bản, tiêu đề) mặc định được GIỮ LẠI (included=True).
            # 2. Đối với header/footer/stamps: KHÔNG loại trừ nếu chứa siêu dữ liệu tài chính,
            #    mã số kế toán, đơn vị tính hoặc tên mẫu biểu BCTC!
            included = True
            if region_type in EXCLUDED_REGION_TYPES:
                has_financial_content = bool(
                    _FINANCIAL_RE.search(block_text) or _FINANCIAL_CODE_OR_NUM_RE.search(block_text)
                )
                is_pure_page_num = bool(_PAGE_NUMBER_RE.match(block_text.strip()))

                if has_financial_content and not is_pure_page_num:
                    included = True
                    logger.debug(
                        "Preserving %s region at %s because it contains financial metadata: '%s'",
                        region_type,
                        bbox,
                        block_text[:50],
                    )
                else:
                    included = False

            regions.append(
                LayoutRegion(
                    region_type=region_type,
                    bbox=bbox,
                    confidence=self._sanitize_confidence(conf),
                    text=block_text,
                    html=block_html,
                    included=included,
                )
            )

        return regions

    def ocr_with_layout(
        self,
        image_input: Union[Path, str, np.ndarray, Image.Image],
    ) -> Tuple[str, float, List[LayoutRegion]]:
        """Thực thi quy trình OCR 1 lượt (Single-Pass) kết hợp phân tích bố cục hình học và lọc nhiễu.

        Loại bỏ hoàn toàn vòng lặp N+1 crop bằng cách chỉ chạy OCR toàn trang một lần duy nhất,
        sau đó gán các hộp chữ vào các vùng cấu trúc dựa trên tọa độ hình học không gian.

        Args:
            image_input (Union[Path, str, np.ndarray, Image.Image]): Ảnh tài liệu.

        Returns:
            Tuple[str, float, List[LayoutRegion]]: (Văn bản hợp nhất, Điểm tin cậy trung bình, Toàn bộ vùng bố cục).
        """
        img = self.to_bgr_array(image_input)
        h, w = img.shape[:2]

        # BƯỚC 1: Thực thi OCR một lượt duy nhất trên toàn bộ trang ảnh (1 forward pass)
        merged_text, avg_conf, items_with_box, unboxed_items = self.ocr_image_detailed(img)

        # Giải phóng bộ nhớ đệm VRAM ngay sau khi suy luận
        self.release_memory()

        if not self.enable_layout:
            fallback_region = LayoutRegion(
                region_type="text",
                bbox=(0, 0, w, h),
                confidence=avg_conf,
                text=merged_text,
                included=True,
            )
            return merged_text, avg_conf, [fallback_region]

        # BƯỚC 2: Phân tích bố cục ngữ nghĩa
        regions = self.analyze_layout(img)
        if not regions:
            logger.debug(
                "No layout regions detected (status=%s); falling back to full-page OCR.",
                self.layout_status,
            )
            fallback_region = LayoutRegion(
                region_type="text",
                bbox=(0, 0, w, h),
                confidence=avg_conf,
                text=merged_text,
                included=True,
            )
            return merged_text, avg_conf, [fallback_region]

        # BƯỚC 3: Ghép nối không gian (Spatial Center-in-Box Matching)
        regions.sort(key=lambda r: (r.bbox[1], r.bbox[0]))

        assigned_indices = set()
        for region in regions:
            if not region.included:
                logger.debug("Filtered out noise region: %s at %s", region.region_type, region.bbox)
                continue

            rx1, ry1, rx2, ry2 = region.bbox

            # Nếu vùng đã có văn bản cấu trúc hoặc HTML từ động cơ bảng, bảo lưu nó
            if region.text.strip() or (region.html and region.html.strip()):
                continue

            # Gán các hộp chữ có tọa độ tâm nằm trong vùng bố cục
            region_items = []
            for idx, item in enumerate(items_with_box):
                box, txt, sc = item
                ymin, xmin, ymax, xmax = box
                cx = (xmin + xmax) / 2.0
                cy = (ymin + ymax) / 2.0
                if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                    region_items.append(item)
                    assigned_indices.add(idx)

            if region_items:
                r_texts, r_scores = self._cluster_boxes_into_lines(region_items)
                region.text = "\n".join(r_texts)
                region.confidence = round(float(np.mean(r_scores)), 4) if r_scores else 0.9

        # Xử lý các mục văn bản còn sót không lọt vào vùng nhận diện nào
        leftover_items = [item for idx, item in enumerate(items_with_box) if idx not in assigned_indices]
        if leftover_items:
            leftover_texts, leftover_scores = self._cluster_boxes_into_lines(leftover_items)
            if leftover_texts:
                regions.append(
                    LayoutRegion(
                        region_type="text",
                        bbox=(0, 0, w, h),
                        confidence=round(float(np.mean(leftover_scores)), 4) if leftover_scores else 0.9,
                        text="\n".join(leftover_texts),
                        included=True,
                    )
                )

        # Sắp xếp lại tất cả các vùng theo thứ tự đọc tự nhiên (từ trên xuống dưới, từ trái sang phải)
        regions.sort(key=lambda r: (r.bbox[1], r.bbox[0]))

        content_parts: List[str] = []
        confidences: List[float] = []
        for region in regions:
            if not region.included:
                continue
            if region.text.strip():
                content_parts.append(region.text.strip())
                if region.confidence > 0.0:
                    confidences.append(region.confidence)
            elif region.html and region.html.strip():
                content_parts.append(region.html.strip())

        final_text = "\n\n".join(content_parts) if content_parts else merged_text
        final_conf = round(float(np.mean(confidences)), 4) if confidences else avg_conf

        return final_text, final_conf, regions
