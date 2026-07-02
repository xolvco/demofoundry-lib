"""pptx_ingest backend selection tests.

Run: python tests/test_pptx_ingest.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry.pipeline import pptx_ingest  # noqa: E402


def test_powerpoint_available_uses_libreoffice_fallback():
    orig_win = pptx_ingest._windows_powerpoint_available
    orig_lo = pptx_ingest._libreoffice_available
    try:
        pptx_ingest._windows_powerpoint_available = lambda: False
        pptx_ingest._libreoffice_available = lambda: True
        assert pptx_ingest.powerpoint_available() is True
    finally:
        pptx_ingest._windows_powerpoint_available = orig_win
        pptx_ingest._libreoffice_available = orig_lo


def test_export_slides_selects_libreoffice_when_windows_unavailable():
    orig_win = pptx_ingest._windows_powerpoint_available
    orig_lo = pptx_ingest._libreoffice_available
    orig_win_export = pptx_ingest._export_slides_windows
    orig_lo_export = pptx_ingest._export_slides_libreoffice
    try:
        pptx_ingest._windows_powerpoint_available = lambda: False
        pptx_ingest._libreoffice_available = lambda: True
        pptx_ingest._export_slides_windows = lambda p, o: [Path("wrong.png")]
        pptx_ingest._export_slides_libreoffice = lambda p, o: [Path("slide-01.png")]
        out = pptx_ingest.export_slides(Path("deck.pptx"), Path("out"))
        assert out == [Path("slide-01.png")]
    finally:
        pptx_ingest._windows_powerpoint_available = orig_win
        pptx_ingest._libreoffice_available = orig_lo
        pptx_ingest._export_slides_windows = orig_win_export
        pptx_ingest._export_slides_libreoffice = orig_lo_export


def test_export_slides_raises_when_no_backend_available():
    orig_win = pptx_ingest._windows_powerpoint_available
    orig_lo = pptx_ingest._libreoffice_available
    try:
        pptx_ingest._windows_powerpoint_available = lambda: False
        pptx_ingest._libreoffice_available = lambda: False
        try:
            pptx_ingest.export_slides(Path("deck.pptx"), Path("out"))
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "No PPTX export backend available" in str(e)
    finally:
        pptx_ingest._windows_powerpoint_available = orig_win
        pptx_ingest._libreoffice_available = orig_lo


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
