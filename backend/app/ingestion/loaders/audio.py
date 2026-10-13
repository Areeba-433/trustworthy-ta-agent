"""Audio department: a lecture recording becomes English transcript blocks. Owner: Zuha.

Part 1: duration limits, ffprobe, light ffmpeg preprocessing, pause detection and the chunk plan.
Part 2: settings, the faster-whisper engine, per-chunk caching and offsets.
Part 3: the hallucination filter, transcript blocks and load().
"""
from __future__ import annotations

import importlib.metadata
import json
import logging
import math
import os
import re
import shutil
import subprocess
import threading
import wave
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.ingestion import messages
from app.ingestion.cleaning.common import clean_text, detect_lang, title_from_filename
from app.ingestion.contract import Block, Location, ParsedDocument, QualityReport, ResourceMeta
from app.ingestion.registry import register
from app.ingestion.storage import Timer, cache_path, raw_dir, write_text_atomic

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

# ---- Speech-to-text. Settings come from .env and are read when a file is processed, not at import ----
TASK = "translate"            # stored text is English: English passes through, Urdu is translated
# AUDIO_KEEP_ORIGINAL (not implemented): would also run task="transcribe" and keep the Urdu text in
# `extra`. It needs a team decision first, because rule 4 of the guide is about the original text.
DEFAULT_MODEL = "medium"
DEFAULT_LANGUAGE = "ur"       # Step 1: auto-detect called Urdu "hi"; forcing "ur" keeps every chunk consistent
DEFAULT_BEAM_SIZE = 5
CPU_THREADS = 8
VAD_MIN_SILENCE_MS = 500
# No initial_prompt: in the Step 1 benchmark a prompt made the output worse and about 4x slower.
REFUSED_MODELS = {"tiny", "base", "small", "turbo", "large-v3-turbo"}   # too weak, or not trained to translate
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models" / "whisper"  # backend/data is gitignored
CACHE_VERSION = "v1"          # bump when the cached JSON layout changes, so old files are ignored
REQUIRED_SEGMENT_KEYS = {"start", "end", "text", "avg_logprob", "no_speech_prob", "compression_ratio"}
PARSER = "faster-whisper"

# ---- Hallucination filter, applied after all chunks are merged. Kept text is never reworded ----
DROP_NO_SPEECH_PROB = 0.6     # drop when no_speech_prob is above this AND ...
DROP_LOGPROB = -1.0           # ... avg_logprob is below this
DROP_COMPRESSION = 2.4        # drop looping text ("the the the the ...")
REPEAT_RUN = 3                # the same line 3 or more times in a row: keep only the first
STOCK_LOW_LOGPROB = -0.7      # a stock phrase is dropped only when Whisper was also unsure:
STOCK_HIGH_NO_SPEECH = 0.5    # avg_logprob below -0.7 OR no_speech_prob above 0.5
STOCK_PHRASES = frozenset({
    "thanks for watching", "thank you for watching", "thank you so much for watching",
    "thank you very much for watching", "please subscribe", "please subscribe to my channel",
    "subscribe to my channel", "like and subscribe", "please like and subscribe",
})
STOCK_PREFIXES = ("subtitles by", "subtitle by", "captions by", "translated by",
                  "transcribed by", "transcription by")

# ---- Transcript blocks ----
BLOCK_MIN_SECONDS = 60        # from here on, close the block at the end of a sentence
BLOCK_TARGET_SECONDS = 120    # from here on, close it at the end of any segment
BLOCK_MAX_SECONDS = 150       # never longer than this
SHORT_TAIL_SECONDS = 30       # a shorter last block joins the one before it
SENTENCE_ENDS = (".", "?", "!", "\u06d4", "\u061f")    # also the Urdu full stop and question mark

# ---- Teacher messages, all from messages.py ----
# Until Minahil adds the audio-specific sentences, the closest existing one is used.
MSG_UNREADABLE = messages.UNREADABLE
MSG_INTERNAL = messages.INTERNAL
MSG_PARTIAL = messages.PARTIAL
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


