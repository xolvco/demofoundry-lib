"""serde round-trip tests.  Run: python tests/test_serde.py"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry import serde  # noqa: E402
from demofoundry.models import (  # noqa: E402
    ActionRecord,
    ActionType,
    Rect,
    RenderPlan,
    Segment,
    SegmentOp,
    Step,
)


def test_steps_round_trip():
    steps = [
        Step(id="s1", action=ActionType.CLICK, target="#go", narration_text="Go."),
        Step(id="s2", action=ActionType.TYPE, target="#e", value="a@b.com",
             zoom_target="#sum", pronunciation_override="a at b dot com"),
    ]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "steps.json"
        serde.save_steps(steps, p)
        back = serde.load_steps(p)
    assert [s.id for s in back] == ["s1", "s2"]
    assert back[1].action is ActionType.TYPE
    assert back[1].zoom_target == "#sum"
    assert back[1].speech_text() == "a at b dot com"


def test_records_round_trip():
    recs = {
        "s1": ActionRecord("s1", 0.0, 1.5, click_xy=(10.0, 20.0),
                           zoom_rect=Rect(1, 2, 3, 4)),
    }
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "records.json"
        serde.save_records(recs, p)
        back = serde.load_records(p)
    r = back["s1"]
    assert r.click_xy == (10.0, 20.0)
    assert r.zoom_rect.width == 3
    assert abs(r.duration - 1.5) < 1e-9


def test_plan_round_trip():
    plan = RenderPlan(segments=[
        Segment("s1", 0.0, 1.0, 2.0, SegmentOp.HOLD, hold_tail=1.0, audio_path="a.wav"),
        Segment("s2", 1.0, 5.0, 2.0, SegmentOp.SPEED, speed=2.0),
    ])
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "plan.json"
        serde.save_plan(plan, p)
        back = serde.load_plan(p)
    assert back.segments[0].op is SegmentOp.HOLD
    assert back.segments[1].speed == 2.0
    assert abs(back.total_duration - 4.0) < 1e-9


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
