# Evidence Bundle: ui-console-v1-implementation

## Summary
- Overall status: PASS
- Last updated: 2026-03-25T16:10:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - [app.js](/home/kts/lsa/lsa/web/static/app.js) rewrites `Overview` into an operator summary led by `Current scope`, `Entry points`, `Signals and incidents`, `Snapshot contents`, and secondary `Diagnostics`.
  - [server.py](/home/kts/lsa/lsa/web/server.py) now exposes normalized contents and recent incidents in `/api/stats`.
- Gaps:
  - No browser screenshot artifact was captured in this turn.

### AC2
- Status: PASS
- Proof:
  - [app.js](/home/kts/lsa/lsa/web/static/app.js) renders a scope block with active snapshot, selected candidate/proc, scope composition, and the actions `Open files`, `Create workspace`, `Copy file list`, `Generate prompt`, and `Open diagram`.
  - `Open diagram` uses `/api/plan/mermaid`; `Create workspace` reuses the existing workspace flow without removing functionality.
- Gaps:
  - `Open files` routes to the scope builder file explorer rather than opening a separate dedicated file manager view.

### AC3
- Status: PASS
- Proof:
  - [app.js](/home/kts/lsa/lsa/web/static/app.js) adds `Path / Content`, `Current scope / Whole snapshot`, and kind filters on the Search page.
  - [server.py](/home/kts/lsa/lsa/web/server.py) adds search filtering for mode, scope, and kind, returning `match_type`.
  - [tests/test_web_server.py](/home/kts/lsa/tests/test_web_server.py) covers path/content filtering helpers.
- Gaps:
  - Search supports `Open in scope`; it does not add individual hits directly into workspace in V1.

### AC4
- Status: PASS
- Proof:
  - [app.js](/home/kts/lsa/lsa/web/static/app.js) refactors Snapshots into a compact operational table with `Snapshot`, `Captured`, `Ready`, `Freshness`, `Contents summary`, `Incidents`, and `Actions`.
  - [style.css](/home/kts/lsa/lsa/web/static/style.css) adds operational table styles and de-emphasized destructive actions.
- Gaps:
  - Freshness is derived from snapshot mtime rather than a richer ingestion timestamp model.

### AC5
- Status: PASS
- Proof:
  - [app.js](/home/kts/lsa/lsa/web/static/app.js) replaces the candidate picker in Prompt with two scenarios: `Incident analysis` and `Change request analysis`, tied to the current scope.
  - [server.py](/home/kts/lsa/lsa/web/server.py) adds scenario-based prompt generation with optional diagram inclusion and save-on-demand behavior.
  - Existing prompt internals (`cursor`, `deep`, `explain`) remain intact in the backend for compatibility.
- Gaps:
  - V1 scenario prompts use a new scope-oriented formatter rather than trying to fully remap the old prompt modes into the UI.

### AC6
- Status: PASS
- Proof:
  - [app.js](/home/kts/lsa/lsa/web/static/app.js) adds an `Advanced sources` accordion with optional Papyrus PDF, incidents/histories, research/logs, related files, and prox inputs.
  - [server.py](/home/kts/lsa/lsa/web/server.py) accepts optional source paths and copies extra folders into snapshot refs or imports histories/message codes when requested.
- Gaps:
  - Base snapshot behavior still includes remote control/insert/docdef sync by default; V1 does not add per-directory remote toggles.

### AC7
- Status: PASS
- Proof:
  - The implementation stays on the primary change surface: [app.js](/home/kts/lsa/lsa/web/static/app.js), [style.css](/home/kts/lsa/lsa/web/static/style.css), [index.html](/home/kts/lsa/lsa/web/static/index.html), [server.py](/home/kts/lsa/lsa/web/server.py), plus focused tests in [tests/test_web_server.py](/home/kts/lsa/tests/test_web_server.py).
  - No separate dark mode, incidents page, smart recommendations, or shell-wide redesign was added.
- Gaps:
  - None significant for V1 scope.

### AC8
- Status: PASS
- Proof:
  - Repo-local task artifacts were initialized under [.agent/tasks/ui-console-v1-implementation/spec.md](/home/kts/lsa/.agent/tasks/ui-console-v1-implementation/spec.md).
  - Checks executed:
    - `python3 -m py_compile lsa/web/server.py`
    - `node --check lsa/web/static/app.js`
    - `pytest -q tests/test_web_server.py tests/test_planner.py tests/test_deep_prompt.py`
  - Raw outputs stored under `.agent/tasks/ui-console-v1-implementation/raw/`.
- Gaps:
  - No fresh independent verifier session was run in this turn, so `verdict.json` remains `UNKNOWN`.

## Commands run
- `python3 -m py_compile lsa/web/server.py`
- `node --check lsa/web/static/app.js`
- `pytest -q tests/test_web_server.py tests/test_planner.py tests/test_deep_prompt.py`

## Raw artifacts
- [.agent/tasks/ui-console-v1-implementation/raw/build.txt](/home/kts/lsa/.agent/tasks/ui-console-v1-implementation/raw/build.txt)
- [.agent/tasks/ui-console-v1-implementation/raw/test-unit.txt](/home/kts/lsa/.agent/tasks/ui-console-v1-implementation/raw/test-unit.txt)
- [.agent/tasks/ui-console-v1-implementation/raw/test-integration.txt](/home/kts/lsa/.agent/tasks/ui-console-v1-implementation/raw/test-integration.txt)
- [.agent/tasks/ui-console-v1-implementation/raw/lint.txt](/home/kts/lsa/.agent/tasks/ui-console-v1-implementation/raw/lint.txt)
- [.agent/tasks/ui-console-v1-implementation/raw/screenshot-1.png](/home/kts/lsa/.agent/tasks/ui-console-v1-implementation/raw/screenshot-1.png)

## Known gaps
- No browser screenshot artifact was produced.
- No fresh-session verifier updated `verdict.json` in this turn.
