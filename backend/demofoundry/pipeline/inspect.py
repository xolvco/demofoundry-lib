"""Inspect — snapshot a target app's interactive elements for the script builder.

Loads the app once with Playwright and extracts the clickable / typeable
elements with a best-guess stable selector each (prefers data-testid, then id,
then a role/text hint). This is the app knowledge Claude needs to turn a goal or
an audio script into a concrete steps.json — without it, selectors are guesswork.

Cheap and read-only: no recording, just a DOM read. Requires the same Chromium
that capture uses (`playwright install chromium`).
"""

from __future__ import annotations

# Run in the page: collect interactive elements with a stable-ish selector each.
_COLLECT_JS = r"""
() => {
  const pick = (el) => {
    const tid = el.getAttribute('data-testid');
    if (tid) return `[data-testid='${tid}']`;
    if (el.id) return `#${el.id}`;
    const name = el.getAttribute('name');
    if (name) return `${el.tagName.toLowerCase()}[name='${name}']`;
    const href = el.getAttribute('href');
    if (el.tagName === 'A' && href) return `a[href='${href}']`;
    const aria = el.getAttribute('aria-label');
    if (aria) return `${el.tagName.toLowerCase()}[aria-label='${aria}']`;
    return null;
  };
  const sel = 'a,button,input,textarea,select,[role=button],[role=link],[role=tab],[contenteditable=true]';
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(sel)) {
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue; // skip hidden
    const selector = pick(el);
    if (!selector || seen.has(selector)) continue;
    seen.add(selector);
    const text = (el.innerText || el.value || el.getAttribute('placeholder') || '').trim().slice(0, 60);
    out.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || el.type || el.tagName.toLowerCase(),
      selector,
      text,
    });
    if (out.length >= 60) break;
  }
  return out;
}
"""


async def snapshot(url: str) -> list[dict]:
    """Return up to ~60 interactive elements of `url` as {tag, role, selector, text}.

    Best-effort: returns [] if the page can't be loaded, so the builder still
    works (Claude just has less to go on).
    """
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(url, wait_until="networkidle", timeout=15000)
            elements = await page.evaluate(_COLLECT_JS)
            await browser.close()
            return elements or []
    except Exception as exc:  # never block script-building on a flaky load
        print(f"[inspect] could not read {url}: {exc}")
        return []


def as_prompt_lines(elements: list[dict]) -> str:
    """Render elements as compact prompt context, one per line."""
    if not elements:
        return "(the app could not be inspected — infer selectors from the reference material)"
    lines = []
    for e in elements:
        text = f'  "{e["text"]}"' if e.get("text") else ""
        lines.append(f"- {e['role']:8} {e['selector']}{text}")
    return "\n".join(lines)
