# Backend + ingestion worker image (owner: Minahil).
# System packages for every ingestion track are installed here on day 0, so no
# track needs to edit this file later.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg: Track 3 audio. tesseract + English/Urdu data: Track 2 OCR (if it wins the comparison).
# libgl1, libglib2.0-0: OpenCV, which Docling's layout and OCR models use.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-urd \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
COPY requirements/ requirements/
RUN pip install -r requirements.txt -r requirements/base.txt

# Track 1: bake Docling's layout and table models into the image so the first
# upload isn't slow. Uncomment once requirements/docs.txt pins Docling.
# RUN docling-tools models download

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
