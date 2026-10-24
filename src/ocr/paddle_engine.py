"""PaddleOCR and PP-Structure wrapper for Vietnamese financial document extraction.

Provides text recognition, layout detection, and table structure analysis
with noise filtering (headers, footers, figures, stamps) and reading-order merging.
"""
import gc
import inspect
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure Windows DLL directories for NVIDIA CUDA runtime if installed in virtualenv
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

# Set PaddlePaddle environment flags to prevent oneDNN PIR unsupported attribute regression
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")

import cv2
import numpy as np
from PIL import Image

from src.ocr.models import LayoutRegion

logger = logging.getLogger(__name__)


class PaddleOCREngineError(Exception):
    """Raised when an unrecoverable error occurs in PaddleOCREngine."""
    pass


# Region types considered noise unless they contain vital financial metadata
EXCLUDED_REGION_TYPES = {"header", "footer", "figure", "seal", "stamp", "logo", "reference", "page_number"}

# Regex patterns identifying vital Vietnamese financial metadata in headers/footers
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


# Singleton engine dictionary keyed by configuration tuple
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
    """Return a shared singleton PaddleOCREngine instance keyed by its configuration.

    Ensures that calling with different parameters returns an engine with matching configuration.
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
    """Safely clear shared engine singletons (useful for unit tests and clean resource reclamation)."""
    global _SHARED_ENGINES, _SHARED_PADDLE_ENGINE
    _SHARED_ENGINES.clear()
    _SHARED_PADDLE_ENGINE = None


class PaddleOCREngine:
    """Production PaddleOCR + PP-Structure wrapper for Vietnamese financial statements."""

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
    ):
        """Initialize PaddleOCREngine.

        Args:
            use_gpu: Whether to attempt GPU acceleration (auto-fallback to CPU).
            lang: Language code for OCR recognition (default 'vi').
            use_angle_cls: Automatically correct rotated text (0/90/180/270 degrees).
            enable_layout: Whether to perform PP-Structure layout analysis and filtering.
            use_table_recognition: Whether to load heavy RT-DETR-L table cell models (default False).
            text_det_limit_side_len: Maximum side length for detection to cap memory.
            ocr_engine: Optional pre-instantiated OCR engine (useful for testing/mocking).
            structure_engine: Optional pre-instantiated structure engine.
        """
        self.use_gpu = use_gpu
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.enable_layout = enable_layout
        self.use_table_recognition = use_table_recognition
        self.text_det_limit_side_len = text_det_limit_side_len
        self._ocr_engine = ocr_engine
        self._structure_engine = structure_engine
        self._cuda_available: Optional[bool] = None

        # Diagnostic and execution state
        self.active_device: Optional[str] = None
        self.effective_config: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.layout_status: str = "uninitialized"

    def is_available(self) -> bool:
        """Check if PaddlePaddle and PaddleOCR packages are installed."""
        try:
            import paddle  # noqa: F401
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    def _check_cuda(self) -> bool:
        """Detect whether CUDA/GPU is actually available in PaddlePaddle."""
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
        """Safely release GPU VRAM cache and invoke Python garbage collector."""
        try:
            import paddle
            if hasattr(paddle.device, "cuda") and hasattr(paddle.device.cuda, "empty_cache"):
                paddle.device.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()

    def _get_ocr_engine(self) -> Any:
        """Lazy initialization of PaddleOCR instance with verified device configuration."""
        if self._ocr_engine is not None:
            return self._ocr_engine

        if not self.is_available():
            raise RuntimeError("PaddlePaddle or PaddleOCR is not installed.")

        from paddleocr import PaddleOCR

        # Determine effective device
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
            # Fallback for older PaddleOCR 2.x which accepts use_gpu and use_angle_cls
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
        """Lazy initialization of PP-Structure engine for layout detection."""
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
        """Convert various image input formats to a standardized BGR numpy array."""
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
        """Sanitize confidence score to a float between 0.0 and 1.0."""
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
        """Validate and extract (ymin, xmin, ymax, xmax) from polygon or bbox."""
        if poly_or_box is None:
            return None
        try:
            if hasattr(poly_or_box, "tolist"):
                poly_or_box = poly_or_box.tolist()

            if not isinstance(poly_or_box, (list, tuple)) or len(poly_or_box) == 0:
                return None

            # Case A: 4-element bbox [xmin, ymin, xmax, ymax]
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

            # Case B: list of points [[x, y], [x, y], ...]
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
        """Cluster OCR bounding boxes horizontally into tab-separated table rows.

        Ensures:
        - Independent of input order (sorts items deterministically).
        - Handles rows with differing font sizes/heights via relative vertical overlap.
        - Strictly prevents merging adjacent financial rows if vertical overlap < 45%.
        - Joins intra-phrase words with space and column gaps with tab.

        Args:
            items_with_box: List of ((ymin, xmin, ymax, xmax), text, confidence)

        Returns:
            Tuple of (line_strings, line_confidences)
        """
        if not items_with_box:
            return [], []

        # Sort primarily by vertical coordinate (center y), secondarily by xmin
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
                # Calculate bounding vertical span of the line
                line_ymins = [b[0][0] for b in line]
                line_ymaxs = [b[0][2] for b in line]
                line_heights = [max(1.0, b[0][2] - b[0][0]) for b in line]
                med_line_h = float(np.median(line_heights))

                # Prevent tall items (e.g. seals/stamps spanning multiple rows) from merging with normal lines
                if h > 2.2 * med_line_h or med_line_h > 2.2 * h:
                    continue

                min_l = min(line_ymins)
                max_l = max(line_ymaxs)
                line_y_center = (sum(line_ymins) + sum(line_ymaxs)) / (2.0 * len(line))

                # Compute vertical intersection
                v_overlap = max(0.0, min(ymax, max_l) - max(ymin, min_l))
                overlap_ratio = v_overlap / min(h, med_line_h)

                # Must overlap by at least 45% of the smaller box and centers must be aligned
                if overlap_ratio >= 0.45 and abs(y_center - line_y_center) <= min(h, med_line_h) * 0.60:
                    if overlap_ratio > best_overlap_ratio:
                        best_overlap_ratio = overlap_ratio
                        best_line_idx = l_idx

            if best_line_idx >= 0:
                lines[best_line_idx].append(item)
            else:
                lines.append([item])

        # Sort lines from top to bottom by average ymin
        lines.sort(key=lambda line: float(np.mean([it[0][0] for it in line])))

        out_texts: List[str] = []
        out_scores: List[float] = []

        def _is_num_or_code(text: str) -> bool:
            t = text.strip()
            return bool(re.match(r"^[\(\[]?-?\d+[\.,\d]*[\)\]\*#S]*$", t))

        for line in lines:
            # Sort tokens in line strictly left-to-right by xmin
            line.sort(key=lambda it: it[0][1])

            # Compute median height for column separation heuristics
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
                        # Adjacent financial numbers/codes are strictly distinct columns
                        line_tokens.append("\t" + clean_txt)
                    elif either_number and gap >= max(6.0, med_h * 0.45):
                        # Transition between label/note and number/code column
                        line_tokens.append("\t" + clean_txt)
                    elif gap >= col_gap_threshold:
                        # Clear column separation
                        line_tokens.append("\t" + clean_txt)
                    else:
                        # Adjacent word within same cell/phrase or slightly overlapping
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
        """Parse text lines and confidence scores from varied PaddleOCR outputs."""
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
        """Parse text lines, scores, and detailed boxed/unboxed items from PaddleOCR output."""
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

        # Handle list-of-pages or single-page response
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

            # Dict or mapping (OCRResult)
            if isinstance(item, dict) or hasattr(item, "keys"):
                rec_texts = item.get("rec_texts")
                rec_scores = item.get("rec_scores")
                polys = item.get("rec_polys") or item.get("dt_polys") or item.get("rec_boxes")

                if isinstance(rec_texts, list) and rec_texts:
                    for idx, t in enumerate(rec_texts):
                        t_str = str(t).strip() if t is not None else ""
                        if not t_str:
                            continue

                        # Validate confidence
                        raw_sc = rec_scores[idx] if (isinstance(rec_scores, list) and idx < len(rec_scores)) else 1.0
                        sc = self._sanitize_confidence(raw_sc)

                        # Validate poly / box
                        box = None
                        if polys is not None and isinstance(polys, (list, tuple, np.ndarray)) and idx < len(polys):
                            box = self._extract_valid_bbox(polys[idx])

                        if box is not None:
                            items_with_box.append((box, t_str, sc))
                        else:
                            unboxed_items.append((t_str, sc))
                    continue

                # Fallback for single text block dict
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

            # Classic PaddleOCR output: [ [ [x1,y1],... ], (text, score) ]
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

        # Cluster items with boxes into lines
        if items_with_box:
            clustered_texts, clustered_scores = self._cluster_boxes_into_lines(items_with_box)
            texts.extend(clustered_texts)
            scores.extend(clustered_scores)

        # CRITICAL: Preserve unboxed items so NO data is lost
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
        """OCR entire image in a single pass and return merged text, average score, and all boxed items.

        Args:
            image_input: Image as filepath, PIL Image, or numpy array.
            lang: Language override (optional).

        Returns:
            Tuple of (merged_text, average_confidence, items_with_box, unboxed_items).
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
        """OCR entire image and return combined text with average confidence score.

        Args:
            image_input: Image as filepath, PIL Image, or numpy array.
            lang: Language override (optional).

        Returns:
            Tuple of (merged_text, average_confidence).
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
        """Analyze page layout and detect semantic blocks using PP-Structure.

        Args:
            image_input: Document image.

        Returns:
            List of detected LayoutRegion objects with inclusion flags.
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

        # Flatten blocks from various PaddleOCR / PaddleX 3.x structures
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
                # PaddleX block object
                label = getattr(block, "label", getattr(block, "type", "text"))
                region_type = str(label).lower() if label else "text"
                raw_bbox = getattr(block, "bbox", raw_bbox)
                content = getattr(block, "content", None)
                if content:
                    block_text = str(content).strip()

            # Sanitize and clamp bounding box
            try:
                x1 = max(0, min(int(round(float(raw_bbox[0]))), w_img))
                y1 = max(0, min(int(round(float(raw_bbox[1]))), h_img))
                x2 = max(x1, min(int(round(float(raw_bbox[2]))), w_img))
                y2 = max(y1, min(int(round(float(raw_bbox[3]))), h_img))
                bbox = (x1, y1, x2, y2)
            except Exception:
                bbox = (0, 0, w_img, h_img)

            # Robust Inclusion / Exclusion Decision:
            # 1. Non-noise regions (tables, text, titles, unknown labels) are INCLUDED by default.
            # 2. Even for headers/footers/stamps: DO NOT exclude if they contain financial metadata,
            #    accounting codes, currency units, or statement titles!
            included = True
            if region_type in EXCLUDED_REGION_TYPES:
                # Check if it contains financial indicators
                has_financial_content = bool(
                    _FINANCIAL_RE.search(block_text) or _FINANCIAL_CODE_OR_NUM_RE.search(block_text)
                )
                is_pure_page_num = bool(_PAGE_NUMBER_RE.match(block_text.strip()))

                if has_financial_content and not is_pure_page_num:
                    # Keep it! It has vital financial indicators
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
        """Run Single-Pass OCR with spatial layout analysis and selective noise filtering.

        Eliminates the N+1 crop loop by executing OCR once for the entire image,
        then assigning text boxes to detected layout/table regions using spatial geometry.

        Args:
            image_input: Document image.

        Returns:
            Tuple of (merged_text, average_confidence, all_regions).
        """
        img = self.to_bgr_array(image_input)
        h, w = img.shape[:2]

        # STEP 1: Single-pass OCR across the entire page (1 model execution only!)
        merged_text, avg_conf, items_with_box, unboxed_items = self.ocr_image_detailed(img)

        # Release memory cache immediately after inference
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

        # STEP 2: Semantic layout analysis
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

        # STEP 3: Spatial IoU / Center-in-Box Matching (Zero Extra Forward Passes!)
        regions.sort(key=lambda r: (r.bbox[1], r.bbox[0]))

        assigned_indices = set()
        for region in regions:
            if not region.included:
                logger.debug("Filtered out noise region: %s at %s", region.region_type, region.bbox)
                continue

            rx1, ry1, rx2, ry2 = region.bbox

            # If region already has structured text or HTML from table engine, preserve it
            if region.text.strip() or (region.html and region.html.strip()):
                continue

            # Assign text boxes whose center point falls inside region bbox
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

        # Handle any leftover items that didn't fall inside detected regions
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

        # Re-sort all active regions in reading order
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
