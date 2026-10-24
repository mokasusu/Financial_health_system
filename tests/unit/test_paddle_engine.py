"""Unit tests for PaddleOCREngine with mock and synthetic data."""
from unittest.mock import MagicMock
import numpy as np
from PIL import Image
import pytest

from src.ocr.models import LayoutRegion
from src.ocr.paddle_engine import (
    PaddleOCREngine,
    PaddleOCREngineError,
    get_shared_paddle_engine,
    reset_shared_paddle_engine,
)


def test_paddle_engine_init_and_availability():
    engine = PaddleOCREngine(use_gpu=False, lang="vi")
    assert engine.use_gpu is False
    assert engine.lang == "vi"
    assert engine.is_available() is True


def test_to_bgr_array():
    engine = PaddleOCREngine()

    # PIL input
    pil_img = Image.new("RGB", (60, 40), color=(100, 150, 200))
    arr = engine.to_bgr_array(pil_img)
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (40, 60, 3)

    # 2D grayscale array
    gray = np.zeros((30, 30), dtype=np.uint8)
    bgr = engine.to_bgr_array(gray)
    assert bgr.shape == (30, 30, 3)

    # Invalid input
    with pytest.raises(TypeError):
        engine.to_bgr_array(12345)


def test_parse_ocr_raw_result_classic_format():
    engine = PaddleOCREngine()
    # Classic format: list of [ [ [x, y], ... ], (text, score) ]
    raw = [
        [
            [[[0, 0], [10, 0], [10, 10], [0, 10]], ("CONG TY CO PHAN 32", 0.985)],
            [[[0, 20], [10, 20], [10, 30], [0, 30]], ("DOANH THU THUAN", 0.950)],
        ]
    ]
    texts, scores = engine._parse_ocr_raw_result(raw)
    assert texts == ["CONG TY CO PHAN 32", "DOANH THU THUAN"]
    assert len(scores) == 2
    assert scores[0] == pytest.approx(0.985)


def test_parse_ocr_raw_result_paddlex_dict_format():
    engine = PaddleOCREngine()
    # PaddleX pipeline dict format
    raw = [
        {
            "rec_texts": ["TAI SAN NGAN HAN", "450.000.000.000 VND"],
            "rec_scores": [0.99, 0.92],
        }
    ]
    texts, scores = engine._parse_ocr_raw_result(raw)
    assert texts == ["TAI SAN NGAN HAN", "450.000.000.000 VND"]
    assert scores == [0.99, 0.92]


def test_ocr_image_mock():
    mock_ocr = MagicMock()
    mock_ocr.predict.return_value = [
        {
            "rec_texts": ["Loi nhuan sau thue", "15.000.000.000 VND"],
            "rec_scores": [0.96, 0.94],
        }
    ]
    engine = PaddleOCREngine(ocr_engine=mock_ocr)
    dummy_img = np.ones((50, 100, 3), dtype=np.uint8) * 255

    text, conf = engine.ocr_image(dummy_img)
    assert "Loi nhuan sau thue" in text
    assert "15.000.000.000 VND" in text
    assert conf == pytest.approx(0.95, 0.01)


def test_ocr_image_empty():
    mock_ocr = MagicMock()
    mock_ocr.predict.return_value = [{"rec_texts": [], "rec_scores": []}]
    engine = PaddleOCREngine(ocr_engine=mock_ocr)
    dummy_img = np.ones((50, 50, 3), dtype=np.uint8) * 255

    text, conf = engine.ocr_image(dummy_img)
    assert text == ""
    assert conf == 0.0


def test_analyze_layout_filtering():
    mock_struct = MagicMock()
    mock_struct.predict.return_value = [
        {"type": "header", "bbox": [0, 0, 500, 50], "res": [{"text": "Page Header", "confidence": 0.99}]},
        {"type": "title", "bbox": [50, 60, 450, 100], "res": [{"text": "BANG CAN DOI KE TOAN", "confidence": 0.98}]},
        {"type": "table", "bbox": [50, 110, 450, 300], "res": {"html": "<table><tr><td>Data</td></tr></table>", "text": "Cell Data"}},
        {"type": "footer", "bbox": [0, 450, 500, 500], "res": [{"text": "Trang 1 / 10", "confidence": 0.99}]},
        {"type": "seal", "bbox": [350, 320, 450, 420], "res": [{"text": "DA DONG DAU", "confidence": 0.85}]},
    ]
    engine = PaddleOCREngine(structure_engine=mock_struct)
    dummy_img = np.ones((500, 500, 3), dtype=np.uint8) * 255

    regions = engine.analyze_layout(dummy_img)
    assert len(regions) == 5

    # Check included vs excluded
    header_reg = next(r for r in regions if r.region_type == "header")
    assert header_reg.included is False

    title_reg = next(r for r in regions if r.region_type == "title")
    assert title_reg.included is True
    assert title_reg.text == "BANG CAN DOI KE TOAN"

    table_reg = next(r for r in regions if r.region_type == "table")
    assert table_reg.included is True
    assert "<table>" in table_reg.html

    footer_reg = next(r for r in regions if r.region_type == "footer")
    assert footer_reg.included is False

    seal_reg = next(r for r in regions if r.region_type == "seal")
    assert seal_reg.included is False


