"""Tests for the audio department (app/ingestion/loaders/audio.py). Owner: Zuha.

Part 1: limits, ffprobe, preprocessing, pause detection and chunking.
Part 2: settings, the engine function, per-chunk caching and offsets.
Part 3: the hallucination filter, transcript blocks and load() from end to end.
No test needs a model or the internet. Tests marked needs_ffmpeg use the real ffmpeg and skip without it.
The one real-model test runs only with AUDIO_INTEGRATION_TEST=1.
"""
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import types
import wave
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.ingestion.contract import ParsedDocument, PrecheckResult, ResourceMeta
from app.ingestion.dispatcher import ingest_file
from app.ingestion.loaders import audio
from app.ingestion.loaders.audio import AudioProblem, Chunk
from app.ingestion.storage import Timer, file_sha256

SAMPLES = Path(__file__).parent / "samples" / "audio"
AUDIO_ENV = ["AUDIO_WHISPER_MODEL", "AUDIO_LANGUAGE", "AUDIO_BEAM_SIZE", "AUDIO_DENOISE", "AUDIO_MODEL_DIR"]
needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed")
needs_model = pytest.mark.skipif(
    os.getenv("AUDIO_INTEGRATION_TEST") != "1"
    or importlib.util.find_spec("faster_whisper") is None
    or shutil.which("ffmpeg") is None,
    reason="real-model test: set AUDIO_INTEGRATION_TEST=1 (needs ffmpeg, faster-whisper and the downloaded model)")


def write_wav(path: Path, samples: np.ndarray, rate: int = audio.SAMPLE_RATE) -> Path:
    """Write float samples in [-1, 1] as a 16-bit mono WAV."""
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    return path


def tone(seconds: float, rate: int = audio.SAMPLE_RATE) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return 0.5 * np.sin(2 * np.pi * 440 * t)


def completed(stdout: bytes = b"", stderr: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def seg(start, end, text, logprob=-0.3, no_speech=0.1, compression=1.5) -> dict:
    """One raw Whisper segment, shaped like transcribe_audio() returns it."""
    return {"start": float(start), "end": float(end), "text": text, "avg_logprob": logprob,
            "no_speech_prob": no_speech, "compression_ratio": compression}


def assert_covers(chunks: list[Chunk], seconds: float) -> None:
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].start == 0.0
    assert chunks[-1].end == pytest.approx(seconds)
    for a, b in zip(chunks, chunks[1:]):
        assert a.end == b.start                      # no gaps and no overlaps


@pytest.fixture
def fake_tools(monkeypatch):
    """Pretend ffmpeg and ffprobe are installed, without running them."""
    monkeypatch.setattr(audio.shutil, "which", lambda name: name)


@pytest.fixture
def clean_env(monkeypatch):
    """Start from the default settings, whatever is in your .env."""
    for name in AUDIO_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


# ================================================================ part 1: duration limits

def test_too_short_recording_is_refused():
    with pytest.raises(AudioProblem) as err:
        audio.check_duration(audio.MIN_SECONDS - 1)
    assert err.value.message == audio.MSG_NO_SPEECH


def test_too_long_recording_is_refused():
    with pytest.raises(AudioProblem) as err:
        audio.check_duration(audio.MAX_MINUTES * 60 + 1)
    assert err.value.message == audio.MSG_TOO_LONG


def test_long_recording_is_accepted_with_a_warning():
    warnings = audio.check_duration(audio.WARN_MINUTES * 60 + 1)
    assert warnings == ([audio.MSG_LONG] if audio.MSG_LONG else [])


def test_normal_recording_has_no_warning():
    assert audio.check_duration(30 * 60) == []


# ================================================================ part 1: ffprobe (faked)

def test_probe_reads_the_duration(fake_tools, monkeypatch):
    out = json.dumps({"streams": [{"index": 0}], "format": {"duration": "600.250"}}).encode()
    monkeypatch.setattr(audio.subprocess, "run", lambda *a, **k: completed(stdout=out))
    assert audio.probe_duration(Path("lecture.mp3")) == pytest.approx(600.25)


