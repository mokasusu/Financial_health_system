"""Unit tests for PDFExtractor pipeline."""
import io
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from PIL import Image, ImageDraw
import pymupdf

from src.ocr.models import ExtractionMethod
from src.ocr.pdf_extractor import PDFExtractor
from src.ocr.tesseract_engine import TesseractEngine, TesseractExecutionError


@pytest.fixture
def native_pdf_path(tmp_path: Path) -> Path:
    """Create a 2-page PDF document with rich native text."""
    pdf_file = tmp_path / "native_report.pdf"
    doc = pymupdf.open()

    # Page 1: Balance sheet text
    page1 = doc.new_page(width=595, height=842)
    text1 = (
        "CONG TY CO PHAN 32\n"
        "BANG CAN DOI KE TOAN TAI NGAY 31 THANG 12 NAM 2020\n"
        "TAI SAN NGAN HAN: 450.000.000.000 VND\n"
        "Tien va cac khoan tuong duong tien: 50.000.000.000 VND\n"
        "Dau tu tai chinh ngan han: 20.000.000.000 VND\n"
        "Cac khoan phai thu ngan han: 180.000.000.000 VND\n"
    )
    page1.insert_text((50, 50), text1, fontsize=12)

    # Page 2: Income statement text
    page2 = doc.new_page(width=595, height=842)
    text2 = (
        "BAO CAO KET QUA HOAT DONG KINH DOANH NAM 2020\n"
        "1. Doanh thu ban hang va cung cap dich vu: 650.000.000.000 VND\n"
        "2. Cac khoan giam tru doanh thu: 0 VND\n"
        "3. Doanh thu thuan ve ban hang: 650.000.000.000 VND\n"
        "4. Gia von hang ban: 520.000.000.000 VND\n"
        "5. Loi nhuan gop ve ban hang: 130.000.000.000 VND\n"
    )
    page2.insert_text((50, 50), text2, fontsize=12)

    doc.save(str(pdf_file))
    doc.close()
    return pdf_file


@pytest.fixture
def scanned_pdf_path(tmp_path: Path) -> Path:
    """Create a 1-page PDF containing only an embedded raster image (no text layer)."""
    pdf_file = tmp_path / "scanned_report.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # Create synthetic image with text drawn onto pixels
    img = Image.new("RGB", (600, 300), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 50), "TONG CONG TAI SAN: 800 TY DONG", fill="black")

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Insert image into page (no native text)
    rect = pymupdf.Rect(50, 50, 545, 300)
    page.insert_image(rect, stream=img_bytes.getvalue())

    doc.save(str(pdf_file))
    doc.close()
    return pdf_file


@pytest.fixture
def hybrid_pdf_path(tmp_path: Path) -> Path:
    """Create a 3-page PDF: Page 1 native, Page 2 scanned image, Page 3 completely empty."""
    pdf_file = tmp_path / "hybrid_report.pdf"
    doc = pymupdf.open()

    # Page 1: Native text
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(
        (50, 50),
        "BAO CAO TAI CHINH KIEM TOAN NAM 2020\n"
        "Noi dung day du voi hon 50 ky tu de vuot qua nguong native text.\n"
        "Tong loi nhuan sau thue thu nhap doanh nghiep dat muc cao.",
        fontsize=12,
    )

    # Page 2: Scanned image only
    p2 = doc.new_page(width=595, height=842)
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "SCANNED PAGE 2 DATA", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    p2.insert_image(pymupdf.Rect(50, 50, 450, 150), stream=buf.getvalue())

    # Page 3: Completely blank
    _ = doc.new_page(width=595, height=842)

    doc.save(str(pdf_file))
    doc.close()
    return pdf_file


