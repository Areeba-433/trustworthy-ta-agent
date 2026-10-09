import hashlib
import re
import time
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def data_dir() -> Path:
    return Path(settings.INGESTION_DATA_DIR)


def resource_dir(resource_id: str) -> Path:
    if not _SAFE_ID.match(resource_id):          # ids become folder names, so block tricks like "../"
        raise ValueError(f"unsafe resource_id: {resource_id!r}")
    path = data_dir() / resource_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def raw_dir(resource_id: str) -> Path:
    path = resource_dir(resource_id) / "raw"
    path.mkdir(exist_ok=True)
    return path


def parsed_path(resource_id: str) -> Path:
    return resource_dir(resource_id) / "parsed.json"


def cache_path(sha: str, parser: str, version: str, variant: str = "default", suffix: str = ".json") -> Path:
    folder = data_dir() / "_cache"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{sha}_{parser}-{version}_{variant}{suffix}"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):   # read 1 MB at a time, so big files don't fill memory
            h.update(chunk)
    return h.hexdigest()


def write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)          # all or nothing: a crash never leaves half a file


class Timer:
    """timer = Timer(); with timer("parse"): ...  then timer.seconds -> {"parse": 1.234}"""
    def __init__(self) -> None:
        self.seconds: dict[str, float] = {}

    @contextmanager
    def __call__(self, stage: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[stage] = round(self.seconds.get(stage, 0.0) + time.perf_counter() - start, 3)