def test_ocr_with_layout_reading_order_and_fallback():
    # Test 1: Layout detected with multiple blocks
    mock_struct = MagicMock()
    mock_struct.predict.return_value = [
        {"type": "title", "bbox": [50, 30, 400, 80], "res": [{"text": "PHAN I: TAI SAN", "confidence": 0.95}]},
        {"type": "header", "bbox": [0, 0, 500, 25], "res": [{"text": "Mau B01-DN", "confidence": 0.99}]},  # Noise
        {"type": "text", "bbox": [50, 90, 400, 150], "res": [{"text": "Tien mat: 100 ty", "confidence": 0.92}]},
    ]
    engine = PaddleOCREngine(structure_engine=mock_struct)
    dummy_img = np.ones((200, 500, 3), dtype=np.uint8) * 255

    merged_text, avg_conf, all_regions = engine.ocr_with_layout(dummy_img)
    assert len(all_regions) == 3
    # Header should be excluded
    assert "Mau B01-DN" not in merged_text
    # Title and text should be included in reading order
    assert "PHAN I: TAI SAN" in merged_text
    assert "Tien mat: 100 ty" in merged_text
    assert avg_conf > 0.90

    # Test 2: Fallback when 0 layout regions detected
    mock_struct_empty = MagicMock()
    mock_struct_empty.predict.return_value = []
    mock_ocr = MagicMock()
    mock_ocr.predict.return_value = [{"rec_texts": ["FALLBACK FULL PAGE OCR"], "rec_scores": [0.88]}]

    engine2 = PaddleOCREngine(ocr_engine=mock_ocr, structure_engine=mock_struct_empty)
    merged2, conf2, regions2 = engine2.ocr_with_layout(dummy_img)
    assert merged2 == "FALLBACK FULL PAGE OCR"
    assert conf2 == pytest.approx(0.88)
    assert len(regions2) == 1
    assert regions2[0].included is True


def test_parse_ocr_raw_result_mixed_boxed_and_unboxed():
    """Verify items without bounding boxes are NOT dropped when others have boxes."""
    engine = PaddleOCREngine()
    raw = [
        {
            "rec_texts": ["TAI SAN NGAN HAN", "450.000.000.000", "Ghi chu bo sung"],
            "rec_scores": [0.98, 0.95, 0.90],
            "rec_boxes": [
                [50, 100, 200, 120],  # valid bbox
                [350, 100, 500, 120],  # valid bbox on same line
                None,  # unboxed item!
            ],
        }
    ]
    texts, scores = engine._parse_ocr_raw_result(raw)
    assert len(texts) == 2
    # First line contains clustered boxed items
    assert "TAI SAN NGAN HAN\t450.000.000.000" in texts[0]
    # Second line preserves unboxed item without data loss
    assert texts[1] == "Ghi chu bo sung"
    assert scores[1] == pytest.approx(0.90)


def test_parse_ocr_raw_result_malformed_empty_none():
    """Verify empty, None, and malformed inputs are handled gracefully without exceptions."""
    engine = PaddleOCREngine()
    assert engine._parse_ocr_raw_result(None) == ([], [])
    assert engine._parse_ocr_raw_result([]) == ([], [])
    assert engine._parse_ocr_raw_result([None]) == ([], [])
    assert engine._parse_ocr_raw_result([{}]) == ([], [])
    # Unsupported primitive type sets last_error and returns gracefully
    res_texts, res_scores = engine._parse_ocr_raw_result(12345)
    assert res_texts == []
    assert res_scores == []
    assert engine.last_error is not None


def test_parse_ocr_raw_result_confidence_sanitization():
    """Verify confidence scores from varied formats (0-100 scale, NaN, strings) are normalized."""
    engine = PaddleOCREngine()
    assert engine._sanitize_confidence(0.95) == 0.95
    assert engine._sanitize_confidence("0.85") == 0.85
    # 0-100 scale normalized
    assert engine._sanitize_confidence(95.0) == 0.95
    # None defaults to 1.0
    assert engine._sanitize_confidence(None) == 1.0
    # NaN and invalid strings default to 0.0
    assert engine._sanitize_confidence(float("nan")) == 0.0
    assert engine._sanitize_confidence("invalid_conf") == 0.0
    assert engine._sanitize_confidence(-0.5) == 0.0


def test_parse_ocr_raw_result_invalid_and_out_of_bounds_bbox():
    """Verify invalid bounding boxes (NaN, inverted, degenerated) are handled safely."""
    engine = PaddleOCREngine()
    # NaN in bbox
    assert engine._extract_valid_bbox([float("nan"), 10, 50, 100]) is None
    # Inverted coordinates get normalized if valid area
    box = engine._extract_valid_bbox([100, 50, 20, 10])  # xmin=20, xmax=100, ymin=10, ymax=50
    assert box is not None
    ymin, xmin, ymax, xmax = box
    assert ymin == 10 and ymax == 50 and xmin == 20 and xmax == 100
    # Zero area / degenerated line
    assert engine._extract_valid_bbox([10, 10, 10, 10]) is None


