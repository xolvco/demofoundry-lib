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

from ..models import ActionRecord, ActionType, Rect, Step

VIEWPORT = {"width": 1920, "height": 1080}


async def _rect(locator) -> Rect | None:
    try:
        box = await locator.bounding_box()
    except Exception:
        box = None
    if not box:
        return None
    return Rect(box["x"], box["y"], box["width"], box["height"])


async def capture(
    target_url: str,
    steps: list[Step],
    out_dir: Path,
) -> tuple[Path, dict[str, ActionRecord]]:
    """Run the steps against `target_url`, recording video + timestamps.

    Returns (video_path, {step_id: ActionRecord}).
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

        for step in steps:
            started = time.monotonic() - clock0
            click_xy = None
            target_rect = None

            try:
                if step.action is ActionType.NAVIGATE and step.value:
                    await page.goto(step.value, wait_until="networkidle")
                elif step.action is ActionType.CLICK and step.target:
                    loc = page.locator(step.target).first
                    target_rect = await _rect(loc)
                    if target_rect:
                        click_xy = (
                            target_rect.x + target_rect.width / 2,
                            target_rect.y + target_rect.height / 2,
                        )
                    await loc.click()
                elif step.action is ActionType.TYPE and step.target:
                    loc = page.locator(step.target).first
                    target_rect = await _rect(loc)
                    await loc.fill(step.value or "")
                elif step.action is ActionType.KEYPRESS and step.value:
                    await page.keyboard.press(step.value)
                elif step.action is ActionType.WAIT:
                    await page.wait_for_timeout(float(step.value or 1000))

                # Let the React app settle so the recorded frame is stable.
                await page.wait_for_load_state("networkidle")
            except Exception as exc:  # surface which step failed; keep going
                print(f"[capture] step {step.id} ({step.action}) failed: {exc}")

            ended = time.monotonic() - clock0

            zoom_rect = target_rect
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
            )

        await context.close()  # finalizes the video file
        await browser.close()

    videos = sorted(out_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    if not videos:
        raise RuntimeError("Playwright produced no recording")
    return videos[-1], records