class TestPDFExtractorUnit:
    """Unit tests for PDFExtractor with controlled mocks."""

    def test_file_not_found(self):
        extractor = PDFExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract("non_existent_bctc_12345.pdf")

    def test_native_text_extraction(self, native_pdf_path: Path):
        # Even with Tesseract disabled, native extraction must succeed
        mock_engine = MagicMock(spec=TesseractEngine)
        mock_engine.is_available.return_value = False

        extractor = PDFExtractor(tesseract_engine=mock_engine, min_native_text_chars=30)
        res = extractor.extract(native_pdf_path)

        assert res.success is True
        assert res.total_pages == 2
        assert len(res.pages) == 2

        # Page 1 checks
        p1 = res.pages[0]
        assert p1.page_number == 1
        assert p1.extraction_method == ExtractionMethod.NATIVE_TEXT.value
        assert "TAI SAN NGAN HAN" in p1.text
        assert p1.success is True

        # Page 2 checks
        p2 = res.pages[1]
        assert p2.page_number == 2
        assert p2.extraction_method == ExtractionMethod.NATIVE_TEXT.value
        assert "Doanh thu thuan" in p2.text

        assert res.has_native_pages is True
        assert res.has_ocr_pages is False
        assert mock_engine.ocr_image.call_count == 0

    def test_scanned_page_ocr_fallback(self, scanned_pdf_path: Path):
        mock_engine = MagicMock(spec=TesseractEngine)
        mock_engine.is_available.return_value = True
        mock_engine.ocr_image.return_value = "TONG CONG TAI SAN: 800 TY DONG\n"

        extractor = PDFExtractor(tesseract_engine=mock_engine, min_native_text_chars=50)
        res = extractor.extract(scanned_pdf_path)

        assert res.success is True
        assert res.total_pages == 1
        assert len(res.pages) == 1

        p1 = res.pages[0]
        assert p1.page_number == 1
        assert p1.extraction_method == ExtractionMethod.OCR.value
        assert "TONG CONG TAI SAN" in p1.text
        assert res.has_ocr_pages is True
        assert mock_engine.ocr_image.call_count == 1

    def test_hybrid_document_classification(self, hybrid_pdf_path: Path):
        mock_engine = MagicMock(spec=TesseractEngine)
        mock_engine.is_available.return_value = True
        # Page 2 returns OCR text, Page 3 returns empty
        mock_engine.ocr_image.side_effect = ["SCANNED PAGE 2 DATA", "   "]

        extractor = PDFExtractor(tesseract_engine=mock_engine, min_native_text_chars=50)
        res = extractor.extract(hybrid_pdf_path)

        assert res.total_pages == 3
        assert len(res.pages) == 3

        # Strictly check page numbering order
        assert [p.page_number for p in res.pages] == [1, 2, 3]

        # Check classification per page
        assert res.pages[0].extraction_method == ExtractionMethod.NATIVE_TEXT.value
        assert res.pages[1].extraction_method == ExtractionMethod.OCR.value
        assert res.pages[2].extraction_method == ExtractionMethod.EMPTY.value

        assert res.has_native_pages is True
        assert res.has_ocr_pages is True

    def test_corrupted_file_handling(self):
        extractor = PDFExtractor()
        corrupted_bytes = b"NOT_A_VALID_PDF_HEADER"
        res = extractor.extract(corrupted_bytes, source_name="corrupted.pdf")

        assert res.success is False
        assert res.total_pages == 0
        assert len(res.errors) > 0

    def test_standalone_image_extraction(self, tmp_path: Path):
        img_path = tmp_path / "receipt_sample.png"
        img = Image.new("RGB", (200, 100), color="white")
        img.save(img_path)

        mock_engine = MagicMock(spec=TesseractEngine)
        mock_engine.is_available.return_value = True
        mock_engine.ocr_image.return_value = "Hoa don gia tri gia tang"

        extractor = PDFExtractor(tesseract_engine=mock_engine)
        res = extractor.extract(img_path)

        assert res.success is True
        assert res.total_pages == 1
        assert res.pages[0].extraction_method == ExtractionMethod.OCR.value
        assert "Hoa don" in res.pages[0].text

    def test_ocr_execution_failure_handling(self, scanned_pdf_path: Path):
        mock_engine = MagicMock(spec=TesseractEngine)
        mock_engine.is_available.return_value = True
        mock_engine.ocr_image.side_effect = TesseractExecutionError("Engine crashed")

        extractor = PDFExtractor(tesseract_engine=mock_engine, min_native_text_chars=50)
        res = extractor.extract(scanned_pdf_path)

        # Extraction should not crash; page should record the warning/failure
        assert len(res.pages) == 1
        p1 = res.pages[0]
        assert p1.extraction_method == ExtractionMethod.FAILED.value
        assert p1.success is False
        assert any("OCR execution failed" in w for w in p1.warnings)


class TestPDFExtractorRealSmoke:
    """Smoke test running end-to-end extraction against real PDF fixtures."""

    def test_native_pdf_real_extraction(self, native_pdf_path: Path):
        extractor = PDFExtractor(min_native_text_chars=30)
        res = extractor.extract(native_pdf_path)

        assert res.success is True
        assert res.total_pages == 2
        assert "CONG TY CO PHAN 32" in res.full_text
        assert res.processing_time_seconds > 0

    def test_scanned_pdf_real_tesseract_smoke(self, scanned_pdf_path: Path):
        engine = TesseractEngine()
        if not engine.is_available():
            pytest.skip("Real Tesseract engine not available for end-to-end smoke test.")

        extractor = PDFExtractor(tesseract_engine=engine, min_native_text_chars=50)
        res = extractor.extract(scanned_pdf_path)

        assert res.total_pages == 1
        assert res.pages[0].extraction_method == ExtractionMethod.OCR.value
        # Real OCR extracted string should be non-empty
        assert len(res.pages[0].text) > 0
