"""Compose tests.

  - write_srt is pure Python and always runs.
  - the ffmpeg render generates a tiny source clip, composes a 2-segment plan
    (exercising hold, speed, zoom, highlight, click marker, concat), and checks
    the output is a real video. Skips cleanly when ffmpeg isn't installed.

    python tests/test_compose.py
    # (render skips unless ffmpeg is on PATH)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry.models import (  # noqa: E402
    ActionRecord,
    ActionType,
    Rect,
    RenderPlan,
    Segment,
    SegmentOp,
    Step,
)
from demofoundry.pipeline import compose  # noqa: E402


class Skip(Exception):
    pass


def _steps() -> list[Step]:
    return [
        Step("s1", ActionType.CLICK, narration_text="First we open the dashboard."),
        Step("s2", ActionType.CLICK, narration_text="Then we confirm the order."),
    ]


def _plan() -> RenderPlan:
    return RenderPlan(segments=[
        # short action under a 2s narration -> freeze the tail
        Segment("s1", 0.0, 1.0, 2.0, SegmentOp.HOLD, hold_tail=1.0),
        # 4s action over a 2s narration -> 2x speed
        Segment("s2", 1.0, 5.0, 2.0, SegmentOp.SPEED, speed=2.0),
    ])


def _records() -> dict[str, ActionRecord]:
    return {
        "s1": ActionRecord("s1", 0.0, 1.0, click_xy=(960.0, 540.0),
                           highlight_rect=Rect(100, 100, 200, 80)),
        "s2": ActionRecord("s2", 1.0, 5.0, zoom_rect=Rect(400, 300, 300, 200)),
    }


def test_write_srt_from_original_text():
    with tempfile.TemporaryDirectory() as d:
        srt = compose.write_srt(_steps(), _plan(), Path(d) / "demo.srt")
        text = srt.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in text   # step 1 spans its 2s slot
    assert "00:00:02,000 --> 00:00:04,000" in text   # step 2 follows
    assert "First we open the dashboard." in text
    assert "Then we confirm the order." in text


def test_compose_renders_a_real_video():
    if not shutil.which("ffmpeg"):
        raise Skip("ffmpeg not on PATH")

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        src = d / "src.mp4"
        # generate a 6s test source so both segment slices are in range
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", "testsrc=duration=6:size=1920x1080:rate=30",
             "-pix_fmt", "yuv420p", str(src)],
            check=True, capture_output=True,
        )

        out = compose.render(_plan(), src, _records(), d / "render")
        assert out.exists() and out.stat().st_size > 0

        # if ffprobe is available, the output should be ~4s (sum of narration)
        if shutil.which("ffprobe"):
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(out)],
                check=True, capture_output=True, text=True,
            )
            dur = float(probe.stdout.strip())
            assert abs(dur - 4.0) < 1.0, f"duration {dur} not ~4.0s"


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = skipped = failed = 0
    for t in tests:
        try:
            t(); passed += 1; print(f"  ok   {t.__name__}")
        except Skip as e:
            skipped += 1; print(f"  skip {t.__name__}: {e}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{passed} passed, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
