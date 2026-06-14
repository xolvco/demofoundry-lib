"""Sync engine tests — runnable with plain Python (no deps):

    python backend/tests/test_sync.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry.models import ActionRecord, ActionType, SegmentOp, Step  # noqa: E402
from demofoundry.pipeline import sync  # noqa: E402


def _step(i: str) -> Step:
    return Step(id=i, action=ActionType.CLICK, narration_text="x")


def test_action_shorter_than_narration_holds():
    steps = [_step("a")]
    records = {"a": ActionRecord("a", started_at=0.0, ended_at=1.0)}  # 1s action
    durations = {"a": 4.0}  # 4s narration
    plan = sync.build_plan(steps, records, durations)
    seg = plan.segments[0]
    assert seg.op is SegmentOp.HOLD
    assert abs(seg.hold_tail - 3.0) < 1e-6   # freeze for the extra 3s
    assert abs(seg.target_duration - 4.0) < 1e-6


def test_action_longer_than_narration_speeds_up():
    steps = [_step("a")]
    records = {"a": ActionRecord("a", started_at=0.0, ended_at=6.0)}  # 6s action
    durations = {"a": 3.0}  # 3s narration
    plan = sync.build_plan(steps, records, durations)
    seg = plan.segments[0]
    assert seg.op is SegmentOp.SPEED
    assert abs(seg.speed - 2.0) < 1e-6        # 6s -> 3s = 2x
    assert seg.hold_tail < 1e-6


def test_extreme_dead_time_is_trimmed_and_padded():
    steps = [_step("a")]
    records = {"a": ActionRecord("a", started_at=0.0, ended_at=30.0)}  # 30s load
    durations = {"a": 2.0}  # 2s narration
    plan = sync.build_plan(steps, records, durations)
    seg = plan.segments[0]
    assert seg.op is SegmentOp.TRIM
    assert abs(seg.speed - sync.MAX_SPEED) < 1e-6   # capped, not 15x
    # 30s/4 = 7.5s shown > 2s narration, so no pad needed here
    assert seg.hold_tail < 1e-6


def test_total_duration_equals_sum_of_narration():
    steps = [_step("a"), _step("b"), _step("c")]
    records = {
        "a": ActionRecord("a", 0.0, 1.0),
        "b": ActionRecord("b", 1.0, 9.0),
        "c": ActionRecord("c", 9.0, 10.0),
    }
    durations = {"a": 3.0, "b": 4.0, "c": 2.0}
    plan = sync.build_plan(steps, records, durations)
    assert abs(plan.total_duration - 9.0) < 1e-6


def test_missing_action_holds_for_narration():
    steps = [_step("a")]
    plan = sync.build_plan(steps, records={}, narration_durations={"a": 5.0})
    seg = plan.segments[0]
    assert seg.op is SegmentOp.HOLD
    assert abs(seg.target_duration - 5.0) < 1e-6


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
