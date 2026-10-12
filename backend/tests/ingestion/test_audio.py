"""Tests for the audio department (app/ingestion/loaders/audio.py). Owner: Zuha.

Part 1: limits, ffprobe, preprocessing, pause detection and chunking.
Most tests fake ffmpeg/ffprobe; the ones marked needs_ffmpeg use the real tools and skip without them.
"""
import json
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from app.ingestion.loaders import audio
from app.ingestion.loaders.audio import AudioProblem, Chunk

SAMPLES = Path(__file__).parent / "samples" / "audio"
needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed")


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


# ---------------------------------------------------------------- duration limits

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


# ---------------------------------------------------------------- ffprobe (faked)

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


# ---------------------------------------------------------------- conversion (faked)

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


# ---------------------------------------------------------------- pauses and chunks

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


# ---------------------------------------------------------------- reading chunks, temp folder

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


# ---------------------------------------------------------------- real ffmpeg (skip without it)

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