@dataclass(frozen=True)
class Plan:
    seconds: float              # length of the prepared WAV, which matches the original
    chunks: tuple[Chunk, ...]


@dataclass(frozen=True)
class AudioSettings:
    model: str
    language: str | None        # None = auto-detect
    beam_size: int
    denoise: bool
    model_dir: Path
    task: str = TASK


@dataclass
class RecordingTranscript:
    seconds: float
    chunks: list[Chunk]
    segments: list[dict]        # every chunk, in order, on the ORIGINAL timeline; not filtered yet
    transcribed: int = 0        # chunks sent to the model in this run
    from_cache: int = 0         # chunks read from the cache
    failed_chunks: list[int] = field(default_factory=list)


# ================================================================ part 1: ffmpeg / ffprobe

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


# ================================================================ part 1: the prepared WAV

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


# ================================================================ part 1: pauses and chunks

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
                chunk_seconds: float | None = None,
                search_seconds: float | None = None) -> list[Chunk]:
    """Split the timeline into ~10-minute chunks, cutting in the middle of the pause nearest each mark.

    No pause within `search_seconds` of a mark: cut exactly at the mark. The chunks cover the whole
    recording with no gaps, so (time inside a chunk) + chunk.start = time in the original.
    """
    chunk_seconds = chunk_seconds or CHUNK_MINUTES * 60
    search_seconds = min(CUT_SEARCH_SECONDS if search_seconds is None else search_seconds,
                         chunk_seconds / 2)
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


# ================================================================ part 1: temporary files

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


# ================================================================ part 2: settings

def _refused(model: str) -> bool:
    name = model.lower()
    return name in REFUSED_MODELS or name.startswith("distil") or name.endswith(".en")


def read_settings() -> AudioSettings:
    """Read the AUDIO_* settings from the environment (config.py has already loaded .env)."""
    model = os.getenv("AUDIO_WHISPER_MODEL", "").strip() or DEFAULT_MODEL
    if _refused(model):
        logger.warning("AUDIO_WHISPER_MODEL=%s can't translate well; using %s instead", model, DEFAULT_MODEL)
        model = DEFAULT_MODEL

    language: str | None = os.getenv("AUDIO_LANGUAGE", "").strip().lower() or DEFAULT_LANGUAGE
    if language == "auto":
        language = None
    elif not re.fullmatch(r"[a-z]{2,3}", language):
        logger.warning("AUDIO_LANGUAGE=%r is not a language code; using %s", language, DEFAULT_LANGUAGE)
        language = DEFAULT_LANGUAGE

    try:
        beam_size = int(os.getenv("AUDIO_BEAM_SIZE", "").strip() or DEFAULT_BEAM_SIZE)
    except ValueError:
        beam_size = 0
    if not 1 <= beam_size <= 10:
        logger.warning("AUDIO_BEAM_SIZE must be a number from 1 to 10; using %d", DEFAULT_BEAM_SIZE)
        beam_size = DEFAULT_BEAM_SIZE

    denoise = os.getenv("AUDIO_DENOISE", "0").strip() == "1"
    model_dir = Path(os.getenv("AUDIO_MODEL_DIR", "").strip() or DEFAULT_MODEL_DIR)
    return AudioSettings(model=model, language=language, beam_size=beam_size,
                         denoise=denoise, model_dir=model_dir)


# ================================================================ part 2: the engine

_engine_lock = threading.Lock()   # one transcription at a time: the dispatcher doesn't serialise audio
_model: Any = None                # loaded on first use, then reused (loading takes seconds and ~1-2 GB)
_model_name: str | None = None


def _get_model(model_name: str, model_dir: Path) -> Any:
    """Load the Whisper model once. Call only while holding _engine_lock."""
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as err:
        raise AudioProblem(MSG_INTERNAL, f"faster-whisper is not installed: {err}") from None
    try:
        model_dir.mkdir(parents=True, exist_ok=True)
        _model = WhisperModel(model_name, device="cpu", compute_type="int8",
                              cpu_threads=CPU_THREADS, download_root=str(model_dir))
    except Exception as err:      # download failure, unknown model name, out of memory
        _model, _model_name = None, None
        raise AudioProblem(MSG_INTERNAL, f"could not load Whisper model {model_name!r}: {err}") from None
    _model_name = model_name
    return _model


