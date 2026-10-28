"""Unit tests for hardened OCR data models and schemas (src/ocr/models.py)."""
import json
import pytest
from pydantic import ValidationError

from src.domain.models.ocr import (
    DocumentExtractionResult,
    ExtractionMethod,
    ExtractionStatus,
    LayoutRegion,
    PageExtractionResult,
)


def test_extraction_method_and_status_enums():
    """Verify enum members, string serialization, and backward compatibility."""
    assert ExtractionMethod.NATIVE_TEXT.value == "native_text"
    assert ExtractionMethod.PADDLE_OCR.value == "paddle_ocr"
    assert ExtractionMethod.OCR.value == "ocr"
    assert ExtractionMethod.EMPTY.value == "empty"
    assert ExtractionMethod.FAILED.value == "failed"

    assert ExtractionStatus.COMPLETE.value == "complete"
    assert ExtractionStatus.PARTIAL.value == "partial"
    assert ExtractionStatus.EMPTY.value == "empty"
    assert ExtractionStatus.FAILED.value == "failed"


def test_layout_region_defaults_and_unknown_labels():
    """Verify LayoutRegion supports arbitrary/unknown labels and provenance fields."""
    # Unknown label (e.g. from newer layout detectors)
    region = LayoutRegion(
        region_type="custom_financial_chart_label",
        bbox=(10, 20, 300, 400),
        confidence=0.92,
        text="Doanh thu quy 3",
        source_method="pp_structure_v3",
        needs_review=True,
        review_reason="Borderline confidence score",
    )
    assert region.region_type == "custom_financial_chart_label"
    assert region.bbox == (10, 20, 300, 400)
    assert region.confidence == 0.92
    assert region.included is True
    assert region.needs_review is True
    assert region.review_reason == "Borderline confidence score"
    assert region.source_method == "pp_structure_v3"

    # Validation: confidence must be 0.0 - 1.0
    with pytest.raises(ValidationError):
        LayoutRegion(region_type="text", bbox=(0, 0, 10, 10), confidence=1.5)

    with pytest.raises(ValidationError):
        LayoutRegion(region_type="text", bbox=(0, 0, 10, 10), confidence=-0.1)


def test_page_extraction_result_char_count_logic():
    """Verify char_count auto-computes from text when not set, and does NOT overwrite explicit value."""
    # Auto-computed from text
    p1 = PageExtractionResult(
        source_name="doc.pdf",
        page_number=1,
        text="Bao cao tai chinh",
    )
    assert p1.char_count == len("Bao cao tai chinh")

    # Explicit char_count preserved even if different from len(text)
    p2 = PageExtractionResult(
        source_name="doc.pdf",
        page_number=2,
        text="ABC",
        char_count=100,
    )
    assert p2.char_count == 100

    # Explicit 0 on empty text
    p3 = PageExtractionResult(
        source_name="doc.pdf",
        page_number=3,
        text="",
        char_count=0,
    )
    assert p3.char_count == 0


def test_page_extraction_result_status_inference():
    """Verify semantic status inference (complete, partial, empty, failed) and sync with success."""
    # Complete
    p_comp = PageExtractionResult(
        source_name="doc.pdf",
        page_number=1,
        text="Du lieu tai chinh day du",
        extraction_method=ExtractionMethod.NATIVE_TEXT.value,
    )
    assert p_comp.status == ExtractionStatus.COMPLETE
    assert p_comp.success is True
    assert p_comp.needs_review is False

    # Partial due to warnings
    p_part = PageExtractionResult(
        source_name="doc.pdf",
        page_number=2,
        text="So lieu mo",
        extraction_method=ExtractionMethod.PADDLE_OCR.value,
        warnings=["Low contrast scanned text detected"],
    )
    assert p_part.status == ExtractionStatus.PARTIAL
    assert p_part.success is True
    assert p_part.needs_review is True

    # Partial due to low OCR confidence
    p_low_conf = PageExtractionResult(
        source_name="doc.pdf",
        page_number=3,
        text="Ket qua kinh doanh",
        extraction_method=ExtractionMethod.PADDLE_OCR.value,
        ocr_confidence=0.45,
    )
    assert p_low_conf.status == ExtractionStatus.PARTIAL
    assert p_low_conf.needs_review is True

    # Empty
    p_empty = PageExtractionResult(
        source_name="doc.pdf",
        page_number=4,
        text="",
        extraction_method=ExtractionMethod.EMPTY.value,
    )
    assert p_empty.status == ExtractionStatus.EMPTY
    assert p_empty.success is True

    # Failed
    p_failed = PageExtractionResult(
        source_name="doc.pdf",
        page_number=5,
        text="",
        extraction_method=ExtractionMethod.FAILED.value,
        error_details="Corrupted image raster",
    )
    assert p_failed.status == ExtractionStatus.FAILED
    assert p_failed.success is False


