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

## Two capture facts that trip people up

1. **The recording is viewport-only.** Anything below the fold isn't filmed. If you `highlight`
   or `zoom` something far down the page (e.g. a control under a long list), DemoFoundry now
   **scrolls it into view** before recording — but only if you name it as the scene's
   `highlight_target`/`zoom_target`. Name the thing you want seen.
2. **Don't `zoom_target` a tiny element.** Zoom crops to that element, so a small heading blows up
   and pixelates. Zoom a **container** (a panel, a card), or skip zoom and just use `highlight_target`
   — the highlight box and click marker already direct the eye.

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

See also the [sample scripts](../sample-scripts/README.md) (working, copy-ready examples) and the
[CLI guide](cli.md) for the step-file reference.
