import pytest
from PIL import Image, ImageDraw

from app.core.config import settings


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Every test writes into its own empty temporary folder."""
    monkeypatch.setattr(settings, "INGESTION_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


@pytest.fixture
def scanned_pdf(tmp_path):
    """A picture-only PDF, made fresh for each test, like a scanner produces."""
    page = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(page).text((100, 100), "Third normal form removes transitive dependencies.", fill="black")
    path = tmp_path / "scanned.pdf"
    page.save(path)
    return path