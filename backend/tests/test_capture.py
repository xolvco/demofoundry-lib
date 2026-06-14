"""Capture smoke test against a bundled HTML fixture (no app dependency).

Exercises the real Playwright path: drive a static page, record video, capture
per-step timestamps and element rects. Skips cleanly when Playwright or the
Chromium browser isn't installed, so the suite stays green without binaries.

    python tests/test_capture.py
    # (skips unless: pip install playwright && playwright install chromium)
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry.models import ActionType, Step  # noqa: E402
from demofoundry.pipeline import capture  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample.html"


class Skip(Exception):
    """Raised to mark a test skipped (missing optional binary)."""


def _playwright_installed() -> bool:
    try:
        import playwright.async_api  # noqa: F401
        return True
    except Exception:
        return False


def _steps() -> list[Step]:
    return [
        Step("s1", ActionType.CLICK, target="[data-testid='start']",
             narration_text="Click get started."),
        Step("s2", ActionType.TYPE, target="#email", value="demo@acme.com",
             narration_text="Enter your email."),
        Step("s3", ActionType.CLICK, target="text=Continue",
             zoom_target="#summary", narration_text="Confirm your order."),
    ]


def test_capture_produces_video_and_records():
    if not _playwright_installed():
        raise Skip("playwright not installed")

    url = FIXTURE.resolve().as_uri()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        try:
            video, records = asyncio.run(capture.capture(url, _steps(), out))
        except Exception as exc:  # missing browser binary -> skip, not fail
            msg = str(exc).lower()
            if any(k in msg for k in ("executable", "playwright install", "browsertype")):
                raise Skip("chromium not installed (playwright install chromium)")
            raise

        # a recording was produced
        assert video.exists() and video.stat().st_size > 0

        # one record per step, in order, with non-negative durations
        assert set(records) == {"s1", "s2", "s3"}
        assert records["s2"].started_at >= records["s1"].started_at
        assert records["s3"].started_at >= records["s2"].started_at
        for r in records.values():
            assert r.ended_at >= r.started_at

        # the click captured a coordinate; the zoom target captured a rect
        assert records["s1"].click_xy is not None
        assert records["s3"].zoom_rect is not None


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = skipped = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  ok   {t.__name__}")
        except Skip as e:
            skipped += 1
            print(f"  skip {t.__name__}: {e}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{passed} passed, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