def transcribe_audio(audio: np.ndarray | Path, task: str, language: str | None,
                     initial_prompt: str | None, *, model_name: str, beam_size: int,
                     model_dir: Path) -> dict:
    """The ONE place that talks to the speech engine. Returns plain, JSON-ready data:

        {"language": "ur", "language_probability": 1.0,
         "segments": [{"start", "end", "text", "avg_logprob", "no_speech_prob", "compression_ratio"}]}

    Times are seconds from the start of `audio`. This is the same shape as a Groq/OpenAI
    "verbose_json" response, so a Groq backend can be added later behind this function
    (it would write the samples to a WAV file and upload that).
    """
    with _engine_lock:
        model = _get_model(model_name, model_dir)
        segments, info = model.transcribe(
            audio, task=task, language=language, initial_prompt=initial_prompt,
            beam_size=beam_size, vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=VAD_MIN_SILENCE_MS),
            condition_on_previous_text=False)
        segments = list(segments)          # a generator: the real work happens here, inside the lock
    return {
        "language": info.language,
        "language_probability": round(float(info.language_probability), 3),
        "segments": [{"start": round(float(s.start), 3), "end": round(float(s.end), 3),
                      "text": s.text.strip(),
                      "avg_logprob": round(float(s.avg_logprob), 4),
                      "no_speech_prob": round(float(s.no_speech_prob), 4),
                      "compression_ratio": round(float(s.compression_ratio), 4)}
                     for s in segments],
    }


# ================================================================ part 2: cache

def _tag(text: str) -> str:
    """Make a setting safe inside a file name (a model setting can be a folder path)."""
    return re.sub(r"[^A-Za-z0-9.]+", "-", text).strip("-") or "x"


def plan_cache_path(sha: str, denoise: bool, chunk_seconds: float, search_seconds: float) -> Path:
    variant = (f"plan-{chunk_seconds:g}-{search_seconds:g}-{SILENCE_NOISE_DB}dB-"
               f"{SILENCE_MIN_SECONDS:g}-{'dn' if denoise else 'plain'}")
    return cache_path(sha, "audio", CACHE_VERSION, variant)


def chunk_cache_path(sha: str, chunk: Chunk, s: AudioSettings) -> Path:
    """One raw-transcript file per chunk. The name holds every setting that changes the words, so a
    translate cache is never reused for transcribe, a different model never reuses an old transcript,
    and a different chunk plan (other start OR end) never reuses a chunk that covered other audio."""
    variant = "_".join([
        _tag(s.model), s.task, s.language or "auto", f"b{s.beam_size}",
        "dn" if s.denoise else "plain", f"c{chunk.index:03d}",
        f"{round(chunk.start * 1000)}-{round(chunk.end * 1000)}ms"])
    return cache_path(sha, "audio", CACHE_VERSION, variant)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        logger.warning("ignoring damaged cache file %s: %s", path.name, err)
        return None


def _write_json(path: Path, data: Any) -> None:
    """Save all-or-nothing with storage.py. A failed save only costs time later, so it never stops the work."""
    try:
        write_text_atomic(path, json.dumps(data, ensure_ascii=False))
    except OSError as err:
        logger.warning("could not save cache file %s: %s", path.name, err)


def _load_plan(path: Path) -> Plan | None:
    data = _read_json(path)
    if data is None:
        return None
    try:
        plan = Plan(seconds=float(data["seconds"]), chunks=tuple(Chunk(**c) for c in data["chunks"]))
    except (TypeError, KeyError, ValueError):
        logger.warning("ignoring damaged cache file %s", path.name)
        return None
    return plan if plan.chunks else None


