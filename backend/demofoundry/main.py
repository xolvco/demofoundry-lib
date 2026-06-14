"""DemoFoundry local web app — FastAPI backend + static UI.

Run:  uvicorn demofoundry.main:app --reload --port 8000
Open: http://localhost:8000
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import config, render, store
from .pipeline import scripting as scripting_api

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
    target_url: str
    description: str = ""
    voice_id: str = ""
    steps: list[StepIn] = []


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
            "description": body.description, "voice_id": body.voice_id,
            "steps": steps,
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
