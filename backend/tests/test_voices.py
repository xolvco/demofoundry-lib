"""voices module tests.

Run: python tests/test_voices.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry import config, voices  # noqa: E402


def test_clone_voice_requires_api_key():
    old = config.ELEVENLABS_API_KEY
    try:
        config.ELEVENLABS_API_KEY = ""
        try:
            voices.clone_voice("Test", [("a.wav", b"abc", "audio/wav")])
            assert False, "expected VoiceCloneError"
        except voices.VoiceCloneError as e:
            assert e.status_code == 400
            assert "ELEVENLABS_API_KEY" in e.detail
    finally:
        config.ELEVENLABS_API_KEY = old


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