def _save_plan(path: Path, plan: Plan) -> None:
    _write_json(path, {"seconds": plan.seconds, "chunks": [asdict(c) for c in plan.chunks]})


def _load_raw(path: Path) -> dict | None:
    data = _read_json(path)
    if data is None:
        return None
    segments = data.get("segments") if isinstance(data, dict) else None
    if isinstance(segments, list) and all(
            isinstance(x, dict) and REQUIRED_SEGMENT_KEYS <= x.keys() for x in segments):
        return data
    logger.warning("ignoring damaged cache file %s", path.name)
    return None


# ================================================================ part 2: offsets and the whole recording

def place_segments(raw: dict, chunk: Chunk) -> list[dict]:
    """Chunk-relative times -> times in the ORIGINAL recording (add the chunk's start), kept inside the chunk."""
    placed = []
    for seg in raw["segments"]:
        start = min(chunk.end, chunk.start + max(0.0, float(seg["start"])))
        end = min(chunk.end, chunk.start + max(0.0, float(seg["end"])))
        placed.append({**seg, "start": round(start, 3), "end": round(max(start, end), 3),
                       "chunk": chunk.index, "source_lang": raw.get("language") or "unknown"})
    return placed


def _transcribe_chunk(wav: Path, chunk: Chunk, s: AudioSettings) -> dict:
    samples = read_chunk(wav, chunk)
    if len(samples) == 0:
        return {"language": s.language or "unknown", "language_probability": 0.0, "segments": []}
    raw = transcribe_audio(samples, s.task, s.language, None,
                           model_name=s.model, beam_size=s.beam_size, model_dir=s.model_dir)
    logger.info("audio chunk %d (%.0f to %.0f s): %d segments",
                chunk.index, chunk.start, chunk.end, len(raw["segments"]))
    return raw


def transcribe_recording(path: Path, meta: ResourceMeta, s: AudioSettings,
                         timer: Timer) -> RecordingTranscript:
    """Whole recording -> raw segments on the original timeline, using the cache wherever possible.

    AudioProblem (ffmpeg missing, unreadable file, model can't load) stops everything.
    Any other error inside one chunk fails only that chunk: the others are kept and cached,
    and the next run retries just the missing ones. If every chunk is cached, ffmpeg isn't run at all.
    """
    sha = meta.file_sha256
    chunk_seconds, search_seconds = CHUNK_MINUTES * 60, CUT_SEARCH_SECONDS
    plan_path = plan_cache_path(sha, s.denoise, chunk_seconds, search_seconds)
    plan = _load_plan(plan_path)
    raws: dict[int, dict] = {}
    if plan is not None:
        for chunk in plan.chunks:
            if not chunk.silent and (raw := _load_raw(chunk_cache_path(sha, chunk, s))) is not None:
                raws[chunk.index] = raw
    result = RecordingTranscript(seconds=0.0, chunks=[], segments=[], from_cache=len(raws))

    if plan is None or any(not c.silent and c.index not in raws for c in plan.chunks):
        with work_dir(meta.resource_id) as tmp:
            wav = tmp / "prepared.wav"
            with timer("audio_convert"):
                seconds = convert_to_wav(path, wav, s.denoise)
            if plan is None:
                with timer("audio_pauses"):
                    silences = find_silences(wav, seconds)
                plan = Plan(seconds, tuple(plan_chunks(seconds, silences, chunk_seconds, search_seconds)))
                _save_plan(plan_path, plan)
            for chunk in plan.chunks:
                if chunk.silent or chunk.index in raws:
                    continue
                try:
                    with timer("audio_transcribe"):
                        raw = _transcribe_chunk(wav, chunk, s)
                except AudioProblem:
                    raise
                except Exception:
                    logger.exception("audio chunk %d of resource %s failed", chunk.index, meta.resource_id)
                    result.failed_chunks.append(chunk.index)
                    continue
                _write_json(chunk_cache_path(sha, chunk, s), raw)   # saved at once: a crash later can resume
                raws[chunk.index] = raw
                result.transcribed += 1

    result.seconds, result.chunks = plan.seconds, list(plan.chunks)
    for chunk in plan.chunks:
        if chunk.index in raws:
            result.segments.extend(place_segments(raws[chunk.index], chunk))
    return result


