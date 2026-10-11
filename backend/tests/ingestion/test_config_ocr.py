import pytest
from docling.datamodel.pipeline_options import EasyOcrOptions, OcrMode, TesseractCliOcrOptions

from app.core.config import settings
from app.ingestion.ocr_config import ocr_options


def test_easyocr_reads_english_and_urdu_by_default():
    opts = ocr_options()
    assert isinstance(opts, EasyOcrOptions)
    assert {"en", "ur"} <= set(opts.lang)


def test_full_page_mode_only_when_asked():
    assert ocr_options(full_page=True).mode == OcrMode.FULL_PAGE
    assert ocr_options(full_page=False).mode == OcrMode.DEFAULT


def test_tesseract_can_be_switched_on_in_settings(monkeypatch):
    monkeypatch.setattr(settings, "OCR_ENGINE", "tesseract")
    assert isinstance(ocr_options(), TesseractCliOcrOptions)


def test_unknown_engine_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "OCR_ENGINE", "magic")
    with pytest.raises(ValueError, match="unknown OCR_ENGINE"):
        ocr_options()