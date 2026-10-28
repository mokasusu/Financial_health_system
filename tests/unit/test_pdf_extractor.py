"""Unit tests for PDFExtractor 3-route pipeline using PaddleOCR exclusively."""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image, ImageDraw
import pymupdf

from src.application.services.parsing_service import FinancialStatementParser
from src.domain.accounting.validator import FinancialValidator
from src.domain.models.ocr import (
    DocumentExtractionResult,
    ExtractionMethod,
    ExtractionStatus,
    LayoutRegion,
    PageExtractionResult,
)
from src.domain.ratios.engine import FinancialRatioCalculator
from src.infrastructure.ocr.paddle_engine import PaddleOCREngine
from src.infrastructure.pdf.extractor import PDFExtractor


@pytest.fixture
def native_pdf_path(tmp_path: Path) -> Path:
    """Create a 2-page PDF document with rich native text and financial tables."""
    pdf_file = tmp_path / "native_report.pdf"
    doc = pymupdf.open()

    # Page 1: Balance sheet text
    page1 = doc.new_page(width=595, height=842)
    text1 = (
        "CONG TY CO PHAN 32\n"
        "BANG CAN DOI KE TOAN TAI NGAY 31 THANG 12 NAM 2020\n"
        "Don vi tinh: VND\n"
        "TAI SAN NGAN HAN\t100\t450.000.000.000\t400.000.000.000\n"
        "Tien va tuong duong tien\t110\t50.000.000.000\t40.000.000.000\n"
        "Dau tu tai chinh ngan han\t120\t20.000.000.000\t20.000.000.000\n"
        "Cac khoan phai thu ngan han\t130\t180.000.000.000\t150.000.000.000\n"
        "TAI SAN DAI HAN\t200\t350.000.000.000\t300.000.000.000\n"
        "TONG CONG TAI SAN\t270\t800.000.000.000\t700.000.000.000\n"
        "NO PHAI TRA\t300\t300.000.000.000\t250.000.000.000\n"
        "VON CHU SO HUU\t400\t500.000.000.000\t450.000.000.000\n"
        "TONG CONG NGUON VON\t440\t800.000.000.000\t700.000.000.000\n"
    )
    page1.insert_text((50, 50), text1, fontsize=12)

    # Page 2: Income statement text
    page2 = doc.new_page(width=595, height=842)
    text2 = (
        "BAO CAO KET QUA HOAT DONG KINH DOANH NAM 2020\n"
        "Don vi tinh: VND\n"
        "Doanh thu ban hang va CCDV\t01\t650.000.000.000\t600.000.000.000\n"
        "Doanh thu thuan\t10\t650.000.000.000\t600.000.000.000\n"
        "Gia von hang ban\t11\t520.000.000.000\t480.000.000.000\n"
        "Loi nhuan gop\t20\t130.000.000.000\t120.000.000.000\n"
        "Chi phi tai chinh\t22\t10.000.000.000\t8.000.000.000\n"
        "Chi phi quan ly doanh nghiep\t26\t40.000.000.000\t35.000.000.000\n"
        "Loi nhuan thuan tu HDKD\t30\t80.000.000.000\t77.000.000.000\n"
        "Tong loi nhuan ke toan truoc thue\t50\t80.000.000.000\t77.000.000.000\n"
        "Loi nhuan sau thue TNDN\t60\t64.000.000.000\t61.600.000.000\n"
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

    img = Image.new("RGB", (600, 300), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 50), "TONG CONG TAI SAN: 800 TY DONG", fill="black")

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    rect = pymupdf.Rect(50, 50, 545, 300)
    page.insert_image(rect, stream=img_bytes.getvalue())

    doc.save(str(pdf_file))
    doc.close()
    return pdf_file


@pytest.fixture
def mixed_page_pdf_path(tmp_path: Path) -> Path:
    """Create a 1-page PDF with native headings (> 50 chars) and an embedded scanned table."""
    pdf_file = tmp_path / "mixed_page_report.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # Native text header (> 50 chars, but purely organizational text with NO financial table numbers)
    heading_text = (
        "CONG TY CO PHAN SAN XUAT THUONG MAI MAY 32\n"
        "BAO CAO TAI CHINH KIEM TOAN THEO THONG TU 200/2014/TT-BTC\n"
        "Dia chi: So 123 Duong Nguyen Hue, Quan 1, Thanh pho Ho Chi Minh\n"
        "Giay chung nhan dang ky doanh nghiep so: 0301234567\n"
    )
    page.insert_text((50, 40), heading_text, fontsize=11)

    # Embedded raster image representing a scanned financial statement table
    img = Image.new("RGB", (500, 260), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "TAI SAN NGAN HAN    100    450.000.000.000", fill="black")
    draw.text((20, 50), "Tien va tuong duong tien    110    50.000.000.000", fill="black")
    draw.text((20, 80), "TONG CONG TAI SAN    270    800.000.000.000", fill="black")

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    # Significant image occupying table area
    page.insert_image(pymupdf.Rect(50, 160, 550, 460), stream=img_bytes.getvalue())

    doc.save(str(pdf_file))
    doc.close()
    return pdf_file


