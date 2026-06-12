# Task: ux-fixes-v1 — Web UI UX fixes from project review

Frozen: 2026-06-11

## Scope

Frontend-only changes: `lsa/web/static/app.js`, `lsa/web/static/index.html`,
`lsa/web/static/style.css`. No backend changes. Keep the existing professional,
minimal aesthetic (no new visual noise).

## Acceptance criteria

### AC1 — Progress bars and result callouts reflect errors
- Snapshot creation: when the final SSE event has `rsync_errors.length > 0` or
  `scan_ok === false`, the progress fill switches to a warn color and the
  result callout uses `callout--warn` (not `callout--info`).
- Workspace creation: same treatment when `copy_errors.length > 0`, and the
  error count is shown in the callout.

### AC2 — Search filter changes re-run the query
- Changing Mode, Scope, Kind, or Results (space) immediately re-runs
  `performSearch` with the current input value when it is non-empty. Displayed
  results never contradict the selected filters.

### AC3 — Form inputs survive navigation and re-renders
- Bundle "Find scope" inputs (Title, CID, Job ID, limit) are mirrored into
  `state.bundleForm` on input and restored when the step re-renders.
- Change Docs inputs (PRID, JIRA, hours, live date, QA job, QA items, extra
  context) are mirrored into `state.changeDocs` on input, so navigating away
  and back does not lose typed values.
- Prompt page: the error/description textarea content is mirrored into state
  and survives scenario/language toggles (which re-render the page) and
  navigation.

### AC4 — Client-side PRID validation
- Preview and Generate in Change Docs validate `/^\d{14,}$/` on PRID before
  any API call; on failure an inline field error is shown and no request is
  made. The inline error clears when the user edits the field.

### AC5 — "Copy raw" in the file preview modal
- The file preview modal offers a copy action that copies the raw file
  content WITHOUT the line-number prefixes. Knowledge previews and other
  modals without raw content do not show the button.

### AC6 — Workspace result XSS hardening
- `files_copied` (and any other interpolated numeric fields in that message)
  are coerced to Number before being placed into innerHTML.

### AC7 — Snapshot table: single freshness column
- The separate "Captured" column is removed; the "Freshness" cell shows the
  relative time with the absolute timestamp in a `title` tooltip. Grid
  template columns updated accordingly (including the responsive variant).

### AC8 — Snapshot select shows progress
- Clicking "Use" on a snapshot row disables the button, swaps its label to a
  busy state, and marks the row visually until the request settles; restored
  on failure.

## Verification
- `node --check app.js` passes (covered by existing pytest test).
- Full pytest suite passes (no backend regressions).
- Code-level verification of each AC by a fresh reviewer (no JS unit-test
  infrastructure exists in this repo; behavioral checks are by inspection).

## Constraints
- No backend (`server.py`) changes.
- No new dependencies, no build step — plain JS/CSS edits only.
- Minimal CSS additions; reuse existing tokens (`--warn`, `callout--warn`,
  `btn--sm`, etc.).
