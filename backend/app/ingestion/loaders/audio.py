"""Audio department: a lecture recording becomes English transcript blocks. Owner: Zuha.

Part 1: duration limits, ffprobe, light ffmpeg preprocessing, pause detection and the chunk plan.
Parts 2 and 3 add transcription with caching, the hallucination filter and the real load().
"""
from __future__ import annotations

import json
import logging
import math
import re
import shutil
import subprocess
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.ingestion import messages
from app.ingestion.contract import ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register
from app.ingestion.storage import raw_dir

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("tta.ingestion.audio")

# ---- Duration limits ----
MIN_SECONDS = 5
WARN_MINUTES = 90
MAX_MINUTES = 180
CHUNK_MINUTES = 10

# ---- Chunk cutting ----
CUT_SEARCH_SECONDS = 60       # look this far either side of each 10-minute mark for a pause
MIN_CHUNK_SECONDS = 60        # a shorter tail joins the chunk before it
SILENCE_NOISE_DB = -35        # quieter than this (after loudnorm) counts as a pause
SILENCE_MIN_SECONDS = 0.5     # a pause must last at least this long
SILENT_EDGE_SECONDS = 0.5     # slack when deciding that a whole chunk is silent

# ---- Preprocessing: light only, because heavy denoising hurts Whisper ----
SAMPLE_RATE = 16_000
HIGHPASS_FILTER = "highpass=f=80"
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
DENOISE_FILTER = "afftdn"     # only when AUDIO_DENOISE=1
PROBE_TIMEOUT = 60            # seconds
CONVERT_TIMEOUT = 1800
SILENCE_TIMEOUT = 600

# ---- Teacher messages, all from messages.py ----
# Until Minahil adds the audio-specific sentences, the closest existing one is used.
MSG_UNREADABLE = messages.UNREADABLE
MSG_INTERNAL = messages.INTERNAL
MSG_TOO_LONG = getattr(messages, "AUDIO_TOO_LONG", messages.TOO_LARGE)
MSG_NO_SPEECH = getattr(messages, "NO_SPEECH", messages.NO_TEXT_FILE)
MSG_LONG = getattr(messages, "AUDIO_LONG", None)   # no close existing sentence: no warning until it exists


