# Writing scripts that succeed

A DemoFoundry script is a list of **scenes**. Each scene is one action (navigate, click, type,
keypress, wait) plus the words to narrate. The render pairs each scene's narration with the screen
that action produces. Most "the demo looks wrong" problems come from a mismatch between what a scene
*says* and what it *shows* — and they're easy to avoid once you know the rules.

## The one rule that prevents most problems

> **Narrate only what the scene actually puts on screen.**

The video you get for a scene is the screen **after its action runs**, held for the length of the
narration. So if a line talks about the Voice screen, that scene's action must *be on* the Voice
screen. If it isn't, you'll hear about one thing while watching another.

??? example "The mistake we hit in the self-demo"
    The last scene clicked **Cancel** (which returns to the Library) while the narration said
    "from here you'd pick a voice…". Result: the voice-over described the Voice screen, but the
    footage showed the Library — the *first* panel, not the voice panel.

    **Fix:** don't navigate away from what you're describing. Either (a) hold on the current screen
    and describe the next steps as *what comes next* ("from here you'd move on to…"), or (b) actually
    navigate to the screen you're narrating (see [Reaching a gated screen](#reaching-a-gated-screen)).

## Rules of thumb

| Do | Why |
|---|---|
| Make each scene's action land on the screen its narration describes. | The held frame is the *result* of the action. |
| To talk about screen B, `navigate`/`click` **to** screen B in that scene. | Otherwise you're narrating B while showing A. |
| Don't click **Back/Cancel/Close** in a scene that describes where you're going. | Those return you to a *previous* screen — you'll show the wrong one. |
| Use a `wait` scene to hold a screen while you narrate it (no navigation). | Good for a closing beat or a "let it sink in" moment. |
| Prefer stable selectors: `text=…`, `role`, or `data-testid`. | Brittle CSS/nth-child selectors break when the UI shifts. |
| Keep each narration line roughly as long as the action is worth showing. | Audio is the master clock; very long lines over a tiny action just hold a still. |

## Reaching a gated screen

Some screens only exist for a specific record. DemoFoundry's **Voice** screen is at
`/voice?id=<project>` — it needs a real project. To demo it you must create one first and navigate to
it explicitly. That's exactly what
[`demofoundry-feature-tour.playwright.steps.json`](../sample-scripts/README.md) does with a
`__PROJECT_ID__` placeholder:

```json
{ "action": "navigate", "value": "/voice?id=__PROJECT_ID__",
  "narration_text": "This is the Voice screen — pick any narrator…" }
```

If a scene narrates a screen you can't reach with a plain selector, that's the tell: you need a
`navigate` (often with an id) to get there.

## Highlights and zooms that read well

Each scene can draw a **highlight** box on `highlight_target`, a **click marker** where it clicked,
and **zoom** in on `zoom_target`. Used well they direct the eye; used carelessly they look like
glitches. Four things to get right:

1. **The recording is viewport-only.** Anything below the fold isn't filmed. DemoFoundry now
   **scrolls** the scene's `highlight_target`/`zoom_target` into view before recording — but only the
   one you name. Name the thing you want seen.

2. **Zoom a container, not a tiny element — or don't zoom at all.** `zoom_target` crops tightly to
   whatever you name, so a single button or one line of text fills the whole screen: pixelated and
   stripped of context. Point zoom at the surrounding **panel, card, or section** so the viewer still
   sees where they are. Better yet, for plain emphasis use `highlight_target` (it keeps the full
   screen) and reserve `zoom` for details too small to read otherwise.