class TestPDFExtractorThreeRoutes:
    """Comprehensive tests for Route A, Route B, and Route C extraction."""

    def test_file_not_found(self):
        extractor = PDFExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract("non_existent_file_123456789.pdf")

    def test_route_a_native_text_pdf(self, native_pdf_path: Path):
        """Route A: Vector PDF with complete financial text must not invoke OCR."""
        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True

        extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=50)
        res = extractor.extract(native_pdf_path)

        assert res.success is True
        assert res.status == ExtractionStatus.COMPLETE
        assert res.total_pages == 2
        assert res.has_native_pages is True
        assert res.has_ocr_pages is False

        # Verify OCR engine was NEVER invoked for Route A
        assert mock_paddle.ocr_with_layout.call_count == 0

        # Page 1 verification
        p1 = res.pages[0]
        assert p1.page_number == 1
        assert p1.extraction_method == ExtractionMethod.NATIVE_TEXT.value
        assert p1.status == ExtractionStatus.COMPLETE
        assert "TAI SAN NGAN HAN" in p1.text
        assert "800.000.000.000" in p1.text
        assert p1.ocr_confidence == 1.0
        assert len(p1.layout_regions) > 0
        assert all(r.source_method == "pymupdf_native" for r in p1.layout_regions)
        assert "Native text extraction" in (p1.routing_reason or "")

        # Page 2 verification
        p2 = res.pages[1]
        assert p2.page_number == 2
        assert p2.extraction_method == ExtractionMethod.NATIVE_TEXT.value
        assert "Doanh thu thuan" in p2.text
        assert p2.status == ExtractionStatus.COMPLETE

    def test_route_b_scanned_pdf(self, scanned_pdf_path: Path):
        """Route B: Raster scan PDF must route to PaddleOCR and populate regions/confidence."""
        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True

        mock_region = LayoutRegion(
            region_type="text",
            bbox=(30, 50, 550, 90),
            confidence=0.965,
            text="TONG CONG TAI SAN: 800 TY DONG",
            included=True,
        )
        mock_paddle.ocr_with_layout.return_value = (
            "TONG CONG TAI SAN: 800 TY DONG\n",
            0.965,
            [mock_region],
        )

        extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=50)
        res = extractor.extract(scanned_pdf_path)

        assert res.success is True
        assert res.total_pages == 1
        assert res.has_ocr_pages is True

        # Exactly 1 call to PaddleOCR for the single scanned page
        assert mock_paddle.ocr_with_layout.call_count == 1

        p1 = res.pages[0]
        assert p1.extraction_method == ExtractionMethod.PADDLE_OCR.value
        assert p1.status == ExtractionStatus.COMPLETE
        assert "800 TY DONG" in p1.text
        assert p1.ocr_confidence == pytest.approx(0.965)
        assert len(p1.layout_regions) == 1
        assert "Scanned page" in (p1.routing_reason or "")

    def test_route_c_mixed_pdf_does_not_bypass_ocr(self, mixed_page_pdf_path: Path):
        """Route C: Native text > 50 chars must NOT bypass OCR when table is in scanned image."""
        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True

        scanned_table_ocr = (
            "TAI SAN NGAN HAN\t100\t450.000.000.000\n"
            "Tien va tuong duong tien\t110\t50.000.000.000\n"
            "TONG CONG TAI SAN\t270\t800.000.000.000"
        )
        scanned_region = LayoutRegion(
            region_type="table",
            bbox=(50, 160, 550, 460),
            confidence=0.94,
            text=scanned_table_ocr,
            included=True,
        )
        mock_paddle.ocr_with_layout.return_value = (
            scanned_table_ocr,
            0.94,
            [scanned_region],
        )

        extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=40)
        res = extractor.extract(mixed_page_pdf_path)

        assert res.success is True
        assert res.total_pages == 1

        p1 = res.pages[0]
        # Route C must be classified as HYBRID extraction
        assert p1.extraction_method == ExtractionMethod.HYBRID.value
        assert p1.status == ExtractionStatus.COMPLETE
        assert "Mixed content detected" in (p1.routing_reason or "")

        # PaddleOCR MUST have been executed to recover the missing table content
        assert mock_paddle.ocr_with_layout.call_count >= 1

        # Both native header and scanned table rows must be merged
        assert "CONG TY CO PHAN SAN XUAT THUONG MAI MAY 32" in p1.text
        assert "450.000.000.000" in p1.text
        assert "800.000.000.000" in p1.text

        # Provenance check: layout_regions must contain both native and OCR origins
        source_methods = {r.source_method for r in p1.layout_regions if r.source_method}
        assert "pymupdf_native" in source_methods
        assert any("paddle_ocr" in sm for sm in source_methods)

    def test_deduplication_between_native_and_ocr(self, tmp_path: Path):
        """Deduplication: Duplicate lines between native text and OCR must not be repeated."""
        pdf_file = tmp_path / "dup_test.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)

        # Native header
        native_header = "CONG TY CP THUC PHAM VIET NAM\nBANG CAN DOI KE TOAN\n"
        page.insert_text((50, 40), native_header, fontsize=12)

        # Embedded image
        img = Image.new("RGB", (400, 200), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page.insert_image(pymupdf.Rect(50, 150, 450, 350), stream=buf.getvalue())
        doc.save(str(pdf_file))
        doc.close()

        # PaddleOCR returns duplicate header + new table rows
        ocr_text_with_dup = (
            "CONG TY CP THUC PHAM VIET NAM\n"  # Duplicate
            "BANG CAN DOI KE TOAN\n"            # Duplicate
            "TAI SAN NGAN HAN: 100.000.000.000 VND\n"  # Novel numeric row
            "TIEN MAT: 10.000.000.000 VND"             # Novel numeric row
        )
        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True
        mock_paddle.ocr_with_layout.return_value = (ocr_text_with_dup, 0.95, [])

        extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=30)
        res = extractor.extract(pdf_file)

        merged = res.pages[0].text
        # Header should appear exactly ONCE
        assert merged.count("CONG TY CP THUC PHAM VIET NAM") == 1
        assert merged.count("BANG CAN DOI KE TOAN") == 1

        # Novel numeric values MUST be retained
        assert "100.000.000.000 VND" in merged
        assert "10.000.000.000 VND" in merged

    def test_standalone_image_extraction(self, tmp_path: Path):
        """Standalone image directly routed through PaddleOCR pipeline."""
        img_path = tmp_path / "invoice.png"
        img = Image.new("RGB", (300, 150), color="white")
        img.save(img_path)

        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True
        region = LayoutRegion(
            region_type="table",
            bbox=(10, 10, 290, 140),
            confidence=0.97,
            text="Hoa don GTGT",
            included=True,
        )
        mock_paddle.ocr_with_layout.return_value = ("Hoa don GTGT: 50.000.000 VND", 0.97, [region])

        extractor = PDFExtractor(paddle_engine=mock_paddle)
        res = extractor.extract(img_path)

        assert res.success is True
        assert res.total_pages == 1
        assert res.pages[0].extraction_method == ExtractionMethod.PADDLE_OCR.value
        assert res.pages[0].status == ExtractionStatus.COMPLETE
        assert "50.000.000 VND" in res.pages[0].text
        assert res.pages[0].ocr_confidence == pytest.approx(0.97)

    def test_corrupted_pdf_handling(self):
        """Corrupted PDF returns structured FAILED result without unhandled exception."""
        extractor = PDFExtractor()
        corrupted_bytes = b"%PDF-1.4 CORRUPTED INVALID GARBAGE DATA 00000"
        res = extractor.extract(corrupted_bytes, source_name="corrupt.pdf")

        assert res.success is False
        assert res.status == ExtractionStatus.FAILED
        assert res.total_pages == 0
        assert len(res.errors) > 0
        assert any("Corrupted or invalid PDF" in err for err in res.errors)

    def test_empty_pdf_handling(self, tmp_path: Path):
        """Empty PDF with blank page returns structured EMPTY result."""
        empty_pdf = tmp_path / "empty.pdf"
        doc = pymupdf.open()
        _ = doc.new_page(width=595, height=842)
        doc.save(str(empty_pdf))
        doc.close()

        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True
        mock_paddle.ocr_with_layout.return_value = ("", 0.0, [])

        extractor = PDFExtractor(paddle_engine=mock_paddle)
        res = extractor.extract(empty_pdf)

        assert res.success is True
        assert res.status == ExtractionStatus.EMPTY
        assert res.total_pages == 1
        assert res.pages[0].status == ExtractionStatus.EMPTY
        assert res.pages[0].extraction_method == ExtractionMethod.EMPTY.value

    def test_ocr_execution_failure_handling(self, scanned_pdf_path: Path):
        """OCR engine exception returns FAILED status and error details without crash."""
        mock_paddle = MagicMock(spec=PaddleOCREngine)
        mock_paddle.is_available.return_value = True
        mock_paddle.ocr_with_layout.side_effect = RuntimeError("Paddle internal CUDA memory error")

        extractor = PDFExtractor(paddle_engine=mock_paddle, min_native_text_chars=50)
        res = extractor.extract(scanned_pdf_path)

        assert len(res.pages) == 1
        p1 = res.pages[0]
        assert p1.extraction_method == ExtractionMethod.FAILED.value
        assert p1.status == ExtractionStatus.FAILED
        assert p1.success is False
        assert "Paddle internal CUDA memory error" in (p1.error_details or "")
        assert any("OCR execution failed" in w for w in p1.warnings)

    def test_no_production_path_invokes_tesseract(self, native_pdf_path: Path, scanned_pdf_path: Path):
        """Verify Tesseract is completely decoupled and never imported or invoked."""
        import sys
        import src.infrastructure.pdf.extractor as pe_mod

        # Verify tesseract is not imported in pdf_extractor module
        assert "TesseractEngine" not in pe_mod.__dict__
        assert "tesseract_engine" not in pe_mod.__dict__

        # Verify constructor has no tesseract parameters
        import inspect
        sig = inspect.signature(PDFExtractor.__init__)
        assert "tesseract_engine" not in sig.parameters

        # Verify legacy method does not exist
        assert not hasattr(PDFExtractor, "_resolve_legacy_lang")

        # Mock pytesseract if present to guarantee it cannot be called
        with patch.dict(sys.modules, {"pytesseract": None}):
            mock_paddle = MagicMock(spec=PaddleOCREngine)
            mock_paddle.is_available.return_value = True
            mock_paddle.ocr_with_layout.return_value = ("Scanned content", 0.95, [])

            extractor = PDFExtractor(paddle_engine=mock_paddle)
            res_native = extractor.extract(native_pdf_path)
            res_scanned = extractor.extract(scanned_pdf_path)

            assert res_native.success is True
            assert res_scanned.success is True

    def test_downstream_end_to_end_compatibility(self, native_pdf_path: Path):
        """Verify output integrates seamlessly with FinancialStatementParser, Validator & Ratios."""
        extractor = PDFExtractor()
        doc_result = extractor.extract(native_pdf_path)

        # 1. Parse via FinancialStatementParser
        parser = FinancialStatementParser()
        report = parser.parse(doc_result)

        assert report.balance_sheet is not None
        assert report.income_statement is not None

        # Verify canonical mapping of Circular 200 items
        bs = report.balance_sheet
        assert float(bs.current_assets) == pytest.approx(450_000_000_000)
        assert float(bs.cash_and_equivalents) == pytest.approx(50_000_000_000)
        assert float(bs.total_assets) == pytest.approx(800_000_000_000)
        assert float(bs.equity) == pytest.approx(500_000_000_000)

        is_ = report.income_statement
        assert float(is_.net_revenue) == pytest.approx(650_000_000_000)
        assert float(is_.gross_profit) == pytest.approx(130_000_000_000)
        assert float(is_.net_profit_after_tax) == pytest.approx(64_000_000_000)

        # 2. Validate via FinancialValidator
        validator = FinancialValidator()
        val_result = validator.validate(report)
        assert val_result.is_valid is True
        assert val_result.passed_checks >= 5
        assert val_result.failed_checks == 0

        # 3. Calculate 14 ratios via FinancialRatioCalculator
        ratio_calc = FinancialRatioCalculator()
        ratio_report = ratio_calc.calculate_all(report)

        cr = ratio_report.get_ratio("current_ratio")
        assert cr is not None
        assert cr.status.value in ("calculated", "not_available", "not_applicable")