# ================================================================ part 3: hallucination filter

def _words(text: str) -> str:
    """Lower-case words only, for comparing lines: 'Thanks for watching!' -> 'thanks for watching'."""
    return " ".join(re.findall(r"\w+", text.lower()))


def drop_reason(seg: dict) -> str | None:
    """Why this segment is a hallucination, or None to keep it."""
    if not seg["text"].strip():
        return "empty"
    if seg["no_speech_prob"] > DROP_NO_SPEECH_PROB and seg["avg_logprob"] < DROP_LOGPROB:
        return "silence"
    if seg["compression_ratio"] > DROP_COMPRESSION:
        return "loop"
    words = _words(seg["text"])
    unsure = seg["avg_logprob"] < STOCK_LOW_LOGPROB or seg["no_speech_prob"] > STOCK_HIGH_NO_SPEECH
    if unsure and (words in STOCK_PHRASES or words.startswith(STOCK_PREFIXES)):
        return "stock phrase"
    return None


def filter_hallucinations(segments: list[dict]) -> tuple[list[dict], Counter[str]]:
    """Keep real speech in time order and count what was dropped, and why. Kept text is never changed."""
    dropped: Counter[str] = Counter()
    kept = []
    for seg in sorted(segments, key=lambda x: (x["start"], x["end"])):
        reason = drop_reason(seg)
        if reason:
            dropped[reason] += 1
        else:
            kept.append(seg)

    result: list[dict] = []
    i = 0
    while i < len(kept):                         # runs of the same line: 3 or more keep only the first
        j = i
        while j + 1 < len(kept) and _words(kept[j + 1]["text"]) == _words(kept[i]["text"]):
            j += 1
        run = kept[i:j + 1]
        if len(run) >= REPEAT_RUN:
            result.append(run[0])
            dropped["repeat"] += len(run) - 1
        else:
            result.extend(run)
        i = j + 1
    return result, dropped


# ================================================================ part 3: transcript blocks

def clock(seconds: float) -> str:
    """'12:40' under an hour, '01:02:03' past one hour."""
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def part_heading(number: int, start: float, end: float) -> str:
    return f"Part {number} ({clock(start)} to {clock(end)})"


def _ends_sentence(text: str) -> bool:
    return text.rstrip().rstrip("\"')]\u201d\u2019").endswith(SENTENCE_ENDS)


def group_segments(segments: list[dict]) -> list[list[dict]]:
    """Walk segments in time order and group them into blocks of about 60 to 120 seconds.

    After 60 s a block closes at the end of a sentence; after 120 s at the end of any segment;
    it never grows past 150 s. A last group shorter than 30 s joins the one before it.
    """
    groups: list[list[dict]] = []
    current: list[dict] = []
    for seg in segments:
        if current and seg["end"] - current[0]["start"] > BLOCK_MAX_SECONDS:
            groups.append(current)
            current = []
        current.append(seg)
        span = seg["end"] - current[0]["start"]
        if (span >= BLOCK_MIN_SECONDS and _ends_sentence(seg["text"])) or span >= BLOCK_TARGET_SECONDS:
            groups.append(current)
            current = []
    if current:
        tail = current[-1]["end"] - current[0]["start"]
        if (groups and tail < SHORT_TAIL_SECONDS
                and current[-1]["end"] - groups[-1][0]["start"] <= BLOCK_MAX_SECONDS):
            groups[-1].extend(current)
        else:
            groups.append(current)
    return groups


def _confidence(group: list[dict]) -> float:
    """Whisper's avg_logprob, weighted by segment length, turned into 0..1 (exp of the mean log-probability)."""
    weights = [max(seg["end"] - seg["start"], 0.01) for seg in group]
    mean = sum(seg["avg_logprob"] * w for seg, w in zip(group, weights)) / sum(weights)
    return round(min(1.0, max(0.0, math.exp(mean))), 3)


