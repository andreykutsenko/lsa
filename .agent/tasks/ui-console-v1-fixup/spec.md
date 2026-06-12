# Task Spec: ui-console-v1-fixup

## Metadata
- Task ID: ui-console-v1-fixup
- Created: 2026-03-25T17:22:26+00:00
- Repo root: /home/kts/lsa
- Working directory at init: /home/kts/lsa

## Guidance sources
- AGENTS.md
- CLAUDE.md
- User task in chat on 2026-03-25
- Existing UI implementation in `lsa/web/static/app.js`
- Existing UI shell and styling in `lsa/web/static/index.html` and `lsa/web/static/style.css`
- Existing API endpoints in `lsa/web/server.py`

## Original task statement
Реализовать V1 operator-console refactor для LSA UI: перестроить Overview вокруг Current scope, демотировать внутренние counters в Diagnostics, упростить правые explanatory panels, улучшить Search, Snapshots, Prompt/Generate prompt, учесть incident/change request handoff, snapshot optional enrichments и последние замечания по Search knowledge/file modes.

## Acceptance criteria
- AC1: `Overview` in the web UI is refocused around `Current scope` as the primary operator surface instead of snapshot index statistics. The central content must expose the active snapshot, selected candidate or proc, a short scope-composition summary, and the main actions `Open files`, `Create workspace`, `Copy file list`, `Generate prompt`, and `Open diagram`.
- AC2: Internal counters and index-oriented metrics such as artifacts, graph nodes, graph edges, case-card counts, and message-code counts are demoted out of the central work surface into a secondary `Diagnostics` area. Any explanatory side cards on the overview or bundle pages must read as supporting context rather than primary interactive panels.
- AC3: Search is operator-oriented and clearly separates file/artifact search from knowledge search. The UI and API together support:
  - `Path` vs `Content`
  - `Current scope` vs `Whole snapshot`
  - kind filtering for file artifacts
  - an explicit result-space distinction such as `Files`, `Knowledge`, and `All`, so message codes and case cards are not mixed indistinguishably with file-path search.
- AC4: Prompt generation works from the already selected `Current scope` and exposes exactly two explicit V1 scenarios: `Incident analysis` and `Change request analysis`. The operator does not need to pick a separate candidate inside the prompt screen, and generated prompt output reflects the chosen scenario and scope.
- AC5: Snapshot creation supports optional enrichments through progressive disclosure rather than showing every optional source up front. V1 must support optional inputs for Papyrus PDF, incidents folder, research or log files folder, related files folder, prox folder, and any missing first-class operator input needed to include control or insert material as optional enrichments without broad backend redesign.
- AC6: The implementation stays pragmatic and localized. The change set primarily targets `lsa/web/static/app.js`, `lsa/web/static/style.css`, `lsa/web/static/index.html`, and `lsa/web/server.py`, avoids broad backend refactors unless required for the acceptance criteria, and does not include dark mode unless it is nearly free.

## Constraints
- Prefer operator utility over decorative redesign.
- Reuse the existing repo-local task folder `.agent/tasks/ui-console-v1-fixup/`.
- Freeze the spec before implementation.
- Before any production-code edit, provide the user a short implementation summary in Russian and wait for explicit approval.
- Keep all workflow artifacts inside `.agent/tasks/ui-console-v1-fixup/`.
- Keep implementer, verifier, and fixer roles separate during the proof loop.
- Prefer the smallest safe diff set that satisfies the acceptance criteria.
- Do not claim completion unless every acceptance criterion is verified as `PASS`.
- Treat restart/reload regressions that break initial UI bootstrap as blocking bugs for V1.

## Non-goals
- Broad backend or data-model redesign outside what is required to expose the V1 operator-console behavior.
- New prompt scenarios beyond `Incident analysis` and `Change request analysis`.
- Rich knowledge workflows such as dedicated case-card editors, message-code management UIs, or a separate knowledge workbench.
- Full redesign of navigation architecture or replacement of the current static SPA stack.
- Dark mode, unless it falls out of the styling changes with near-zero additional cost.
- V2-level operator features such as saved search presets, bulk multi-scope comparison, advanced workspace templates, or a richer knowledge-results drilldown beyond clear V1 separation.

## Assumptions
- The current frontend already contains partial V1-aligned work; this task is a fixup/refinement pass rather than a greenfield rewrite.
- `Current scope` continues to be derived from the plan candidate selected in the bundle/scope-builder flow.
- Search result-space separation may be implemented with a minimal UI/API extension instead of a new subsystem, as long as file and knowledge results are clearly distinguishable and operator-usable.
- Snapshot optional enrichments may reuse existing backend fields where they already cover the required sources; only small API/request-shape changes should be made if an explicit V1 input is still missing.
- If the existing backend already includes base snapshot copying for core source sets, V1 only needs to expose optional enrichments more clearly in the operator flow rather than redefining the whole acquisition pipeline.

## Verification plan
- Build: run the project frontend/backend build or packaging check used by the repo, if present.
- Unit tests: run targeted unit tests for web/server behavior if present.
- Integration tests: run relevant UI/server integration tests if present.
- Lint: run the repo lint command or targeted lint for touched files if configured.
- Manual checks:
  - confirm `Overview` centers `Current scope` and main actions
  - confirm diagnostics are secondary
  - confirm search exposes result-space separation plus mode/scope/kind controls
  - confirm `Bundle` uses the current-scope action row as the single clear entry point for files, workspace, prompt, and diagram, without duplicate primary surfaces
  - confirm a real Papyrus/PDF message code can be found in live search for `Knowledge` and `All`, including after selecting `Current scope`
  - confirm prompt page uses the selected scope and supports the two V1 scenarios
  - confirm snapshot creation hides optional enrichments behind progressive disclosure
  - restart the LSA server, reload the web UI, and confirm the initial snapshot screen still loads usable content
  - confirm no unnecessary broad backend refactor or dark-mode scope creep
