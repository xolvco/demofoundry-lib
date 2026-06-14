"""Project store — SQLite + local asset folder (MVP).

Single-user/local now; the schema is keyed so it becomes per-user without change
(add an owner column). Steps are stored as a JSON blob on the project row.
"""

from __future__ import annotations

import json
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
                srt_path TEXT
            )"""
        )


def create(project: dict) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO projects
               (id, name, target_url, description, voice_id, steps_json, status)
               VALUES (?,?,?,?,?,?, 'new')""",
            (
                project["id"], project.get("name", ""), project["target_url"],
                project.get("description", ""), project.get("voice_id", ""),
                json.dumps(project.get("steps", [])),
            ),
        )


def get(pid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["steps"] = json.loads(d.pop("steps_json") or "[]")
    return d


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


def asset_dir(pid: str) -> Path:
    d = config.WORKSPACE / pid
    d.mkdir(parents=True, exist_ok=True)
    return d