def test_cluster_boxes_into_lines_differing_heights_and_multi_column():
    """Verify multi-column table clustering with different row font heights and spacing."""
    engine = PaddleOCREngine()

    # Row 1: Header with 25px height (y: 100..125)
    # Row 2: Close financial row with 15px height (y: 130..145) - 5px gap, no vertical overlap
    items = [
        ((100, 50, 125, 200), "CHỈ TIÊU BÁO CÁO", 0.99),
        ((100, 300, 125, 350), "MÃ SỐ", 0.98),
        ((100, 450, 125, 600), "SỐ CUỐI NĂM", 0.97),
        ((130, 50, 145, 220), "Tiền và tương đương tiền", 0.96),
        ((130, 300, 145, 330), "110", 0.99),
        ((130, 450, 145, 580), "15.000.000.000", 0.94),
    ]

    texts, scores = engine._cluster_boxes_into_lines(items)
    assert len(texts) == 2
    # Row 1: Header row columns separated by tab
    assert "CHỈ TIÊU BÁO CÁO\tMÃ SỐ\tSỐ CUỐI NĂM" in texts[0]
    # Row 2: Data row columns separated by tab
    assert "Tiền và tương đương tiền\t110\t15.000.000.000" in texts[1]
    assert len(scores) == 2


def test_cluster_boxes_into_lines_order_independence():
    """Verify output is identical regardless of input bounding box ordering."""
    engine = PaddleOCREngine()
    items = [
        ((100, 50, 120, 150), "Doanh thu", 0.95),
        ((100, 300, 120, 400), "100 tỷ", 0.90),
        ((150, 50, 170, 150), "Lợi nhuận", 0.92),
        ((150, 300, 170, 400), "10 tỷ", 0.91),
    ]
    texts_forward, _ = engine._cluster_boxes_into_lines(items)
    # Reverse input order
    texts_reversed, _ = engine._cluster_boxes_into_lines(items[::-1])
    assert texts_forward == texts_reversed
    assert "Doanh thu\t100 tỷ" in texts_forward[0]
    assert "Lợi nhuận\t10 tỷ" in texts_forward[1]


def test_analyze_layout_engine_failure_vs_empty():
    """Verify differentiation between layout engine exception and zero detected regions."""
    mock_struct_failing = MagicMock()
    mock_struct_failing.predict.side_effect = RuntimeError("GPU out of memory simulation")

    engine = PaddleOCREngine(structure_engine=mock_struct_failing)
    dummy_img = np.ones((100, 100, 3), dtype=np.uint8) * 255

    # Should not raise; records layout_status = 'failed'
    regions = engine.analyze_layout(dummy_img)
    assert regions == []
    assert engine.layout_status == "failed"
    assert "GPU out of memory" in engine.last_error

    # Fallback in ocr_with_layout works gracefully
    mock_ocr = MagicMock()
    mock_ocr.predict.return_value = [{"rec_texts": ["FALLBACK TEXT"], "rec_scores": [0.9]}]
    engine._ocr_engine = mock_ocr
    text, conf, all_regs = engine.ocr_with_layout(dummy_img)
    assert text == "FALLBACK TEXT"
    assert len(all_regs) == 1


def test_analyze_layout_preserves_financial_headers():
    """Verify headers containing currency units or financial statements are preserved."""
    mock_struct = MagicMock()
    mock_struct.predict.return_value = [
        {
            "type": "header",
            "bbox": [0, 0, 500, 40],
            "res": [{"text": "BÁO CÁO TÀI CHÍNH (Đơn vị tính: VNĐ)", "confidence": 0.98}],
        },
        {
            "type": "footer",
            "bbox": [0, 460, 500, 500],
            "res": [{"text": "Trang 1 / 15", "confidence": 0.99}],
        },
    ]
    engine = PaddleOCREngine(structure_engine=mock_struct)
    dummy_img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    regions = engine.analyze_layout(dummy_img)

    header_reg = next(r for r in regions if r.region_type == "header")
    assert header_reg.included is True  # Preserved because it contains 'Đơn vị tính: VNĐ'

    footer_reg = next(r for r in regions if r.region_type == "footer")
    assert footer_reg.included is False  # Excluded because it's purely 'Trang 1 / 15'


def test_singleton_configuration_isolation_and_reset():
    """Verify singleton returns distinct instances for differing configs and supports safe reset."""
    reset_shared_paddle_engine()

    engine_vi = get_shared_paddle_engine(lang="vi", use_gpu=False)
    engine_en = get_shared_paddle_engine(lang="en", use_gpu=False)
    assert engine_vi is not engine_en
    assert engine_vi.lang == "vi"
    assert engine_en.lang == "en"

    # Same config returns exact same instance
    engine_vi_again = get_shared_paddle_engine(lang="vi", use_gpu=False)
    assert engine_vi_again is engine_vi

    # Reset cleans all singletons
    reset_shared_paddle_engine()
    engine_vi_new = get_shared_paddle_engine(lang="vi", use_gpu=False)
    assert engine_vi_new is not engine_vi