def test_probe_refuses_a_file_without_audio(fake_tools, monkeypatch):
    out = json.dumps({"streams": [], "format": {"duration": "60"}}).encode()
    monkeypatch.setattr(audio.subprocess, "run", lambda *a, **k: completed(stdout=out))
    with pytest.raises(AudioProblem) as err:
        audio.probe_duration(Path("video_only.mp4"))
    assert err.value.message == audio.MSG_UNREADABLE


def test_ffprobe_failure_becomes_unreadable(fake_tools, monkeypatch):
    def broken(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, output=b"", stderr=b"Invalid data found")
    monkeypatch.setattr(audio.subprocess, "run", broken)
    with pytest.raises(AudioProblem) as err:
        audio.probe_duration(Path("broken.mp3"))
    assert err.value.message == audio.MSG_UNREADABLE
    assert "Invalid data" in err.value.detail


def test_missing_ffmpeg_is_an_internal_problem(monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    with pytest.raises(AudioProblem) as err:
        audio.probe_duration(Path("lecture.mp3"))
    assert err.value.message == audio.MSG_INTERNAL


# ================================================================ part 1: conversion (faked)

def test_conversion_uses_the_light_filter_and_never_trims(fake_tools, monkeypatch, tmp_path):
    seen = []

    def fake_ffmpeg(cmd, **kwargs):
        seen.append(cmd)
        write_wav(Path(cmd[-1]), tone(2.0))          # what ffmpeg would have written
        return completed()

    monkeypatch.setattr(audio.subprocess, "run", fake_ffmpeg)
    seconds = audio.convert_to_wav(tmp_path / "in.mp3", tmp_path / "out.wav")
    cmd = seen[0]
    assert seconds == pytest.approx(2.0)
    assert cmd[cmd.index("-af") + 1] == "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11"
    assert cmd[cmd.index("-ar") + 1] == "16000"
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert "-vn" in cmd
    assert not any("silenceremove" in part for part in cmd)


def test_denoise_adds_afftdn_before_loudnorm():
    assert audio.build_filter(True) == "highpass=f=80,afftdn,loudnorm=I=-16:TP=-1.5:LRA=11"
    assert "afftdn" not in audio.build_filter(False)


# ================================================================ part 1: pauses and chunks

FFMPEG_SILENCE_LOG = """\
[silencedetect @ 000001] silence_start: -0.0213
[silencedetect @ 000001] silence_end: 1.5 | silence_duration: 1.5213
size=N/A time=00:00:30.00 bitrate=N/A speed= 900x
[silencedetect @ 000001] silence_start: 12.25
[silencedetect @ 000001] silence_end: 13.75 | silence_duration: 1.5
[silencedetect @ 000001] silence_start: 28.4
"""


def test_silence_log_is_parsed_into_pairs():
    assert audio.parse_silences(FFMPEG_SILENCE_LOG, 30.0) == [(0.0, 1.5), (12.25, 13.75), (28.4, 30.0)]


def test_short_recording_is_one_chunk():
    assert audio.plan_chunks(300.0, []) == [Chunk(0, 0.0, 300.0)]


def test_cut_goes_in_the_middle_of_the_nearest_pause():
    silences = [(580.0, 582.0), (610.0, 611.0), (1190.0, 1192.0)]
    chunks = audio.plan_chunks(1500.0, silences)
    assert [(c.start, c.end) for c in chunks] == [(0.0, 610.5), (610.5, 1191.0), (1191.0, 1500.0)]
    assert_covers(chunks, 1500.0)


def test_cut_falls_back_to_the_mark_when_no_pause_is_near():
    chunks = audio.plan_chunks(1300.0, [(100.0, 101.0)])
    assert [(c.start, c.end) for c in chunks] == [(0.0, 600.0), (600.0, 1200.0), (1200.0, 1300.0)]


def test_short_tail_joins_the_chunk_before_it():
    assert [(c.start, c.end) for c in audio.plan_chunks(640.0, [])] == [(0.0, 640.0)]


def test_whole_silent_chunk_is_marked_for_skipping():
    chunks = audio.plan_chunks(1300.0, [(590.0, 1250.0)])
    assert [c.silent for c in chunks] == [False, True, False]


def test_three_hour_lecture_chunks_stay_near_ten_minutes():
    seconds = 3 * 3600.0
    silences = [(30.0 + 45.0 * k, 31.0 + 45.0 * k) for k in range(240)]   # a pause every 45 s
    chunks = audio.plan_chunks(seconds, silences)
    assert_covers(chunks, seconds)
    assert all(540 <= c.seconds <= 660 for c in chunks[:-1])
    assert 60 <= chunks[-1].seconds <= 660


# ================================================================ part 1: reading chunks, temp folder

def test_read_chunk_returns_exactly_that_stretch(tmp_path):
    rate = audio.SAMPLE_RATE
    ramp = np.arange(3 * rate, dtype=np.float64) / (3 * rate)    # value rises steadily with time
    wav = write_wav(tmp_path / "prepared.wav", ramp)
    samples = audio.read_chunk(wav, Chunk(1, 1.0, 2.0))
    assert samples.dtype == np.float32
    assert len(samples) == rate
    assert samples[0] == pytest.approx(ramp[rate], abs=1e-3)     # sample 0 is exactly 1.0 s in


def test_read_chunk_refuses_a_wav_in_the_wrong_format(tmp_path):
    wav = write_wav(tmp_path / "wrong.wav", tone(1.0, rate=44_100), rate=44_100)
    with pytest.raises(AudioProblem) as err:
        audio.read_chunk(wav, Chunk(0, 0.0, 1.0))
    assert err.value.message == audio.MSG_INTERNAL


def test_temp_folder_is_deleted_even_after_a_crash(data_dir):
    with pytest.raises(RuntimeError):
        with audio.work_dir("r1") as folder:
            (folder / "prepared.wav").write_bytes(b"x")
            assert folder.is_dir()
            assert folder.is_relative_to(data_dir)
            raise RuntimeError("crash in the middle")
    assert not folder.exists()


# ================================================================ part 1: real ffmpeg (skip without it)

@needs_ffmpeg
def test_real_sample_duration():
    assert 20 < audio.probe_duration(SAMPLES / "short_mixed.mp3") < 30


@needs_ffmpeg
def test_real_corrupt_file_is_unreadable(tmp_path):
    bad = tmp_path / "broken.mp3"
    bad.write_bytes(b"this is not audio at all " * 100)
    with pytest.raises(AudioProblem) as err:
        audio.probe_duration(bad)
    assert err.value.message == audio.MSG_UNREADABLE


@needs_ffmpeg
def test_real_ffmpeg_keeps_the_length_and_finds_the_pause(tmp_path):
    rate = audio.SAMPLE_RATE
    signal = np.concatenate([tone(3.0), np.zeros(2 * rate), tone(3.0)])   # sound, 2 s pause, sound
    src = write_wav(tmp_path / "sound_pause_sound.wav", signal)
    prepared = tmp_path / "prepared.wav"
    seconds = audio.convert_to_wav(src, prepared)
    assert seconds == pytest.approx(8.0, abs=0.1)          # timeline not trimmed or shifted
    silences = audio.find_silences(prepared, seconds)
    assert any(start <= 3.3 and end >= 4.7 for start, end in silences)


# ================================================================ part 2: settings

def test_settings_defaults(clean_env):
    s = audio.read_settings()
    assert (s.model, s.language, s.beam_size, s.denoise, s.task) == ("medium", "ur", 5, False, "translate")
    assert s.model_dir.parts[-3:] == ("data", "models", "whisper")


@pytest.mark.parametrize("name", ["small", "distil-large-v3", "medium.en", "large-v3-turbo"])
def test_models_that_cannot_translate_well_fall_back_to_medium(clean_env, name, caplog):
    clean_env.setenv("AUDIO_WHISPER_MODEL", name)
    with caplog.at_level(logging.WARNING, logger="tta.ingestion.audio"):
        assert audio.read_settings().model == "medium"
    assert name in caplog.text


def test_language_setting(clean_env):
    clean_env.setenv("AUDIO_LANGUAGE", "auto")
    assert audio.read_settings().language is None
    clean_env.setenv("AUDIO_LANGUAGE", "EN")
    assert audio.read_settings().language == "en"
    clean_env.setenv("AUDIO_LANGUAGE", "urdu please")
    assert audio.read_settings().language == "ur"


def test_beam_and_denoise_settings(clean_env):
    clean_env.setenv("AUDIO_BEAM_SIZE", "2")
    clean_env.setenv("AUDIO_DENOISE", "1")
    s = audio.read_settings()
    assert s.beam_size == 2 and s.denoise is True
    clean_env.setenv("AUDIO_BEAM_SIZE", "lots")
    assert audio.read_settings().beam_size == 5


# ================================================================ part 2: the engine function (fake model)

class FakeWhisperModel:
    """Stands in for faster_whisper.WhisperModel: records how it was built and called."""
    instances = 0

    def __init__(self, name, **kwargs):
        FakeWhisperModel.instances += 1
        self.name, self.kwargs, self.calls = name, kwargs, []

    def transcribe(self, audio_input, **kwargs):
        self.calls.append(kwargs)
        segments = (SimpleNamespace(start=0.0, end=4.21234, text=" Pointer size depends on the machine.",
                                    avg_logprob=-0.41, no_speech_prob=0.35, compression_ratio=1.83)
                    for _ in range(1))                       # a generator, like the real one
        return segments, SimpleNamespace(language="ur", language_probability=1.0)


@pytest.fixture
def fake_whisper(monkeypatch):
    module = types.ModuleType("faster_whisper")
    module.WhisperModel = FakeWhisperModel
    FakeWhisperModel.instances = 0
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    monkeypatch.setattr(audio, "_model", None)
    monkeypatch.setattr(audio, "_model_name", None)
    return FakeWhisperModel


def call_engine(model_dir: Path) -> dict:
    return audio.transcribe_audio(np.zeros(16000, dtype=np.float32), "translate", "ur", None,
                                  model_name="medium", beam_size=5, model_dir=model_dir)


def test_transcribe_audio_uses_the_agreed_options_and_returns_plain_data(fake_whisper, tmp_path):
    out = call_engine(tmp_path)
    model = audio._model
    assert model.name == "medium"
    assert model.kwargs == {"device": "cpu", "compute_type": "int8", "cpu_threads": 8,
                            "download_root": str(tmp_path)}
    call = model.calls[0]
    assert call["task"] == "translate" and call["language"] == "ur" and call["initial_prompt"] is None
    assert call["beam_size"] == 5 and call["vad_filter"] is True
    assert call["vad_parameters"] == {"min_silence_duration_ms": 500}
    assert call["condition_on_previous_text"] is False
    assert out == {"language": "ur", "language_probability": 1.0, "segments": [
        {"start": 0.0, "end": 4.212, "text": "Pointer size depends on the machine.",
         "avg_logprob": -0.41, "no_speech_prob": 0.35, "compression_ratio": 1.83}]}


def test_the_model_is_loaded_once_and_reused(fake_whisper, tmp_path):
    for _ in range(3):
        call_engine(tmp_path)
    assert fake_whisper.instances == 1


def test_missing_faster_whisper_is_an_internal_problem(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)    # makes the import fail
    monkeypatch.setattr(audio, "_model", None)
    monkeypatch.setattr(audio, "_model_name", None)
    with pytest.raises(AudioProblem) as err:
        call_engine(tmp_path)
    assert err.value.message == audio.MSG_INTERNAL


# ================================================================ part 2: offsets, cache, resume (fake engine)

RECORDING_SECONDS = 1500.0
PAUSES = [(610.0, 611.0), (1190.0, 1192.0)]          # cuts land at 610.5 and 1191.0


class FakeEngine:
    """Stands in for ffprobe, ffmpeg and Whisper: no model, no internet, no real audio."""

    def __init__(self):
        self.seconds, self.silences = RECORDING_SECONDS, list(PAUSES)
        self.converted = 0
        self.calls = []              # one entry per model call
        self.fail_on_call = None     # the call number that raises, to imitate a crash

    def probe(self, path):
        return self.seconds

    def convert(self, src, dst, denoise=False):
        self.converted += 1
        return self.seconds

    def find_silences(self, wav, seconds):
        return list(self.silences)

    @staticmethod
    def read_chunk(wav, chunk):
        return np.zeros(int(round(chunk.seconds)), dtype=np.float32)   # one "sample" per second keeps tests light

    @staticmethod
    def make_segments(seconds: int) -> list[dict]:
        """Default speech: an 8-second sentence every 10 seconds of the chunk. Tests may replace this."""
        return [seg(t, t + 8, f"Sentence {t}.") for t in range(0, seconds - 8, 10)]

    def transcribe(self, samples, task, language, initial_prompt=None, *, model_name, beam_size, model_dir):
        self.calls.append((task, language, model_name, len(samples)))
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("model crashed")
        return {"language": language or "ur", "language_probability": 1.0,
                "segments": self.make_segments(len(samples))}


@pytest.fixture
def engine(monkeypatch, data_dir, clean_env):
    fake = FakeEngine()
    monkeypatch.setattr(audio, "probe_duration", fake.probe)
    monkeypatch.setattr(audio, "convert_to_wav", fake.convert)
    monkeypatch.setattr(audio, "find_silences", fake.find_silences)
    monkeypatch.setattr(audio, "read_chunk", fake.read_chunk)
    monkeypatch.setattr(audio, "transcribe_audio", fake.transcribe)
    return fake


def make_meta(name: str = "L4_pointers.mp3") -> ResourceMeta:
    return ResourceMeta(resource_id="r1", course_id="c1", file_name=name, file_sha256="a" * 64,
                        precheck=PrecheckResult(source_type="audio"))


def run_recording() -> audio.RecordingTranscript:
    return audio.transcribe_recording(Path("lecture.mp3"), make_meta(), audio.read_settings(), Timer())


def test_place_segments_adds_the_chunk_start_and_stays_inside_the_chunk():
    raw = {"language": "ur", "segments": [
        {"start": 0.0, "end": 4.0, "text": "a", "avg_logprob": -0.2, "no_speech_prob": 0.1, "compression_ratio": 1.2},
        {"start": 578.0, "end": 583.0, "text": "b", "avg_logprob": -0.2, "no_speech_prob": 0.1,
         "compression_ratio": 1.2}]}                     # the second one runs past the chunk's end
    placed = audio.place_segments(raw, Chunk(1, 610.5, 1191.0))
    assert [(s["start"], s["end"]) for s in placed] == [(610.5, 614.5), (1188.5, 1191.0)]
    assert all(s["chunk"] == 1 and s["source_lang"] == "ur" for s in placed)


def test_offsets_put_every_segment_on_the_original_timeline(engine):
    result = run_recording()
    assert [(c.start, c.end) for c in result.chunks] == [(0.0, 610.5), (610.5, 1191.0), (1191.0, 1500.0)]
    assert len(engine.calls) == 3
    first_of_chunk1 = next(s for s in result.segments if s["chunk"] == 1)
    assert (first_of_chunk1["start"], first_of_chunk1["end"]) == (610.5, 618.5)
    for s in result.segments:
        chunk = result.chunks[s["chunk"]]
        assert chunk.start <= s["start"] <= s["end"] <= chunk.end
    for a, b in zip(result.segments, result.segments[1:]):
        assert a["end"] <= b["start"]                    # increasing and never overlapping
    assert {s["source_lang"] for s in result.segments} == {"ur"}


def test_second_run_uses_the_cache_without_converting_or_transcribing(engine):
    first = run_recording()
    second = run_recording()
    assert len(engine.calls) == 3 and engine.converted == 1
    assert (second.from_cache, second.transcribed) == (3, 0)
    assert second.segments == first.segments


def test_a_crash_midway_resumes_from_the_chunks_already_cached(engine):
    engine.fail_on_call = 3                              # the third chunk's model call fails
    first = run_recording()
    assert first.failed_chunks == [2] and first.transcribed == 2
    engine.fail_on_call = None
    second = run_recording()
    assert len(engine.calls) == 4                        # only the missing chunk went to the model again
    assert (second.failed_chunks, second.from_cache, second.transcribed) == ([], 2, 1)


def test_cache_key_changes_with_every_setting_that_changes_the_words(data_dir):
    sha, chunk = "a" * 64, Chunk(1, 610.5, 1191.0)
    base = audio.AudioSettings(model="medium", language="ur", beam_size=5, denoise=False, model_dir=Path("m"))
    variants = [base, replace(base, task="transcribe"), replace(base, model="large-v3"),
                replace(base, language=None), replace(base, beam_size=2), replace(base, denoise=True)]
    assert len({audio.chunk_cache_path(sha, chunk, s) for s in variants}) == len(variants)
    assert audio.chunk_cache_path(sha, chunk, base) == audio.chunk_cache_path(
        sha, chunk, replace(base, model_dir=Path("somewhere/else")))      # where the model lives doesn't matter
    other_plan = Chunk(1, 610.5, 900.0)                  # same index and start, different end
    assert audio.chunk_cache_path(sha, other_plan, base) != audio.chunk_cache_path(sha, chunk, base)


def test_a_silent_chunk_is_never_sent_to_the_model(engine):
    engine.seconds, engine.silences = 1300.0, [(590.0, 1250.0)]
    result = run_recording()
    assert [c.silent for c in result.chunks] == [False, True, False]
    assert len(engine.calls) == 2
    assert not any(600 <= s["start"] < 1200 for s in result.segments)


def test_a_damaged_cache_file_is_ignored_and_rebuilt(engine):
    first = run_recording()
    broken = audio.chunk_cache_path("a" * 64, first.chunks[0], audio.read_settings())
    broken.write_text("{ not json", encoding="utf-8")
    second = run_recording()
    assert len(engine.calls) == 4 and second.transcribed == 1
    assert second.segments == first.segments


def test_a_model_problem_stops_the_whole_recording(engine, monkeypatch, data_dir):
    def broken(*args, **kwargs):
        raise AudioProblem(audio.MSG_INTERNAL, "model download failed")
    monkeypatch.setattr(audio, "transcribe_audio", broken)
    with pytest.raises(AudioProblem):
        run_recording()
    assert not (data_dir / "r1" / "raw" / "audio_tmp").exists()     # temp files still cleaned up


# ================================================================ part 3: hallucination filter

def test_the_filter_drops_each_kind_of_hallucination_and_rewords_nothing():
    segments = [
        seg(0, 8, "Pointers store memory addresses."),
        seg(10, 18, "   "),                                           # empty
        seg(20, 28, "Okay.", logprob=-1.3, no_speech=0.8),            # Whisper heard silence
        seg(30, 38, "the the the the the the the the", compression=3.1),   # looping
        seg(40, 48, "Thanks for watching!", logprob=-0.9),            # stock phrase, unsure
        seg(50, 54, "Right?"), seg(54, 58, "Right?"), seg(58, 62, "right"),   # 3 times in a row
        seg(70, 78, "A 64-bit machine has 8-byte pointers."),
    ]
    kept, dropped = audio.filter_hallucinations(list(reversed(segments)))   # input order doesn't matter
    assert [s["text"] for s in kept] == ["Pointers store memory addresses.", "Right?",
                                         "A 64-bit machine has 8-byte pointers."]
    assert dropped == {"empty": 1, "silence": 1, "loop": 1, "stock phrase": 1, "repeat": 2}


def test_a_stock_phrase_is_dropped_only_when_whisper_was_unsure():
    assert audio.drop_reason(seg(0, 4, "Thanks for watching!", logprob=-0.2, no_speech=0.1)) is None
    assert audio.drop_reason(seg(0, 4, "Thanks for watching!", logprob=-0.9)) == "stock phrase"
    assert audio.drop_reason(seg(0, 4, "Subtitles by the Amara.org community", no_speech=0.7)) == "stock phrase"


def test_a_line_said_twice_is_kept_twice():
    kept, dropped = audio.filter_hallucinations([seg(0, 2, "Yes sir."), seg(2, 4, "Yes sir.")])
    assert len(kept) == 2 and not dropped


# ================================================================ part 3: timestamps and grouping

def spans(groups: list[list[dict]]) -> list[tuple[float, float]]:
    return [(g[0]["start"], g[-1]["end"]) for g in groups]


def test_clock_and_part_heading():
    assert audio.clock(5) == "00:05"
    assert audio.clock(760.9) == "12:40"
    assert audio.clock(3723) == "01:02:03"
    assert audio.part_heading(3, 760, 850) == "Part 3 (12:40 to 14:10)"          # the guide's example
    assert audio.part_heading(9, 3590, 3700) == "Part 9 (59:50 to 01:01:40)"


def test_a_group_closes_at_the_first_sentence_end_after_60_seconds():
    segments = [seg(t, t + 5, "words." if t % 20 == 15 else "words") for t in range(0, 300, 5)]
    assert spans(audio.group_segments(segments)) == [(0, 60), (60, 120), (120, 180), (180, 240), (240, 300)]


def test_without_punctuation_a_group_closes_after_120_seconds():
    segments = [seg(t, t + 5, "words without a full stop") for t in range(0, 300, 5)]
    assert spans(audio.group_segments(segments)) == [(0, 120), (120, 240), (240, 300)]


def test_a_group_never_grows_past_150_seconds():
    segments = [seg(0, 20, "words"), seg(40, 60, "words"), seg(170, 180, "words.")]
    assert spans(audio.group_segments(segments)) == [(0, 60), (170, 180)]


def test_a_short_last_group_joins_the_one_before():
    segments = [seg(t, t + 5, "words.") for t in range(0, 75, 5)]
    assert spans(audio.group_segments(segments)) == [(0, 75)]


# ================================================================ part 3: load() from end to end (fake engine)

def load_doc(name: str = "L4_pointers.mp3") -> ParsedDocument:
    return audio.load(Path("lecture.mp3"), make_meta(name))


def test_a_lecture_becomes_valid_transcript_blocks(engine):
    doc = load_doc()
    assert doc.quality.status == "ok" and doc.quality.warnings == []
    assert (doc.source_type, doc.title, doc.parser) == ("audio", "L4 pointers", "faster-whisper")
    assert [b.seq for b in doc.blocks] == list(range(len(doc.blocks)))
    for b in doc.blocks:
        assert b.kind == "transcript" and b.text and b.lang == "en"
        assert b.heading_path[0] == doc.title
        assert re.fullmatch(r"Part \d+ \(\d\d:\d\d to \d\d:\d\d\)", b.heading_path[1])
        assert b.heading_path[1].startswith(f"Part {b.seq + 1} (")
        assert b.extra == {"source_lang": "ur", "task": "translate", "model": "medium"}
        assert 0 <= b.confidence <= 1
    assert doc.quality.units_total == 1500
    assert doc.quality.chars_total == sum(len(b.text) for b in doc.blocks)
    ParsedDocument.model_validate(doc.model_dump())      # the contract's own rules, as the dispatcher checks them


def test_block_times_increase_and_never_overlap(engine):
    blocks = load_doc().blocks
    for b in blocks:
        assert b.loc.t_start <= b.loc.t_end
    for a, b in zip(blocks, blocks[1:]):
        assert a.loc.t_start < b.loc.t_start
        assert a.loc.t_end <= b.loc.t_start
    assert blocks[-1].loc.t_end == pytest.approx(1499.0)     # the last chunk's offset reached the blocks


def test_blocks_are_60_to_120_seconds(engine):
    lengths = [b.loc.t_end - b.loc.t_start for b in load_doc().blocks]
    assert all(60 <= x <= 120 for x in lengths[:-1])
    assert 0 < lengths[-1] <= audio.BLOCK_MAX_SECONDS


def test_hallucinations_never_reach_the_blocks(engine):
    engine.seconds, engine.silences = 200.0, []
    engine.make_segments = lambda seconds: [
        seg(0, 8, "Pointers store memory addresses."), seg(10, 18, "   "),
        seg(20, 28, "Thanks for watching!", logprob=-0.9),
        seg(30, 38, "the the the the the the the the", compression=3.1),
        seg(40, 48, "Okay.", logprob=-1.3, no_speech=0.8),
        seg(50, 54, "Right?"), seg(54, 58, "Right?"), seg(58, 62, "Right?"),
        seg(70, 78, "A 64-bit machine has 8-byte pointers.")]
    text = " ".join(b.text for b in load_doc().blocks)
    assert "Pointers store memory addresses." in text and "8-byte pointers." in text
    assert text.count("Right?") == 1
    for gone in ("Thanks for watching", "the the the", "Okay."):
        assert gone not in text


def test_a_second_upload_of_the_same_file_uses_the_cache(engine):
    first = load_doc()
    second = load_doc()
    assert len(engine.calls) == 3 and engine.converted == 1
    assert [b.model_dump() for b in second.blocks] == [b.model_dump() for b in first.blocks]


def test_a_silent_recording_fails_with_a_warning(engine):
    engine.seconds, engine.silences = 300.0, [(0.0, 300.0)]
    doc = load_doc()
    assert doc.quality.status == "failed" and doc.blocks == []
    assert doc.quality.warnings == [audio.MSG_NO_SPEECH]
    assert engine.calls == []                            # a silent chunk never reaches the model


def test_a_too_long_recording_fails_with_a_warning(engine):
    engine.seconds = audio.MAX_MINUTES * 60 + 60
    doc = load_doc()
    assert doc.quality.status == "failed" and doc.quality.warnings == [audio.MSG_TOO_LONG]
    assert engine.converted == 0                         # refused before any work was done


def test_a_long_recording_succeeds_with_a_warning(engine):
    engine.seconds, engine.silences = audio.WARN_MINUTES * 60 + 60, []
    doc = load_doc()
    assert doc.quality.status == "ok" and doc.blocks
    assert doc.quality.warnings == ([audio.MSG_LONG] if audio.MSG_LONG else [])


def test_one_failed_chunk_gives_a_degraded_document(engine):
    engine.fail_on_call = 2                              # the middle chunk (610.5 to 1191 s) fails
    doc = load_doc()
    assert doc.quality.status == "degraded"
    assert audio.MSG_PARTIAL in doc.quality.warnings
    assert doc.blocks
    assert not any(620 < b.loc.t_start < 1180 for b in doc.blocks)


def test_failed_chunks_with_no_other_speech_is_an_internal_failure(engine):
    engine.seconds, engine.silences = 300.0, []
    engine.fail_on_call = 1
    doc = load_doc()
    assert doc.quality.status == "failed" and doc.quality.warnings == [audio.MSG_INTERNAL]


def test_an_unexpected_bug_becomes_a_failed_document(engine, monkeypatch):
    def bug(*args, **kwargs):
        raise ZeroDivisionError("a bug in the loader")
    monkeypatch.setattr(audio, "build_blocks", bug)
    doc = load_doc()                                     # must not raise
    assert doc.quality.status == "failed" and doc.quality.warnings == [audio.MSG_INTERNAL]


def test_missing_ffmpeg_gives_a_failed_document(data_dir, clean_env, monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    doc = audio.load(Path("lecture.mp3"), make_meta())
    assert doc.quality.status == "failed" and doc.quality.warnings == [audio.MSG_INTERNAL]


@needs_ffmpeg
def test_a_corrupt_file_gives_a_failed_document_and_does_not_raise(tmp_path, data_dir, clean_env):
    bad = tmp_path / "broken.mp3"
    bad.write_bytes(b"this is not audio at all " * 100)
    doc = audio.load(bad, make_meta("broken.mp3"))
    assert doc.quality.status == "failed" and doc.blocks == []
    assert doc.quality.warnings == [audio.MSG_UNREADABLE]


def test_through_the_dispatcher_and_saved_as_parsed_json(engine, tmp_path, data_dir):
    upload = tmp_path / "L4_pointers.mp3"
    upload.write_bytes(b"pretend this is an mp3 " * 50)          # the fake engine never reads it
    doc = ingest_file(upload, "r9", "c1")
    assert doc.quality.status == "ok" and doc.source_type == "audio"
    saved = json.loads((data_dir / "r9" / "parsed.json").read_text(encoding="utf-8"))
    assert saved["blocks"][0]["loc"]["t_start"] == 0.0
    assert saved["blocks"][0]["heading_path"][0] == "L4 pointers"


# ================================================================ part 3: the real model (opt-in)

@needs_model
def test_real_model_on_the_short_sample(data_dir):
    path = SAMPLES / "short_mixed.mp3"
    meta = ResourceMeta(resource_id="real1", course_id="c1", file_name=path.name,
                        file_sha256=file_sha256(path), precheck=PrecheckResult(source_type="audio"))
    doc = audio.load(path, meta)
    assert doc.quality.status == "ok", doc.quality.warnings
    assert doc.blocks and all(b.lang == "en" for b in doc.blocks)
    assert doc.blocks[0].heading_path[0] == "short mixed"
    assert 0 <= doc.blocks[0].loc.t_start < doc.blocks[-1].loc.t_end <= 26