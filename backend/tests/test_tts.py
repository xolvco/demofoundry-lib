"""TTS silent-fallback tests (no key needed).  Run: python tests/test_tts.py"""

from __future__ import annotations

import os
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry.pipeline import tts  # noqa: E402


def test_silent_produces_wav_with_duration():
    with tempfile.TemporaryDirectory() as d:
        path, dur, timings = tts.synth("Hello there, this is a demo.", "default", Path(d) / "a")
        assert Path(path).exists()
        assert dur > 0
        assert timings == []  # silent fallback has no word timings
        with wave.open(str(path)) as w:
            assert w.getframerate() == tts.SAMPLE_RATE


def test_longer_text_is_longer_audio():
    with tempfile.TemporaryDirectory() as d:
        _, short, _ = tts.synth("One.", "default", Path(d) / "s")
        _, long, _ = tts.synth("One two three four five six seven eight nine ten.",
                               "default", Path(d) / "l")
        assert long > short


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(); print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