3. **Only highlight something that's still on the screen the scene settles on.** The box is drawn at
   the element's captured position. If that element **moves, disappears, or you navigate away** in the
   same scene, the box ends up hovering over empty space or unrelated content — it reads as an error.
   Highlight the thing you just acted on (it's still there), not something transient, and don't put a
   highlight on a scene whose action navigates to a different screen.

4. **One target per scene.** A highlight and a zoom on the same scene fight each other. Pick the one
   that tells the story.

??? example "The two glitches users hit most"
    - *Zoom too tight:* `zoom_target: "text=Pacing"` crops to the word "Pacing" — huge and blurry.
      Fix: drop the zoom and `highlight_target` the **Pacing panel**, or zoom the panel, not the word.
    - *Stray box:* a scene navigates to a new screen but still carries a `highlight_target` from the
      old one — the yellow box floats over the new page. Fix: remove the highlight, or highlight an
      element that's actually on the screen the scene lands on.

## Debug a script in 30 seconds

Render it, then look at one frame per scene and check it matches the line:

```bash
cd backend/work-demo/render
# pull the last frame of each scene segment (that's the held frame the viewer sees)
for f in seg_*.mp4; do ffmpeg -v error -y -sseof -0.3 -i "$f" -frames:v 1 "${f%.mp4}.jpg"; done
# now eyeball seg_000.jpg … against scene 1's narration, seg_001.jpg against scene 2, etc.
```

Also open `demo.srt` — each cue's text is a scene's narration, in order. If cue 7 talks about the
Voice screen, `seg_006.jpg` had better show it.

## Prompting Claude to write or repair a script

Claude writes good scripts when you give it the same things a human needs:

- **The goal** in one sentence ("a 60-second tour of the invoicing flow").
- **The real screens and selectors** — paste the elements (the in-app Build screen inspects these for
  you), or the routes like `/voice?id=…`. Claude can't guess your `data-testid`s.
- **The rule, stated explicitly:** *"Each scene must narrate only what its action shows. To describe a
  screen, navigate to it in that scene. Never click Back/Cancel in a scene that describes where we're
  going."*

A good repair prompt:

> Here's my steps.json and a frame from each scene. Scene N narrates "<line>" but the frame shows
> "<what you saw>". Rewrite the script so every scene's narration matches the screen its action
> produces — add a `navigate` if a scene needs to reach a screen, and don't navigate away from a
> screen we're describing.

That single instruction fixes the most common class of failure — the one in the example above.

### A copy-ready prompt (every rule baked in)

This is the prompt that produces scripts like the ones in [sample scripts](../sample-scripts/README.md)
— including the fixes above (narration matches footage, no stray boxes, no over-tight zooms). Fill in
the **bracketed** parts and paste it to Claude:

```text
You are writing a DemoFoundry script — a steps.json that drives a web app with Playwright and
narrates each scene. Output ONLY a JSON object of this shape:

  { "name": "...", "target_url": "[APP URL]",
    "steps": [ { "action": ..., "target": ..., "value": ..., "zoom_target": ...,
                 "highlight_target": ..., "narration_text": "..." } ] }

Actions: navigate | click | type | keypress | wait.
  - navigate: value = path or URL (relative paths resolve against target_url).
  - click / type: target = a Playwright selector; type also needs value (the text).
  - wait: value = milliseconds.

App: [APP NAME] at [APP URL].
Goal: [ONE-SENTENCE GOAL, e.g. "a 60-second tour of the invoicing flow"].
Screens & selectors you may use (use these verbatim; do not invent selectors):
  [PASTE REAL SELECTORS / ROUTES — e.g. text=New demo, button:has-text("Web app"),
   #name, #target, text=Reset to sample, /voice?id=__PROJECT_ID__, ...]

Follow these rules exactly:
1. Each scene's narration must describe ONLY what that scene's action puts on screen. The frame the
   viewer holds is the RESULT of the action.
2. To talk about a screen, navigate or click TO it in that same scene. Screens that need a record
   (e.g. the Voice screen) require their id: /voice?id=__PROJECT_ID__.
3. Never click Back, Cancel, or Close in a scene that describes where you're going — that returns to a
   previous screen and the footage won't match the words. To end, hold on the current screen with a
   `wait` and describe the next steps as what comes next.
4. For emphasis prefer highlight_target — it keeps the whole screen visible. Use zoom_target ONLY for
   detail too small to read, and always point it at a CONTAINING panel / card / section, never a bare
   button or single line of text (tight zooms pixelate and lose context). At most one of
   highlight_target / zoom_target per scene.
5. Only set highlight_target / zoom_target to an element that is still on the screen the scene settles
   on. Never highlight something that moves, disappears, or that you navigate away from — the box will
   hover over empty space and look like an error. Usually: highlight the element you just acted on.
6. Prefer stable selectors: text=…, role=…, or data-testid. One element each.
7. Keep each narration line about as long as the action is worth showing; linger where there's
   something to see, and write in a warm, plain, spoken voice.

Write [N] scenes that accomplish the goal.
```

!!! tip "Why this prompt works"
    Rules 1–3 keep narration and footage in sync (no "talking about the Voice screen while showing the
    Library"). Rules 4–5 stop the two visual glitches — pixelated over-zooms and highlight boxes
    stranded over content that's gone. The DemoFoundry feature-tour and self-demo samples were written
    with exactly this prompt.

See also the [sample scripts](../sample-scripts/README.md) (working, copy-ready examples) and the
[CLI guide](cli.md) for the step-file reference.
