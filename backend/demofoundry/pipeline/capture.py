"""Capture — drive the target web app once with Playwright and record it.

Produces the two things the rest of the pipeline needs:
  1. a screen recording (webm) of the walkthrough, and
  2. an ActionRecord per step, timed against the recording clock, with the
     element rects needed for zoom/highlight in post.

Record once; narration/sync/compose run cheaply afterward and never re-drive
the browser. Requires `playwright install chromium` once.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from ..models import ActionRecord, ActionType, Rect, Step

VIEWPORT = {"width": 1920, "height": 1080}

# How long to wait on a single element before giving up. Playwright's default is
# 30s, and a bad selector pays it twice (once locating, once acting) — ~60s of
# dead air per typo while authoring. 5s is plenty for an element that exists and
# fails fast for one that doesn't. Page-load/navigation waits keep their own
# (longer) budget so genuinely slow apps still settle.
ACTION_TIMEOUT_MS = 5000

# Dwell after each action settles, before we stamp `ended_at`. Two reasons:
#   1. A client-side (SPA) nav resolves `networkidle` *before* the new route
#      paints, so without this the recorded end-frame is the OUTGOING screen —
#      the sync engine then HOLDs that stale frame for the whole narration, and
#      the demo looks frozen on the previous page. The settle lets the result
#      paint and be recorded.
#   2. It gives each scene a real slice of footage to hold/stretch instead of a
#      sub-second sliver, so a 10-step walkthrough isn't crammed into ~4s.
# `ended_at` (and the zoom/highlight rects) are read after this, so they reflect
# the settled result the viewer should see.
SETTLE_MS = 900

# For each action, the field it needs to do anything. If that field is empty the
# step matches no branch below and silently no-ops — we mark it "skipped" with
# this name so the review UI can explain why.
_REQUIRED_FIELD = {
    ActionType.NAVIGATE: "value (url)",
    ActionType.CLICK: "target (selector)",
    ActionType.TYPE: "target (selector)",
    ActionType.KEYPRESS: "value (key)",
}


async def _rect(locator) -> Rect | None:
    try:
        box = await locator.bounding_box(timeout=ACTION_TIMEOUT_MS)
    except Exception:
        box = None
    if not box:
        return None
    return Rect(box["x"], box["y"], box["width"], box["height"])


async def capture(
    target_url: str,
    steps: list[Step],
    out_dir: Path,
    on_step: Callable[[int, int, Step], None] | None = None,
) -> tuple[Path, dict[str, ActionRecord]]:
    """Run the steps against `target_url`, recording video + timestamps.

    `on_step(i, total, step)` is called as each scene starts (1-based) so callers
    can report live capture progress. Returns (video_path, {step_id: ActionRecord}).
    """
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, ActionRecord] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(out_dir),
            record_video_size=VIEWPORT,
        )
        page = await context.new_page()
        await page.goto(target_url, wait_until="networkidle")

        clock0 = time.monotonic()  # recording starts ~now

        total = len(steps)
        for idx, step in enumerate(steps, start=1):
            if on_step:
                on_step(idx, total, step)
            started = time.monotonic() - clock0
            click_xy = None
            target_rect = None
            status = "ok"
            error: str | None = None

            try:
                if step.action is ActionType.NAVIGATE and step.value:
                    # Resolve relative paths ("/dashboard") against the current
                    # page so authored steps don't need the full origin. Absolute
                    # URLs pass through urljoin unchanged.
                    dest = urljoin(page.url, step.value)
                    await page.goto(dest, wait_until="networkidle")
                elif step.action is ActionType.CLICK and step.target:
                    loc = page.locator(step.target).first
                    target_rect = await _rect(loc)
                    if target_rect:
                        click_xy = (
                            target_rect.x + target_rect.width / 2,
                            target_rect.y + target_rect.height / 2,
                        )
                    await loc.click(timeout=ACTION_TIMEOUT_MS)
                elif step.action is ActionType.TYPE and step.target:
                    loc = page.locator(step.target).first
                    target_rect = await _rect(loc)
                    await loc.fill(step.value or "", timeout=ACTION_TIMEOUT_MS)
                elif step.action is ActionType.KEYPRESS and step.value:
                    await page.keyboard.press(step.value)
                elif step.action is ActionType.WAIT:
                    await page.wait_for_timeout(float(step.value or 1000))
                else:
                    # No branch matched: the action's required field was empty,
                    # so nothing ran. Flag it rather than letting it pass silently.
                    status = "skipped"
                    missing = _REQUIRED_FIELD.get(step.action, "input")
                    error = f"missing {missing} — nothing to do"

                # Let the React app settle so the recorded frame is stable.
                await page.wait_for_load_state("networkidle")
                # Bring the scene's focus area into view BEFORE the settle frame
                # is recorded. The video only captures the viewport, so a
                # highlight/zoom target below the fold would otherwise be off the
                # recorded frame (and its rect would clamp to the top). Scrolling
                # here keeps the recorded pixels and the rects we read in agreement.
                focus_sel = step.zoom_target or step.highlight_target
                if focus_sel:
                    try:
                        await page.locator(focus_sel).first.scroll_into_view_if_needed(
                            timeout=ACTION_TIMEOUT_MS
                        )
                    except Exception:
                        pass  # not scrollable / not found — fall back to current view
                # ...then dwell so an SPA route actually paints before we stamp
                # `ended_at` — otherwise the held frame is the previous screen.
                await page.wait_for_timeout(SETTLE_MS)
            except Exception as exc:  # the action raised (e.g. selector matched nothing)
                status = "failed"
                error = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
                print(f"[capture] step {step.id} ({step.action.value}) failed: {error}")

            ended = time.monotonic() - clock0

            # Zoom is opt-in: only crop in when the step explicitly names a
            # zoom_target. Defaulting to the clicked element zoomed every "click a
            # tab" step into that tiny button, pixelating the label instead of
            # showing the page. The click marker + highlight already point the eye.
            zoom_rect = None
            if step.zoom_target:
                zoom_rect = await _rect(page.locator(step.zoom_target).first)
            highlight_rect = None
            if step.highlight_target:
                highlight_rect = await _rect(page.locator(step.highlight_target).first)

            records[step.id] = ActionRecord(
                step_id=step.id,
                started_at=started,
                ended_at=ended,
                click_xy=click_xy,
                target_rect=target_rect,
                zoom_rect=zoom_rect,
                highlight_rect=highlight_rect,
                status=status,
                error=error,
            )

        await context.close()  # finalizes the video file
        await browser.close()

    videos = sorted(out_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    if not videos:
        raise RuntimeError("Playwright produced no recording")
    return videos[-1], records
