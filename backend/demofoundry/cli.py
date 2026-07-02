"""DemoFoundry CLI - each pipeline step as a subcommand.

Steps chain on the filesystem (JSON artifacts), so each stage runs and is tested
in isolation:

    demofoundry capture --url URL --steps steps.json --out-dir work
    demofoundry script  --steps steps.json --desc "tour of checkout"
    demofoundry tts     --steps steps.json --out-dir work
    demofoundry sync    --steps steps.json --records work/records.json \\
                        --durations work/durations.json --out work/plan.json
    demofoundry compose --steps steps.json --plan work/plan.json \\
                        --video work/recording.webm --records work/records.json \\
                        --out work/demo.mp4
    demofoundry render  --url URL --steps steps.json --out-dir work   # all of it
    demofoundry serve   --port 8000                                   # web app
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from . import serde
from .pipeline import compose, sync, tts


def _cmd_capture(args) -> int:
    from .pipeline import capture

    steps = serde.load_steps(args.steps)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    video, records = asyncio.run(capture.capture(args.url, steps, out / "capture"))
    dest = out / "recording.webm"
    shutil.copyfile(video, dest)
    serde.save_records(records, out / "records.json")
    print(f"recording: {dest}")
    print(f"records:   {out / 'records.json'}")
    return 0


def _cmd_script(args) -> int:
    from .pipeline import scripting

    steps = serde.load_steps(args.steps)
    generated = scripting.generate(args.desc, steps)
    scripting.apply(steps, generated)
    serde.save_steps(steps, args.out or args.steps)
    print(f"narration written to {args.out or args.steps}")
    return 0


def _cmd_tts(args) -> int:
    steps = serde.load_steps(args.steps)
    out = Path(args.out_dir)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    durations, audio = {}, {}
    for step in steps:
        path, dur, _ = tts.synth(step.speech_text(), args.voice, out / "audio" / step.id)
        durations[step.id] = dur
        audio[step.id] = str(path)
    serde.save_json(durations, out / "durations.json")
    serde.save_json(audio, out / "audio.json")
    print(f"durations: {out / 'durations.json'}")
    return 0


def _cmd_sync(args) -> int:
    steps = serde.load_steps(args.steps)
    records = serde.load_records(args.records)
    durations = serde.load_json(args.durations)
    audio = serde.load_json(args.audio) if args.audio else {}
    plan = sync.build_plan(steps, records, durations, audio)
    serde.save_plan(plan, args.out)
    print(f"plan: {args.out}  ({plan.total_duration:.1f}s, {len(plan.segments)} segments)")
    return 0


def _cmd_compose(args) -> int:
    steps = serde.load_steps(args.steps)
    plan = serde.load_plan(args.plan)
    records = serde.load_records(args.records)
    out = Path(args.out)
    video = compose.render(plan, Path(args.video), records, out.parent, out.name)
    srt = compose.write_srt(steps, plan, out.with_suffix(".srt"))
    print(f"video: {video}")
    print(f"srt:   {srt}")
    return 0


def _cmd_render(args) -> int:
    from . import render

    steps = serde.load_steps(args.steps)
    if args.desc:
        from .pipeline import scripting

        scripting.apply(steps, scripting.generate(args.desc, steps))
    video, srt = asyncio.run(
        render.render_to_files(
            args.url, steps, Path(args.out_dir), args.voice,
            on_status=lambda s: print(f"  …{s}"),
            voice_speed=args.voice_speed,
            scene_lead_ms=args.scene_lead,
        )
    )
    print(f"video: {video}")
    print(f"srt:   {srt}")
    return 0


def _cmd_ingest_pptx(args) -> int:
    from .pipeline import pptx_ingest

    if not pptx_ingest.powerpoint_available():
        print(
            "error: no PPTX export backend found. Install Microsoft PowerPoint "
            "(Windows) or LibreOffice+soffice with pypdfium2.",
            file=sys.stderr,
        )
        return 2
    info = pptx_ingest.ingest(Path(args.pptx), Path(args.out_dir), narrate=not args.no_narrate)
    print(f"slides:  {info['slides']}  (speaker notes on {info['notes_found']})")
    print(f"deck:    {info['deck_html']}")
    print(f"steps:   {info['steps']}")
    print("next:    demofoundry render --url \"%s\" --steps \"%s\" --out-dir <dir> --voice <id>"
          % (info["deck_url"], info["steps"]))
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("demofoundry.main:app", host="127.0.0.1", port=args.port, reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="demofoundry", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("capture", help="drive + record the target app")
    c.add_argument("--url", required=True)
    c.add_argument("--steps", required=True)
    c.add_argument("--out-dir", required=True)
    c.set_defaults(func=_cmd_capture)

    c = sub.add_parser("script", help="Claude writes narration + suggestions")
    c.add_argument("--steps", required=True)
    c.add_argument("--desc", required=True)
    c.add_argument("--out", help="defaults to overwriting --steps")
    c.set_defaults(func=_cmd_script)

    c = sub.add_parser("tts", help="render per-step narration clips")
    c.add_argument("--steps", required=True)
    c.add_argument("--out-dir", required=True)
    c.add_argument("--voice", default="default")
    c.set_defaults(func=_cmd_tts)

    c = sub.add_parser("sync", help="build the time-remap plan")
    c.add_argument("--steps", required=True)
    c.add_argument("--records", required=True)
    c.add_argument("--durations", required=True)
    c.add_argument("--audio")
    c.add_argument("--out", required=True)
    c.set_defaults(func=_cmd_sync)

    c = sub.add_parser("compose", help="render the plan to MP4 + SRT")
    c.add_argument("--steps", required=True)
    c.add_argument("--plan", required=True)
    c.add_argument("--video", required=True)
    c.add_argument("--records", required=True)
    c.add_argument("--out", required=True)
    c.set_defaults(func=_cmd_compose)

    c = sub.add_parser("render", help="run the whole pipeline")
    c.add_argument("--url", required=True)
    c.add_argument("--steps", required=True)
    c.add_argument("--out-dir", required=True)
    c.add_argument("--desc", help="optional: let Claude write narration first")
    c.add_argument("--voice", default="default")
    c.add_argument("--voice-speed", type=float, default=None,
                   help="speaking rate; 1.0 normal, <1.0 slower (0.7–1.2). "
                        "Default from config (0.9).")
    c.add_argument("--scene-lead", type=int, default=None, metavar="MS",
                   help="silent hold (ms) on each new screen before the voice "
                        "starts. Default from config (600).")
    c.set_defaults(func=_cmd_render)

    c = sub.add_parser("ingest-pptx", help="turn a .pptx into a narratable deck")
    c.add_argument("pptx", help="path to the .pptx file")
    c.add_argument("--out-dir", required=True)
    c.add_argument("--no-narrate", action="store_true",
                   help="don't call Claude; leave narration to speaker notes / hand-authoring")
    c.set_defaults(func=_cmd_ingest_pptx)

    c = sub.add_parser("serve", help="launch the local web app")
    c.add_argument("--port", type=int, default=8000)
    c.add_argument("--reload", action="store_true")
    c.set_defaults(func=_cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
