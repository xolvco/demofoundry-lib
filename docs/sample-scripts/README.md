# Sample scripts

Copy-ready `steps.json` scripts you can run through DemoFoundry. Each is either a **web** script
(DemoFoundry drives it with Playwright — needs real selectors) or a **screen-capture** script
(narration only — you record yourself; selectors are ignored). See the
[CLI guide](../guide/cli.md) and [Screen capture guide](../guide/screen-capture.md).

| File | Mode | What it demos |
|---|---|---|
| [`demofoundry-self-demo.playwright.steps.json`](demofoundry-self-demo.playwright.steps.json) | Web (Playwright) | DemoFoundry's own UI, fully click-driven — every step has a real selector. |
| [`demofoundry-web-tour.steps.json`](demofoundry-web-tour.steps.json) | Web (Playwright) | A lighter narrated tour of the DemoFoundry New-demo flow. |
| [`webmethods-getting-started.steps.json`](webmethods-getting-started.steps.json) | Screen capture (Desktop) | Getting started with IBM webMethods.io Integration. |

## Running a web script

The two DemoFoundry scripts drive the app at `http://localhost:3000`, so start the app first
(`npm run dev` for the frontend, the backend on `:8001`). Then:

```bash
cd backend
demofoundry render --url http://localhost:3000 \
  --steps ../docs/sample-scripts/demofoundry-self-demo.playwright.steps.json \
  --out-dir work
```

The selectors are taken from the live UI (`text=New demo`, `button:has-text("Web app")`, `#name`,
`#target`, `text=Reset to sample`, `text=What we read`, `text=Cancel`). If the UI changes, update the
`target` fields to match.

## Running a screen-capture script

`webmethods-getting-started.steps.json` targets IBM webMethods.io — an external SaaS you can't (and
shouldn't) drive with selectors. Use the **Desktop** capture path: create the demo as a Desktop app,
record yourself walking through webMethods.io in the browser, mark the eleven scenes, pick a voice,
and render. The script supplies the narration for each beat. See
[Screen capture](../guide/screen-capture.md).

## IBM webMethods — where to get started (official docs)

For the webMethods script above, these are the official starting points:

- **IBM webMethods documentation home** — <https://docs.webmethods.io>
- **Getting started (IBM Docs)** — <https://www.ibm.com/docs/en/wam/wdp/11.1.0?topic=getting-started>
- **webMethods Integration overview** — <https://www.ibm.com/docs/en/wm-integration-ipaas?topic=overview>
- **Getting Started with webMethods.io: A Beginner's Guide (IBM Community)** —
  <https://community.ibm.com/community/user/integration/viewdocument/getting-started-with-webmethodsio>
- **Working with IBM webMethods Integration Server** —
  <https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/11.1.0?topic=guide-working-webmethods-integration-server>