def test_document_extraction_result_aggregation_and_full_text():
    """Verify DocumentExtractionResult status aggregation, provenance, and full_text property."""
    p1 = PageExtractionResult(
        source_name="bctc.pdf",
        page_number=1,
        text="TRANG 1: BANG CAN DOI KE TOAN",
        extraction_method=ExtractionMethod.NATIVE_TEXT.value,
    )
    p2 = PageExtractionResult(
        source_name="bctc.pdf",
        page_number=2,
        text="TRANG 2: KET QUA KINH DOANH",
        extraction_method=ExtractionMethod.PADDLE_OCR.value,
        warnings=["Scan slightly rotated"],
    )
    p3 = PageExtractionResult(
        source_name="bctc.pdf",
        page_number=3,
        text="",
        extraction_method=ExtractionMethod.EMPTY.value,
    )

    doc = DocumentExtractionResult(
        source_name="bctc.pdf",
        total_pages=3,
        pages=[p1, p2, p3],
        has_native_pages=True,
        has_ocr_pages=True,
    )

    # Status aggregated to PARTIAL because p2 had warnings
    assert doc.status == ExtractionStatus.PARTIAL
    assert doc.success is True
    assert doc.needs_review is True

    # full_text joins only non-empty pages with dividers
    expected_full_text = (
        "===== PAGE 1 =====\nTRANG 1: BANG CAN DOI KE TOAN\n\n"
        "===== PAGE 2 =====\nTRANG 2: KET QUA KINH DOANH"
    )
    assert doc.full_text == expected_full_text


def test_document_extraction_result_failed_and_empty():
    """Verify document status when entire document fails or has 0 pages."""
    # Failed document
    doc_failed = DocumentExtractionResult(
        source_name="corrupt.pdf",
        total_pages=0,
        success=False,
        errors=["File header signature corrupt"],
    )
    assert doc_failed.status == ExtractionStatus.FAILED
    assert doc_failed.success is False

    # Empty document
    doc_empty = DocumentExtractionResult(
        source_name="blank.pdf",
        total_pages=0,
        success=True,
    )
    assert doc_empty.status == ExtractionStatus.EMPTY
    assert doc_empty.success is True


def test_legacy_payload_deserialization_compatibility():
    """Verify backward compatibility: deserializing legacy JSON without new fields succeeds cleanly."""
    legacy_page_payload = {
        "source_name": "legacy_doc.pdf",
        "page_number": 1,
        "text": "Tai san: 100 ty",
        "extraction_method": "ocr",
        "warnings": [],
        "success": True,
        "char_count": 15,
        "tables": [],
        "ocr_confidence": 0.95,
        "layout_regions": [
            {
                "region_type": "text",
                "bbox": [10, 10, 200, 50],
                "confidence": 0.95,
                "text": "Tai san: 100 ty",
                "html": "",
                "included": True,
            }
        ],
    }

    # Deserializing legacy page payload
    page = PageExtractionResult.model_validate(legacy_page_payload)
    assert page.source_name == "legacy_doc.pdf"
    assert page.page_number == 1
    assert page.status == ExtractionStatus.COMPLETE
    assert page.needs_review is False
    assert page.routing_reason is None
    assert page.layout_regions[0].source_method is None
    assert page.layout_regions[0].needs_review is False

    # Deserializing legacy document payload
    legacy_doc_payload = {
        "source_name": "legacy_doc.pdf",
        "total_pages": 1,
        "pages": [legacy_page_payload],
        "metadata": {"title": "BCTC 2020"},
        "success": True,
        "has_ocr_pages": True,
        "has_native_pages": False,
        "has_tables": False,
        "processing_time_seconds": 1.25,
        "errors": [],
    }

    doc = DocumentExtractionResult.model_validate(legacy_doc_payload)
    assert doc.status == ExtractionStatus.COMPLETE
    assert doc.success is True
    assert doc.needs_review is False
    assert "Tai san: 100 ty" in doc.full_text


def test_serialization_roundtrip_json():
    """Verify model_dump and model_validate roundtrip with all modern fields."""
    region = LayoutRegion(
        region_type="table",
        bbox=(50, 100, 500, 400),
        confidence=0.98,
        text="Bang can doi ke toan",
        html="<table><tr><td>TS</td></tr></table>",
        source_method="pp_structure",
        needs_review=False,
    )
    page = PageExtractionResult(
        source_name="roundtrip.pdf",
        page_number=1,
        text="A. TAI SAN NGAN HAN\t100\t500.000",
        extraction_method=ExtractionMethod.PADDLE_OCR.value,
        ocr_confidence=0.98,
        layout_regions=[region],
        routing_reason="Insufficient native text fallback",
    )
    doc = DocumentExtractionResult(
        source_name="roundtrip.pdf",
        total_pages=1,
        pages=[page],
        processing_time_seconds=0.85,
    )

    json_str = doc.model_dump_json()
    parsed_data = json.loads(json_str)

    assert parsed_data["status"] == "complete"
    assert parsed_data["pages"][0]["extraction_method"] == "paddle_ocr"
    assert parsed_data["pages"][0]["routing_reason"] == "Insufficient native text fallback"
    assert parsed_data["pages"][0]["layout_regions"][0]["source_method"] == "pp_structure"

    # Reconstitute
    reconstituted = DocumentExtractionResult.model_validate_json(json_str)
    assert reconstituted.source_name == doc.source_name
    assert reconstituted.status == ExtractionStatus.COMPLETE
    assert reconstituted.pages[0].char_count == len("A. TAI SAN NGAN HAN\t100\t500.000")
    assert reconstituted.pages[0].layout_regions[0].html == "<table><tr><td>TS</td></tr></table>"
