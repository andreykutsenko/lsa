# Evidence Bundle: ui-console-v1-fixup

## Summary
- Overall status: PASS
- Last updated: 2026-03-25
- Note: a restart/reload bootstrap regression was reproduced and fixed on 2026-03-25 before this evidence bundle was refreshed.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Current scope block exposes active snapshot, selected proc/candidate, scope composition, and the required action row in [app.js](/home/kts/lsa/lsa/web/static/app.js#L242) and [app.js](/home/kts/lsa/lsa/web/static/app.js#L231).
  - Overview renders `Current scope` as the first and primary section in [app.js](/home/kts/lsa/lsa/web/static/app.js#L969) and [app.js](/home/kts/lsa/lsa/web/static/app.js#L983).
  - The Bundle action row now routes `Open files` and `Create workspace` to the single in-page targets via [app.js](/home/kts/lsa/lsa/web/static/app.js#L283) and [app.js](/home/kts/lsa/lsa/web/static/app.js#L940) instead of leaving `Open files` as a no-op on the bundle screen.
  - Live smoke outputs confirm scope selection, file opening, prompt generation, diagram payload generation, and workspace creation against the selected scope in `.agent/tasks/ui-console-v1-fixup/raw/test-integration.txt`.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Internal counters `Artifacts`, `Nodes`, `Edges`, `Case cards`, and `Message codes` are rendered only inside `Diagnostics` in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1039).
  - The bundle-page explanatory card was removed as a competing primary-looking panel; the operator guidance is now a short help line under the single scope finder surface in [app.js](/home/kts/lsa/lsa/web/static/app.js#L731).
  - The duplicate inline diagram section was removed from the bundle page, leaving `Open diagram` in the current-scope action row as the single entry point; see [app.js](/home/kts/lsa/lsa/web/static/app.js#L907).
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - Search now exposes explicit result-space controls `All`, `Files`, and `Knowledge` in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1135).
  - The search help text in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1144) no longer contains raw backticks inside a template literal, so the browser script parses after restart/reload; this is also guarded by [test_web_server.py](/home/kts/lsa/tests/test_web_server.py#L197).
  - Search still supports `Path` vs `Content`, `Current scope` vs `Whole snapshot`, and kind filters in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1098), [app.js](/home/kts/lsa/lsa/web/static/app.js#L1105), and [app.js](/home/kts/lsa/lsa/web/static/app.js#L1128).
  - The UI renders knowledge hits and file hits in separate result groups in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1211).
  - Backend search now keeps knowledge hits available even when the operator selects `Current scope` with `All` or `Knowledge`, matching the UI contract that PDF/message-code knowledge is snapshot-wide; see [server.py](/home/kts/lsa/lsa/web/server.py#L1160).
  - Backend behavior is covered by [test_web_server.py](/home/kts/lsa/tests/test_web_server.py#L166) and [test_web_server.py](/home/kts/lsa/tests/test_web_server.py#L180), and passes in `.agent/tasks/ui-console-v1-fixup/raw/test-unit.txt`.
  - Live smoke outputs show `PPCS0178E` found successfully for `Knowledge` and `All` while `scope=current`, plus `Files` + `Path` for a scoped proc path, in `.agent/tasks/ui-console-v1-fixup/raw/test-integration.txt`.
- Gaps:
  - None.

### AC4
- Status: PASS
- Proof:
  - Prompt page is built from the selected current scope block and does not introduce a second candidate picker in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1242) and [app.js](/home/kts/lsa/lsa/web/static/app.js#L1286).
  - Prompt UI exposes exactly two scenarios, `Incident analysis` and `Change request analysis`, in [app.js](/home/kts/lsa/lsa/web/static/app.js#L1253).
  - Backend accepts scenario-driven prompt generation from the selected candidate and returns scope-aware prompt metadata in [server.py](/home/kts/lsa/lsa/web/server.py#L83) and [server.py](/home/kts/lsa/lsa/web/server.py#L710).
  - Targeted unit tests for operator scope summary and scenario prompt generation pass in [test_web_server.py](/home/kts/lsa/tests/test_web_server.py#L79) and `.agent/tasks/ui-console-v1-fixup/raw/test-unit.txt`.
- Gaps:
  - None.

### AC5
- Status: PASS
- Proof:
  - Snapshot creation uses progressive disclosure through the hidden advanced panel in [app.js](/home/kts/lsa/lsa/web/static/app.js#L418).
  - Optional inputs now include Papyrus PDF, incidents, research/logs, related files, prox, control, and insert in [app.js](/home/kts/lsa/lsa/web/static/app.js#L437).
  - `NewSnapshotRequest` carries `control_path` and `insert_path` in [server.py](/home/kts/lsa/lsa/web/server.py#L94).
  - Backend copies optional `control` and `insert` enrichments into the snapshot in [server.py](/home/kts/lsa/lsa/web/server.py#L432).
  - Request-model coverage for the new optional fields is in [test_web_server.py](/home/kts/lsa/tests/test_web_server.py#L185) and passes in `.agent/tasks/ui-console-v1-fixup/raw/test-unit.txt`.
- Gaps:
  - None.

### AC6
- Status: PASS
- Proof:
  - The change set remains concentrated in [app.js](/home/kts/lsa/lsa/web/static/app.js), [style.css](/home/kts/lsa/lsa/web/static/style.css), [index.html](/home/kts/lsa/lsa/web/static/index.html), [server.py](/home/kts/lsa/lsa/web/server.py), and [test_web_server.py](/home/kts/lsa/tests/test_web_server.py).
  - No dark-mode implementation is present in [style.css](/home/kts/lsa/lsa/web/static/style.css).
  - `python3 -m py_compile lsa/web/server.py tests/test_web_server.py`, `python3 -m pytest tests/test_web_server.py`, and `node --check lsa/web/static/app.js` all exited `0`; outputs are recorded in `.agent/tasks/ui-console-v1-fixup/raw/build.txt`, `.agent/tasks/ui-console-v1-fixup/raw/test-unit.txt`, and `.agent/tasks/ui-console-v1-fixup/raw/lint.txt`.
  - A live restart/reload and action-flow smoke test against a freshly restarted LSA server confirmed that `/`, `/static/app.js`, `/api/snapshots`, `/api/plan`, `/api/file`, `/api/prompt`, `/api/plan/mermaid`, `/api/workspace/create`, and `/api/search` all behave as expected; captured output is in `.agent/tasks/ui-console-v1-fixup/raw/test-integration.txt`.
- Gaps:
  - None.

## Commands run
- `python3 -m py_compile lsa/web/server.py tests/test_web_server.py`
- `python3 -m pytest tests/test_web_server.py`
- `node --check lsa/web/static/app.js`
- Restarted `python3 -m lsa.cli serve --no-open --port 18903` outside the sandbox
- Loaded `/` in headless Chrome
- Fetched `/api/snapshot/select`, `/api/plan`, `/api/file`, `/api/prompt`, `/api/plan/mermaid`, `/api/workspace/create`, `/api/search`, `/api/snapshots`, and `/static/app.js`

## Raw artifacts
- `.agent/tasks/ui-console-v1-fixup/raw/build.txt`
- `.agent/tasks/ui-console-v1-fixup/raw/test-unit.txt`
- `.agent/tasks/ui-console-v1-fixup/raw/test-integration.txt`
- `.agent/tasks/ui-console-v1-fixup/raw/lint.txt`
- `.agent/tasks/ui-console-v1-fixup/raw/screenshot-1.png`

## Known gaps
- No failing acceptance criteria remain in the current local verification pass.
- Earlier verifier `PASS` was insufficient because it relied on backend tests and static evidence without a live restart/reload smoke test of the browser bootstrap path.
