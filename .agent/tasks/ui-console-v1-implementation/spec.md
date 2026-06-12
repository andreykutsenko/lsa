# Task Spec: ui-console-v1-implementation

## Metadata
- Task ID: ui-console-v1-implementation
- Created: 2026-03-25T15:47:56+00:00
- Repo root: /home/kts/lsa
- Working directory at init: /home/kts/lsa

## Guidance sources
- User task statement and approved V1 implementation plan from the active chat.
- /home/kts/lsa/AGENTS.md
- /home/kts/lsa/CLAUDE.md
- /home/kts/lsa/lsa/web/static/index.html
- /home/kts/lsa/lsa/web/static/style.css
- /home/kts/lsa/lsa/web/static/app.js
- /home/kts/lsa/lsa/web/server.py
- /home/kts/lsa/.agent/tasks/ui-console-review-ru/spec.md

## Original task statement
Реализовать V1 operator-oriented refactor текущей operator console: перестроить UI вокруг Current scope, переделать Overview/Search/Snapshots/Prompt, улучшить snapshot creation flow, сохранить существующую функциональность, минимизировать backend-рефактор, сначала выдать implementation plan на русском и ждать одобрения пользователя перед кодом.

## Acceptance criteria
- AC1: Overview is refactored from index-metrics view into an operator summary led by Current scope, Entry points, Signals and incidents, Snapshot contents, and secondary Diagnostics.
- AC2: Current scope shows the active snapshot, selected candidate or proc context when available, concise scope composition by kinds, and the actions Open files, Create workspace, Copy file list, Generate prompt, and Open diagram.
- AC3: Search supports Path vs Content mode, Current scope vs Whole snapshot scope, kind filters for All, procs, scripts, controls, inserts, docdef, logs, and refs, and exposes useful result actions without a heavy explanatory aside.
- AC4: Snapshots page becomes a more operational list or table that surfaces snapshot, captured time, ready state, freshness, contents summary, incidents, and actions, while de-emphasizing delete and large explanatory cards.
- AC5: Prompt UI works from the current scope, presents two user-facing scenarios (incident analysis and change request analysis), supports Generate prompt, Copy prompt, Save prompt, and Include diagram, while preserving existing prompt generation functionality behind the UI.
- AC6: Snapshot creation flow keeps a short default form and adds optional enrichments behind an Advanced sources accordion or similar progressive disclosure for control or prox or insert or related files, Papyrus PDF, incidents folder, and research or logs folder.
- AC7: The implementation preserves existing core functionality where feasible and avoids decorative dashboard elements, wide backend rewrites, separate dark-mode work, and V2-only features.
- AC8: The task is completed with repo-local proof artifacts, relevant checks, and a Russian summary for the user.

## Constraints
- Prefer /home/kts/lsa/lsa/web/static/app.js, /home/kts/lsa/lsa/web/static/style.css, /home/kts/lsa/lsa/web/static/index.html, and /home/kts/lsa/lsa/web/server.py as the main change surface.
- Do not remove existing core capabilities such as snapshot selection, workspace creation, file preview, prompt generation, diagram export, and search.
- Minimize backend changes to the data and API support necessary for operator utility improvements.
- Keep the design mature and utilitarian, with clear separation between passive information, work surfaces, and actions.
- Do not expand the task into a broad shell redesign, a new design system, or a dark-mode project.
- Keep all workflow artifacts under /home/kts/lsa/.agent/tasks/ui-console-v1-implementation/.

## Non-goals
- Separate incidents page or case-card knowledge mode.
- Broad global shell refactor beyond light cleanup needed for V1.
- Smart recommendations, activity feeds, hero blocks, or oversized statistics cards.
- Rich handoff bundle export beyond the requested V1 prompt and scope actions.
- Full redesign of prompt generation internals beyond the UI and minimal endpoint support required.

## Verification plan
- Build: run relevant automated tests or targeted scripts for the modified web server and prompt/search behavior if available.
- Unit tests: run focused pytest coverage for affected server behavior when practical.
- Integration tests: none unless there is an existing low-cost command to validate the UI/server flows.
- Lint: run a relevant lightweight check if available; otherwise rely on targeted tests and manual review.
- Manual checks:
  - Confirm Overview renders Current scope-first operator summary and pushes diagnostics down.
  - Confirm Search exposes mode, scope, and kind controls and returns filtered results.
  - Confirm Prompt shows two top-level scenarios and uses current scope without forcing candidate reselection as the main UI model.
  - Confirm Snapshots page surfaces operational metadata and a shorter creation flow with Advanced sources.
  - Confirm existing actions such as preview file, create workspace, copy file list, generate prompt, and open diagram still exist in the V1 flow.
