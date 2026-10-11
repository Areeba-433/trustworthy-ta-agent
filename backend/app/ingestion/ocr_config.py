"""OCR engine settings shared by the OCR track and Areeba's picture OCR: one decision, one place."""
from docling.datamodel.pipeline_options import EasyOcrOptions, OcrMode, OcrOptions, TesseractCliOcrOptions

from app.core.config import settings

OCR_LANGUAGES = {"easyocr": ["en", "ur"], "tesseract": ["eng", "urd"]}
OCR_SCALE = 3.0      # Docling's default; to be tuned later with measurements


def ocr_options(full_page: bool = False) -> OcrOptions:
    """The OCR engine and languages for the whole project.

    full_page=True reads the whole page (images, scanned pages, broken text layers);
    otherwise Docling reads only picture areas that have no real text (mixed PDFs).
    """
    engine = settings.OCR_ENGINE
    mode = OcrMode.FULL_PAGE if full_page else OcrMode.DEFAULT
    if engine == "easyocr":
        return EasyOcrOptions(lang=OCR_LANGUAGES[engine], mode=mode, scale=OCR_SCALE)
    if engine == "tesseract":
        return TesseractCliOcrOptions(lang=OCR_LANGUAGES[engine], mode=mode, scale=OCR_SCALE)
    raise ValueError(f"unknown OCR_ENGINE {engine!r}: use 'easyocr' or 'tesseract'")