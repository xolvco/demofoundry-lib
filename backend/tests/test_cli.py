"""CLI plumbing tests for the no-binary steps (tts, sync).

Exercises serde + argparse + the library together, end-to-end on temp files,
with no browser / ffmpeg / API keys.  Run: python tests/test_cli.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from demofoundry import cli, serde  # noqa: E402
from demofoundry.models import ActionRecord  # noqa: E402


def _write_steps(p: Path) -> None:
    p.write_text(
        '[{"id":"s1","action":"click","target":"#go","narration_text":"Click to start the flow."},'
        ' {"id":"s2","action":"type","target":"#e","value":"x","narration_text":"Type your email and continue now."}]',
        encoding="utf-8",
    )


def test_tts_then_sync_via_cli():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        steps = d / "steps.json"
        _write_steps(steps)

        # tts step
        assert cli.main(["tts", "--steps", str(steps), "--out-dir", str(d)]) == 0
        durations = serde.load_json(d / "durations.json")
        assert set(durations) == {"s1", "s2"} and all(v > 0 for v in durations.values())

        # fake capture output so sync has records
        records = {
            "s1": ActionRecord("s1", 0.0, 0.5),   # short action -> hold
            "s2": ActionRecord("s2", 0.5, 6.0),   # long action  -> speed
        }
        serde.save_records(records, d / "records.json")

        # sync step
        rc = cli.main([
            "sync", "--steps", str(steps), "--records", str(d / "records.json"),
            "--durations", str(d / "durations.json"),
            "--audio", str(d / "audio.json"), "--out", str(d / "plan.json"),
        ])
        assert rc == 0
        plan = serde.load_plan(d / "plan.json")
        ops = {s.step_id: s.op.value for s in plan.segments}
        assert ops["s1"] == "hold"
        assert ops["s2"] in ("speed", "trim")
        # total timeline equals the narration total
        assert abs(plan.total_duration - sum(durations.values())) < 1e-6


def test_parser_registers_all_steps():
    import argparse

    parser = cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert set(sub.choices) >= {
        "capture", "script", "tts", "sync", "compose", "render", "serve"
    }


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
