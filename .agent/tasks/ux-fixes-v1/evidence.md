# Evidence — ux-fixes-v1

Date: 2026-06-11

All changes are frontend-only: `lsa/web/static/app.js`, `index.html`, `style.css`.
No backend or dependency changes.

## AC1 — error-aware progress/callouts: PASS
- Snapshot create: `hasErrors = rsync_errors.length > 0 || !scan_ok` toggles
  `progress-fill--warn` on the fill and `callout--warn` on the result.
- Workspace create: `copy_errors.length > 0` does the same and the count is
  appended to the message ("N copy error(s) — see pull script for retry").
- New CSS: `.progress-fill--warn` (amber gradient from `--warn` token).

## AC2 — filters re-run search: PASS
- `rerunSearch()` closure added in `renderSearchPage`; called from all four
  filter change handlers (mode, scope, kind, space) when the query is non-empty.

## AC3 — form state survives navigation: PASS
- `state.bundleForm` {title, cid, jobid, limit}: rendered into input `value`
  attrs and mirrored on `input` events in `renderBundleStep`.
- Change Docs: 7 fields (prid, jira, hours, liveDate, qaJob, qaItems,
  extraContext) mirrored into `state.changeDocs` on `input`; template already
  rendered from `cd.*` so values now persist.
- Prompt: `state.promptInput` rendered into the textarea and mirrored on
  `input` — survives scenario/lang toggles (which re-render) and navigation.

## AC4 — PRID client-side validation: PASS
- `_validatePrid` checks `/^\d{14,}$/`, shows inline `.field-error` under the
  PRID field (distinct messages for empty vs malformed), returns early — no
  API call. Error clears on PRID input. Used by both Preview and Generate.

## AC5 — Copy raw in file preview modal: PASS
- `showModal(title, content, copyText)`: third param shows the `#modal-copy`
  button (added to `index.html` modal header) wired to `copyToClipboard`.
- `previewFile` passes the raw, un-numbered content. All other `showModal`
  callers omit the param — button hidden. `showDeleteConfirm` (which bypasses
  `showModal`) explicitly hides the button to avoid a stale one.

## AC6 — workspace result XSS hardening: PASS
- `files_copied` and `copy_errors` count interpolated via `Number(...)`;
  rsync error count in snapshot message likewise.

## AC7 — single freshness column: PASS
- "Captured" header and cell removed; freshness cell carries
  `title="Captured: <date>"`. Grid template reduced 7 -> 6 columns
  (`1.3fr 0.7fr 0.7fr 1.2fr 0.5fr 0.9fr`); responsive variant already
  collapses to `1fr` — untouched.

## AC8 — snapshot select busy state: PASS
- "Use" button: disabled + label "Using…", row gets `.is-busy`
  (opacity + pointer-events none); restored in `finally`.

## Verification
- `node --check app.js`: OK (`raw/node_check.txt`).
- Full pytest: **200 passed** (`raw/pytest_full.txt`) — includes the
  `test_app_js_parses_when_node_is_available` syntax test.

## Fix round 1 (after first verification FAIL on AC3)
- Problem: `escapeHtml` (innerHTML-based) did not escape quotes, so values
  containing `"` broke `value="..."` attribute interpolation (truncation +
  attribute injection).
- Fix: `escapeHtml` now appends `.replace(/"/g, '&quot;').replace(/'/g, '&#39;')`.
  Safe for all call sites (all render into innerHTML; entities decode back to
  literal characters; no double-escaping found by grep).
- Reverified: overall PASS in verdict.json; node --check OK; 200 tests pass.

## Not verified
- Live browser interaction (no JS test infra in repo; behavior verified by
  code inspection per spec).