class AudioProblem(Exception):
    """A problem the teacher should hear about. load() turns it into a failed document with `message`."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(detail or message)
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float          # seconds in the original recording
    end: float
    silent: bool = False  # True: one pause covers the whole chunk, so the model can skip it

    @property
    def seconds(self) -> float:
        return self.end - self.start


# ---------------------------------------------------------------- ffmpeg / ffprobe

def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise AudioProblem(MSG_INTERNAL, f"{name} is not installed or not on PATH")
    return found


def _run(cmd: list[str], timeout: int, fail_message: str) -> subprocess.CompletedProcess:
    """Run ffmpeg or ffprobe. Any failure becomes AudioProblem(fail_message); nothing else escapes."""
    name = Path(cmd[0]).name
    try:
        return subprocess.run(cmd, check=True, capture_output=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
    except subprocess.CalledProcessError as err:
        tail = (err.stderr or b"").decode("utf-8", "replace").strip()[-500:]
        raise AudioProblem(fail_message, f"{name} failed: {tail}") from None
    except subprocess.TimeoutExpired:
        raise AudioProblem(fail_message, f"{name} took longer than {timeout} s") from None
    except OSError as err:
        raise AudioProblem(MSG_INTERNAL, f"could not start {name}: {err}") from None


def probe_duration(path: Path) -> float:
    """Length of the recording in seconds. AudioProblem if there is no readable audio track."""
    proc = _run([_tool("ffprobe"), "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=index:format=duration", "-of", "json", str(path)],
                PROBE_TIMEOUT, MSG_UNREADABLE)
    try:
        info = json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError:
        raise AudioProblem(MSG_UNREADABLE, "ffprobe output was not JSON") from None
    if not isinstance(info, dict) or not info.get("streams"):
        raise AudioProblem(MSG_UNREADABLE, "the file has no audio track")
    try:
        seconds = float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise AudioProblem(MSG_UNREADABLE, "ffprobe found no duration") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise AudioProblem(MSG_UNREADABLE, f"impossible duration {seconds}")
    return seconds


def check_duration(seconds: float) -> list[str]:
    """Raise for recordings we refuse; return the warnings for ones we accept."""
    if seconds < MIN_SECONDS:
        raise AudioProblem(MSG_NO_SPEECH, f"only {seconds:.1f} s long")
    if seconds > MAX_MINUTES * 60:
        raise AudioProblem(MSG_TOO_LONG, f"{seconds / 60:.0f} minutes long")
    if seconds > WARN_MINUTES * 60 and MSG_LONG:
        return [MSG_LONG]
    return []


def build_filter(denoise: bool) -> str:
    parts = [HIGHPASS_FILTER] + ([DENOISE_FILTER] if denoise else []) + [LOUDNORM_FILTER]
    return ",".join(parts)


def convert_to_wav(src: Path, dst: Path, denoise: bool = False) -> float:
    """Mono 16 kHz 16-bit WAV with light clean-up. Returns its length in seconds.

    Silence is NOT trimmed: the timeline stays identical to the original, so 12:40 in a block is
    12:40 in the teacher's file. Whisper's VAD skips pauses inside each chunk instead.
    """
    _run([_tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
          "-i", str(src), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
          "-af", build_filter(denoise), "-c:a", "pcm_s16le",
          "-map_metadata", "-1", "-fflags", "+bitexact", str(dst)],
         CONVERT_TIMEOUT, MSG_UNREADABLE)
    seconds = wav_seconds(dst)
    if seconds <= 0:
        raise AudioProblem(MSG_UNREADABLE, "ffmpeg produced no audio")
    return seconds


# ---------------------------------------------------------------- the prepared WAV

@contextmanager
def _open_prepared(wav: Path) -> Iterator[wave.Wave_read]:
    try:
        w = wave.open(str(wav), "rb")
    except (wave.Error, EOFError, OSError) as err:
        raise AudioProblem(MSG_INTERNAL, f"prepared WAV unreadable: {err}") from None
    with w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SAMPLE_RATE):
            raise AudioProblem(MSG_INTERNAL, "prepared WAV is not 16 kHz mono 16-bit")
        yield w


def wav_seconds(wav: Path) -> float:
    with _open_prepared(wav) as w:
        return w.getnframes() / SAMPLE_RATE


def read_chunk(wav: Path, chunk: Chunk) -> np.ndarray:
    """The chunk's samples as float32 in [-1, 1], which is what faster-whisper accepts directly.

    Reading by sample position means no cut files and an exact offset: sample 0 of the result
    is chunk.start seconds into the original recording.
    """
    import numpy as np

    with _open_prepared(wav) as w:
        total = w.getnframes()
        first = min(total, int(round(chunk.start * SAMPLE_RATE)))
        last = min(total, int(round(chunk.end * SAMPLE_RATE)))
        w.setpos(first)
        data = w.readframes(max(0, last - first))
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


# ---------------------------------------------------------------- pauses and chunks

_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def parse_silences(log: str, seconds: float) -> list[tuple[float, float]]:
    """Turn ffmpeg silencedetect output into (start, end) pairs, in seconds."""
    found: list[tuple[float, float]] = []
    start: float | None = None
    for line in log.splitlines():
        if m := _SILENCE_START.search(line):
            start = max(0.0, float(m.group(1)))
        elif (m := _SILENCE_END.search(line)) and start is not None:
            found.append((start, min(seconds, float(m.group(1)))))
            start = None
    if start is not None:                       # the recording ends during a pause
        found.append((start, seconds))
    return found


def find_silences(wav: Path, seconds: float) -> list[tuple[float, float]]:
    proc = _run([_tool("ffmpeg"), "-nostdin", "-hide_banner", "-nostats", "-i", str(wav),
                 "-af", f"silencedetect=noise={SILENCE_NOISE_DB}dB:d={SILENCE_MIN_SECONDS}",
                 "-f", "null", "-"], SILENCE_TIMEOUT, MSG_INTERNAL)
    return parse_silences(proc.stderr.decode("utf-8", "replace"), seconds)


def plan_chunks(seconds: float, silences: list[tuple[float, float]],
                chunk_seconds: float = CHUNK_MINUTES * 60,
                search_seconds: float = CUT_SEARCH_SECONDS) -> list[Chunk]:
    """Split the timeline into ~10-minute chunks, cutting in the middle of the pause nearest each mark.

    No pause within `search_seconds` of a mark: cut exactly at the mark. The chunks cover the whole
    recording with no gaps, so (time inside a chunk) + chunk.start = time in the original.
    """
    search_seconds = min(search_seconds, chunk_seconds / 2)
    cuts = [0.0]
    while seconds - cuts[-1] > chunk_seconds + MIN_CHUNK_SECONDS:
        target = cuts[-1] + chunk_seconds
        cut, best = target, math.inf
        for s_start, s_end in silences:
            middle = (s_start + s_end) / 2
            distance = abs(middle - target)
            if (distance <= search_seconds and distance < best
                    and cuts[-1] + MIN_CHUNK_SECONDS <= middle <= seconds - MIN_CHUNK_SECONDS):
                cut, best = middle, distance
        cuts.append(cut)
    cuts.append(seconds)

    chunks = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        silent = any(s <= a + SILENT_EDGE_SECONDS and e >= b - SILENT_EDGE_SECONDS for s, e in silences)
        chunks.append(Chunk(index=i, start=round(a, 3), end=round(b, 3), silent=silent))
    return chunks


# ---------------------------------------------------------------- temporary files

@contextmanager
def work_dir(resource_id: str) -> Iterator[Path]:
    """A temporary folder under data/<resource_id>/raw/ (from storage.py), always deleted afterwards."""
    folder = raw_dir(resource_id) / "audio_tmp"
    shutil.rmtree(folder, ignore_errors=True)        # leftovers from a run that crashed
    folder.mkdir(parents=True, exist_ok=True)
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@register("audio")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    # Temporary until Step 4. "transcript" is the contract's block kind for audio; the old
    # placeholder's kind="audio" is not a valid kind, so every audio file failed with INTERNAL.
    return stub_document(meta, kind="transcript")