def _source_lang(group: list[dict]) -> str:
    return Counter(seg.get("source_lang", "unknown") for seg in group).most_common(1)[0][0]


def build_blocks(segments: list[dict], title: str, s: AudioSettings) -> list[Block]:
    """Grouped segments -> contract Blocks: seq 0, 1, 2 with no gaps, title first, times in seconds."""
    pieces = []
    for group in group_segments(segments):
        # clean_text() joins single line breaks into spaces: fine for an English transcript.
        text = clean_text(" ".join(seg["text"].strip() for seg in group))
        if text:
            pieces.append((group, text))
    spans = [(g[0]["start"], max(seg["end"] for seg in g)) for g, _ in pieces]
    for i in range(len(spans) - 1):                      # a block never runs into the next one
        start, end = spans[i]
        spans[i] = (start, max(start, min(end, spans[i + 1][0])))

    blocks = []
    for seq, ((group, text), (start, end)) in enumerate(zip(pieces, spans)):
        blocks.append(Block(
            seq=seq, kind="transcript", text=text,
            heading_path=[title, part_heading(seq + 1, start, end)],
            loc=Location(t_start=round(start, 2), t_end=round(end, 2)),
            lang=detect_lang(text), confidence=_confidence(group),
            extra={"source_lang": _source_lang(group), "task": s.task, "model": s.model}))
    return blocks


# ================================================================ part 3: the document and load()

def _engine_version() -> str:
    try:
        return importlib.metadata.version("faster-whisper")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _failed(meta: ResourceMeta, reason: str) -> ParsedDocument:
    from app.ingestion.dispatcher import failed_document   # shared helper; imported here so imports stay one-way
    return failed_document(meta, meta.precheck.source_type, reason)


def _load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    timer = Timer()
    s = read_settings()
    title = title_from_filename(meta.file_name)
    with timer("audio_probe"):
        seconds = probe_duration(path)
    warnings = check_duration(seconds)                   # raises when too short or too long

    rec = transcribe_recording(path, meta, s, timer)
    with timer("audio_blocks"):
        kept, dropped = filter_hallucinations(rec.segments)
        blocks = build_blocks(kept, title, s)
    logger.info(
        "audio %s: %.0f s, %d chunks (%d silent, %d from cache, %d transcribed, %d failed), "
        "%d segments, dropped %s, %d blocks, model=%s task=%s language=%s",
        meta.resource_id, rec.seconds, len(rec.chunks), sum(c.silent for c in rec.chunks),
        rec.from_cache, rec.transcribed, len(rec.failed_chunks), len(rec.segments),
        dict(dropped) or "none", len(blocks), s.model, s.task, s.language or "auto")

    if not blocks:
        if rec.failed_chunks:            # part of it couldn't be listened to; a retry resumes from the cache
            raise AudioProblem(MSG_INTERNAL, f"chunks {rec.failed_chunks} failed and no other speech was found")
        raise AudioProblem(MSG_NO_SPEECH, "no speech left after the hallucination filter")
    status = "ok"
    if rec.failed_chunks:
        status = "degraded"
        warnings.append(MSG_PARTIAL)

    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=meta.precheck.source_type, title=title,
        parser=PARSER, parser_version=_engine_version(), blocks=blocks,
        quality=QualityReport(
            status=status, warnings=warnings, units_total=int(round(rec.seconds)),
            chars_total=sum(len(b.text) for b in blocks),
            avg_confidence=round(sum(b.confidence for b in blocks) / len(blocks), 3),
            seconds_taken=dict(timer.seconds)))


@register("audio")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    try:
        return _load(path, meta)
    except AudioProblem as problem:
        logger.warning("audio %s failed: %s", meta.resource_id, problem.detail or problem.message)
        return _failed(meta, problem.message)
    except Exception:                    # a bug or something unexpected: never crash the upload
        logger.exception("audio loader crashed on resource %s", meta.resource_id)
        return _failed(meta, MSG_INTERNAL)