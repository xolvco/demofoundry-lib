"""Project store — SQLite + local asset folder (MVP).

Single-user/local now; the schema is keyed so it becomes per-user without change
(add an owner column). Steps are stored as a JSON blob on the project row.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from . import config, serde
from .models import Step

# Step (de)serialization lives in serde (shared with the CLI/web layers).
step_to_dict = serde.step_to_dict
step_from_dict = serde.step_from_dict

DB_PATH = config.WORKSPACE / "demofoundry.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                target_url TEXT,
                description TEXT,
                voice_id TEXT,
                steps_json TEXT,
                status TEXT DEFAULT 'new',
                error TEXT,
                video_path TEXT,
                srt_path TEXT,
                step_results_json TEXT,
                reference TEXT,
                audio_script TEXT,
                pronunciations TEXT,
                progress TEXT,
                capture_mode TEXT DEFAULT 'web'
            )"""
        )
        # Migrate older DBs that predate later columns.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(projects)")}
        if "step_results_json" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN step_results_json TEXT")
        if "reference" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN reference TEXT")
        if "audio_script" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN audio_script TEXT")
        if "pronunciations" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN pronunciations TEXT")
        if "progress" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN progress TEXT")
        if "capture_mode" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN capture_mode TEXT DEFAULT 'web'")


def create(project: dict) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO projects
               (id, name, target_url, description, reference, audio_script, pronunciations, voice_id, steps_json, status)
               VALUES (?,?,?,?,?,?,?,?,?, 'new')""",
            (
                project["id"], project.get("name", ""), project["target_url"],
                project.get("description", ""), project.get("reference", ""),
                project.get("audio_script", ""),
                json.dumps(project.get("pronunciations", {})),
                project.get("voice_id", ""), json.dumps(project.get("steps", [])),
            ),
        )


def list_all() -> list[dict]:
    """Project summaries for the Library list, newest first."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, name, target_url, status, error, steps_json "
            "FROM projects ORDER BY rowid DESC"
        ).fetchall()
    summaries = []
    for row in rows:
        d = dict(row)
        d["step_count"] = len(json.loads(d.pop("steps_json") or "[]"))
        summaries.append(d)
    return summaries


def get(pid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["steps"] = json.loads(d.pop("steps_json") or "[]")
    # Per-step capture outcomes ({step_id: {status, error, duration}}), written
    # after the capture stage. Empty until a render has run.
    d["step_results"] = json.loads(d.pop("step_results_json", None) or "{}")
    # Pronunciation catalog ({term: spoken}) — applied to the spoken audio only,
    # the narration captions stay as written.
    d["pronunciations"] = json.loads(d.get("pronunciations") or "{}")
    return d


def set_step_results(pid: str, results: dict) -> None:
    """Persist the per-step capture outcomes for the review UI."""
    with _conn() as c:
        c.execute(
            "UPDATE projects SET step_results_json=? WHERE id=?",
            (json.dumps(results), pid),
        )


def get_steps(pid: str) -> list[Step]:
    p = get(pid)
    return [step_from_dict(s) for s in (p["steps"] if p else [])]


def set_steps(pid: str, steps: list[Step]) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE projects SET steps_json=? WHERE id=?",
            (json.dumps([step_to_dict(s) for s in steps]), pid),
        )


def update(pid: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE projects SET {cols} WHERE id=?", (*fields.values(), pid))


def delete(pid: str) -> bool:
    """Remove a project row and its rendered assets. Returns False if unknown."""
    with _conn() as c:
        cur = c.execute("DELETE FROM projects WHERE id=?", (pid,))
        if cur.rowcount == 0:
            return False
    assets = config.WORKSPACE / pid
    if assets.exists():
        shutil.rmtree(assets, ignore_errors=True)
    return True


def asset_dir(pid: str) -> Path:
    d = config.WORKSPACE / pid
    d.mkdir(parents=True, exist_ok=True)
    return d
