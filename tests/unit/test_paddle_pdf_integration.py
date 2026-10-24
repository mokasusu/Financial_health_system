"""Integration tests for PDFExtractor using PaddleOCREngine, ensuring no OCR duplication."""
import io
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from PIL import Image, ImageDraw
import pymupdf

from src.ocr.image_preprocessor import ImagePreprocessor
from src.ocr.models import ExtractionMethod, LayoutRegion
from src.ocr.paddle_engine import PaddleOCREngine
from src.ocr.pdf_extractor import PDFExtractor


@pytest.fixture
def sample_hybrid_pdf(tmp_path: Path) -> Path:
    """Create a 3-page test PDF:
    Page 1: Rich native text (> 50 chars).
    Page 2: Scanned raster image (no native text).
    Page 3: Blank page.
    """
    pdf_path = tmp_path / "hybrid_doc.pdf"
    doc = pymupdf.open()

    # Page 1: Native text
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(
        (50, 50),
        "CONG TY CO PHAN CONG NGHE TAI CHINH\n"
        "BAO CAO LUU CHUYEN TIEN TE HOP NHAT THEO THONG TU 200/2014/TT-BTC\n"
        "Luu chuyen tien thuan tu hoat dong kinh doanh dat 120.000.000.000 VND.",
        fontsize=12,
    )

    # Page 2: Scanned raster image
    p2 = doc.new_page(width=595, height=842)
    img = Image.new("RGB", (500, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "VAY VA NO THUE TAI CHINH NGAN HAN: 50 TY VND", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    p2.insert_image(pymupdf.Rect(50, 50, 500, 250), stream=buf.getvalue())

    # Page 3: Blank page
    _ = doc.new_page(width=595, height=842)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_no_ocr_overlapping_on_native_page(sample_hybrid_pdf: Path):
    """Verify strictly NO OCR is executed when native text is sufficient."""
    mock_paddle = MagicMock(spec=PaddleOCREngine)
    mock_paddle.is_available.return_value = True

    extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=40)
    res = extractor.extract(sample_hybrid_pdf)

    # Page 1 (Native)
    p1 = res.pages[0]
    assert p1.extraction_method == ExtractionMethod.NATIVE_TEXT.value
    assert "BAO CAO LUU CHUYEN TIEN TE" in p1.text

    # Verify that mock_paddle.ocr_with_layout was NOT called for page 1!
    # Page 2 was scanned (so called once), Page 3 was blank (so called once).
    # Crucially, total calls must be 2 (pages 2 and 3), NEVER 3 (page 1 skipped OCR entirely).
    assert mock_paddle.ocr_with_layout.call_count == 2


def test_paddle_ocr_route_page_and_regions(sample_hybrid_pdf: Path):
    """Verify Route B extracts via PaddleOCR and populates layout_regions and ocr_confidence."""
    mock_paddle = MagicMock(spec=PaddleOCREngine)
    mock_paddle.is_available.return_value = True

    # Page 2 OCR returns text and regions; Page 3 returns empty
    region_p2 = LayoutRegion(
        region_type="text",
        bbox=(50, 50, 500, 250),
        confidence=0.975,
        text="VAY VA NO THUE TAI CHINH NGAN HAN: 50 TY VND",
        included=True,
    )
    mock_paddle.ocr_with_layout.side_effect = [
        ("VAY VA NO THUE TAI CHINH NGAN HAN: 50 TY VND", 0.975, [region_p2]),
        ("", 0.0, []),
    ]

    extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=40)
    res = extractor.extract(sample_hybrid_pdf)

    assert res.success is True
    assert res.total_pages == 3
    assert res.has_native_pages is True
    assert res.has_ocr_pages is True

    # Page 1: Native
    assert res.pages[0].extraction_method == ExtractionMethod.NATIVE_TEXT.value

    # Page 2: PaddleOCR
    p2 = res.pages[1]
    assert p2.extraction_method == ExtractionMethod.PADDLE_OCR.value
    assert "50 TY VND" in p2.text
    assert p2.ocr_confidence == pytest.approx(0.975)
    assert len(p2.layout_regions) == 1
    assert p2.layout_regions[0].region_type == "text"

    # Page 3: Empty
    p3 = res.pages[2]
    assert p3.extraction_method == ExtractionMethod.EMPTY.value
    assert p3.text == ""


def test_standalone_image_paddle_ocr(tmp_path: Path):
    """Verify standalone images route directly to PaddleOCR."""
    img_path = tmp_path / "invoice.png"
    img = Image.new("RGB", (300, 150), color="white")
    img.save(img_path)

    mock_paddle = MagicMock(spec=PaddleOCREngine)
    mock_paddle.is_available.return_value = True
    region = LayoutRegion(
        region_type="table",
        bbox=(10, 10, 290, 140),
        confidence=0.96,
        text="Hoa don GTGT",
        html="<table></table>",
        included=True,
    )
    mock_paddle.ocr_with_layout.return_value = ("Hoa don GTGT", 0.96, [region])

    extractor = PDFExtractor(paddle_engine=mock_paddle)
    res = extractor.extract(img_path)

    assert res.success is True
    assert res.total_pages == 1
    p1 = res.pages[0]
    assert p1.extraction_method == ExtractionMethod.PADDLE_OCR.value
    assert p1.text == "Hoa don GTGT"
    assert p1.ocr_confidence == pytest.approx(0.96)
    assert len(p1.layout_regions) == 1
    assert res.has_ocr_pages is True


def test_paddle_unavailable_graceful_degradation(sample_hybrid_pdf: Path):
    """Verify graceful handling when PaddleOCR is unavailable."""
    mock_paddle = MagicMock(spec=PaddleOCREngine)
    mock_paddle.is_available.return_value = False

    extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=40)
    res = extractor.extract(sample_hybrid_pdf)

    # Page 1 still succeeds via PyMuPDF native
    assert res.pages[0].extraction_method == ExtractionMethod.NATIVE_TEXT.value
    assert res.pages[0].success is True

    # Pages 2 and 3 fail/empty gracefully without crash
    assert res.pages[1].extraction_method == ExtractionMethod.EMPTY.value
    assert any("OCR engine unavailable" in w for w in res.pages[1].warnings)
