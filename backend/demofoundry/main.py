"""DemoFoundry local web app — FastAPI backend + static UI.

Run:  uvicorn demofoundry.main:app --reload --port 8000
Open: http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import config, render, store, voices as voices_api
from .pipeline import inspect as inspect_api
from .pipeline import scripting as scripting_api
from .pipeline import screencap as screencap_api

app = FastAPI(title="DemoFoundry", version="0.1.0")
STATIC = Path(__file__).resolve().parent / "static"

# In production the React static export is served from STATIC (same origin, no
# CORS needed). This allows the Next dev server (localhost:3000) to call the API
# directly during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    store.init()


class StepIn(BaseModel):
    id: str | None = None
    action: str = "click"
    target: str | None = None
    value: str | None = None
    narration_text: str = ""
    pronunciation_override: str | None = None
    zoom_target: str | None = None
    highlight_target: str | None = None


class ProjectIn(BaseModel):
    name: str = ""
    target_url: str = ""  # the app URL for web demos; unused for desktop recordings
    description: str = ""  # the goal / mission of the demo
    reference: str = ""  # optional docs/links about the app, for the builder
    audio_script: str = ""  # optional narration the user already has
    pronunciations: dict[str, str] = {}  # term -> spoken (applied to audio only)
    voice_id: str = ""
    capture_mode: str = "web"  # "web" (drive w/ Playwright) | "desktop" (record)
    voice_speed: float | None = None  # narration rate (None = config default 0.9)
    scene_lead_ms: int | None = None  # silent hold on each new screen (None = 600)
    steps: list[StepIn] = []


class ProjectPatch(BaseModel):
    """Partial update. Only the fields present are written — so the Edit screen
    can save steps without touching the voice, and Voice can set the voice
    without touching the steps."""

    name: str | None = None
    target_url: str | None = None
    description: str | None = None
    reference: str | None = None
    audio_script: str | None = None
    pronunciations: dict[str, str] | None = None
    voice_id: str | None = None
    capture_mode: str | None = None
    voice_speed: float | None = None
    scene_lead_ms: int | None = None
    steps: list[StepIn] | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "anthropic_key": bool(config.ANTHROPIC_API_KEY),
        "elevenlabs_key": bool(config.ELEVENLABS_API_KEY),
    }


@app.get("/api/voices")
def list_voices() -> list[dict]:
    """Narrator catalog for the Voice screen (with preview_url when available)."""
    return voices_api.list_voices()


@app.post("/api/voices/clone")
async def clone_voice(
    name: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict:
    """Instant Voice Clone: upload audio sample(s) of a voice -> a new voice_id.

    The returned voice behaves like any narrator — pick it to have DemoFoundry
    speak the script in that voice. Requires ELEVENLABS_API_KEY and the
    speaker's consent to clone their voice.
    """
    blobs = [(f.filename or "sample", await f.read(), f.content_type) for f in files]
    try:
        return voices_api.clone_voice(name, blobs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Voice clone failed: {exc}")


@app.post("/api/projects")
def create_project(body: ProjectIn) -> dict:
    pid = uuid.uuid4().hex[:12]
    steps = []
    for i, s in enumerate(body.steps):
        d = s.model_dump()
        d["id"] = d.get("id") or f"s{i + 1}"
        steps.append(d)
    store.create(
        {
            "id": pid, "name": body.name, "target_url": body.target_url,
            "description": body.description, "reference": body.reference,
            "audio_script": body.audio_script, "pronunciations": body.pronunciations,
            "voice_id": body.voice_id, "capture_mode": body.capture_mode, "steps": steps,
        }
    )
    return {"id": pid}


@app.get("/api/projects")
def list_projects() -> list[dict]:
    """Project summaries for the Library list."""
    return store.list_all()


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch) -> dict:
    """Save edits from the Script / Voice screens (partial update)."""
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")

    if body.steps is not None:
        steps = []
        for i, s in enumerate(body.steps):
            d = s.model_dump()
            d["id"] = d.get("id") or f"s{i + 1}"
            steps.append(d)
        store.set_steps(pid, [store.step_from_dict(d) for d in steps])

    scalars = {
        k: v
        for k, v in {
            "name": body.name,
            "target_url": body.target_url,
            "description": body.description,
            "reference": body.reference,
            "audio_script": body.audio_script,
            "voice_id": body.voice_id,
            "capture_mode": body.capture_mode,
            "voice_speed": body.voice_speed,
            "scene_lead_ms": body.scene_lead_ms,
        }.items()
        if v is not None
    }
    if scalars:
        store.update(pid, **scalars)
    if body.pronunciations is not None:
        store.update(pid, pronunciations=json.dumps(body.pronunciations))
    return store.get(pid)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str) -> dict:
    """Remove a project (and its rendered assets) from the Library."""
    if not store.delete(pid):
        raise HTTPException(404, "project not found")
    return {"deleted": pid}


class ScriptPromptIn(BaseModel):
    inspect: bool = True          # snapshot the app's elements for selector context
    audio_script: str = ""        # optional narration the user already has


@app.post("/api/projects/{pid}/script-prompt")
async def script_prompt(pid: str, body: ScriptPromptIn) -> dict:
    """Assemble the builder prompt (optionally inspecting the app) and return it
    verbatim so the UI can show/edit it before running Claude."""
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")
    elements = await inspect_api.snapshot(p["target_url"]) if body.inspect else []
    prompt = scripting_api.build_prompt(
        p.get("description", ""),
        p.get("reference", ""),
        inspect_api.as_prompt_lines(elements),
        body.audio_script or p.get("audio_script", ""),
        p.get("steps", []),
    )
    return {
        "prompt": prompt,
        "system": scripting_api.BUILD_SYSTEM,
        "element_count": len(elements),
    }


class BuildScriptIn(BaseModel):
    prompt: str  # the (possibly edited) builder prompt to send to Claude


@app.post("/api/projects/{pid}/build-script")
def build_script(pid: str, body: BuildScriptIn) -> dict:
    """Run Claude on the prompt, save the produced steps, return the project."""
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")
    try:
        produced = scripting_api.build(body.prompt)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    steps = []
    for i, d in enumerate(produced):
        d["id"] = d.get("id") or f"s{i + 1}"
        steps.append(store.step_from_dict(d))
    store.set_steps(pid, steps)
    return store.get(pid)


@app.post("/api/projects/{pid}/script")
def script_project(pid: str) -> dict:
    """Have Claude write narration + suggest zoom/highlight for the steps."""
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")
    steps = store.get_steps(pid)
    try:
        generated = scripting_api.generate(p.get("description", ""), steps)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    scripting_api.apply(steps, generated)
    store.set_steps(pid, steps)
    return store.get(pid)


@app.post("/api/projects/{pid}/render")
async def render_project(pid: str) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")
    if not p.get("steps"):
        raise HTTPException(400, "This demo has no scenes — add at least one before generating.")
    store.update(pid, status="queued")
    asyncio.create_task(render.run(pid))  # fire-and-forget; poll status
    return {"status": "queued"}


@app.get("/api/projects/{pid}/video")
def get_video(pid: str) -> FileResponse:
    p = store.get(pid)
    if not p or not p.get("video_path"):
        raise HTTPException(404, "no video yet")
    return FileResponse(p["video_path"], media_type="video/mp4")


@app.get("/api/projects/{pid}/srt")
def get_srt(pid: str) -> FileResponse:
    p = store.get(pid)
    if not p or not p.get("srt_path"):
        raise HTTPException(404, "no subtitles yet")
    return FileResponse(p["srt_path"], media_type="application/x-subrip")


# --- Screen capture (desktop apps) -------------------------------------------
# The backend runs locally, so it can host the recorder itself. One active
# recorder per project. Times cross the API boundary in milliseconds (to match
# forgemoment + the funscript world); on disk events.json stays in seconds.
_recorders: dict[str, screencap_api.Recorder] = {}


def _screencap_dir(pid: str) -> Path:
    return store.asset_dir(pid) / "screencap"


def _events_to_ms(ev: dict) -> dict:
    return {
        "duration_ms": int(ev.get("duration", 0) * 1000),
        "size": ev.get("size", [0, 0]),
        "marks_ms": [int(t * 1000) for t in ev.get("marks", [])],
        "clicks": [
            {"t_ms": int(c["t"] * 1000), "x": c["x"], "y": c["y"]}
            for c in ev.get("clicks", [])
        ],
    }


class RecordStartIn(BaseModel):
    window: str | None = None  # capture this window (title substring); else primary monitor


@app.post("/api/projects/{pid}/record/start")
def record_start(pid: str, body: RecordStartIn) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "project not found")
    if pid in _recorders and _recorders[pid].status()["recording"]:
        raise HTTPException(409, "already recording this project")
    try:
        geo = screencap_api.resolve_geometry(window_title=body.window)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    rec = screencap_api.Recorder(_screencap_dir(pid), geo)
    rec.start()
    _recorders[pid] = rec
    store.update(pid, capture_mode="desktop")
    return {"window": body.window, "size": [geo.width, geo.height], **rec.status()}


@app.get("/api/projects/{pid}/record/status")
def record_status(pid: str) -> dict:
    rec = _recorders.get(pid)
    return rec.status() if rec else {"recording": False, "elapsed": 0, "clicks": 0, "marks": 0}


@app.post("/api/projects/{pid}/record/mark")
def record_mark(pid: str) -> dict:
    rec = _recorders.get(pid)
    if not rec or not rec.status()["recording"]:
        raise HTTPException(409, "not recording")
    rec.mark()
    return rec.status()


@app.post("/api/projects/{pid}/record/stop")
def record_stop(pid: str) -> dict:
    rec = _recorders.pop(pid, None)
    if not rec:
        raise HTTPException(409, "not recording")
    return _events_to_ms(rec.stop())  # full events.json is on disk


@app.get("/api/projects/{pid}/recording")
def get_recording(pid: str) -> FileResponse:
    path = _screencap_dir(pid) / "recording.mp4"
    if not path.exists():
        raise HTTPException(404, "no recording yet")
    return FileResponse(str(path), media_type="video/mp4")  # Starlette serves Range


@app.get("/api/projects/{pid}/events")
def get_events(pid: str) -> dict:
    path = _screencap_dir(pid) / "events.json"
    if not path.exists():
        raise HTTPException(404, "no recording yet")
    return _events_to_ms(json.loads(path.read_text(encoding="utf-8")))


class MarksIn(BaseModel):
    marks_ms: list[float]  # scene boundaries in milliseconds, from the marking UI


@app.put("/api/projects/{pid}/marks")
def put_marks(pid: str, body: MarksIn) -> dict:
    path = _screencap_dir(pid) / "events.json"
    if not path.exists():
        raise HTTPException(404, "no recording yet")
    ev = json.loads(path.read_text(encoding="utf-8"))
    ev["marks"] = sorted(m / 1000.0 for m in body.marks_ms)  # store seconds on disk
    path.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    return {"marks_ms": [int(t * 1000) for t in ev["marks"]]}
