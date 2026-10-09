"""Imports every track so its @register line runs. One entry per track, written on day 0.

A track whose libraries aren't installed is skipped with a warning (listed in
MISSING) instead of breaking the other tracks. The contract test fails loudly
if any source type ends up without a loader.
"""

import importlib
import logging

log = logging.getLogger(__name__)

TRACKS = {
    "docs": "requirements/docs.txt",    # Track 1, Areeba: digital PDF, DOCX, PPTX
    "ocr": "requirements/ocr.txt",      # Track 2, Minahil: scanned PDF, images
    "audio": "requirements/audio.txt",  # Track 3, Zuha: lecture recordings
    "code": "requirements/code.txt",    # Track 4, Fariha: .cpp and friends
    "text": "requirements/code.txt",    # Track 4, Fariha: .txt, .md
}

MISSING: dict[str, str] = {}

for _module, _requirements in TRACKS.items():
    try:
        importlib.import_module(f"{__name__}.{_module}")
    except ImportError as error:
        MISSING[_module] = f"{error} (pip install -r {_requirements})"
        log.warning("Ingestion track %r not loaded: %s", _module, MISSING[_module])
