# Task Spec: ui-tech-refresh

## Metadata
- Task ID: ui-tech-refresh
- Created: 2026-03-25T01:03:31+00:00
- Repo root: /home/kts/lsa
- Working directory at init: /home/kts/lsa

## Guidance sources
- User task text captured during `init`
- `lsa/web/server.py`
- `lsa/web/static/index.html`
- `lsa/web/static/style.css`
- `lsa/web/static/app.js`

## Original task statement
Сделать интерфейс более профессиональным и техническим: уменьшить избыточные отступы, скругления и декоративность, усилить визуальную иерархию, привести UI к стилю developer tools / technical SaaS, улучшить формы, панели, таблицы, модалки, loading/error/empty states, не ломая существующий функционал.

## Acceptance criteria
- AC1: The UI shell presents a denser, more technical visual style on the main visible screens (`Snapshots`, `Build Bundle`, `Generate Prompt`, `Overview`, `Search`) by reducing oversized spacing and rounding, strengthening panel/border structure, and using a restrained professional palette while preserving all existing routes and interactions.
- AC2: Shared UI primitives in `style.css` are refreshed first so cards, buttons, fields, section headers, lists, modals, loading states, empty states, and status treatments look consistent across the application without broad rewrites to page logic.
- AC3: The first implementation pass adds higher-signal information hierarchy for technical workflows, including improved shell chrome, clearer section framing, denser file/search result presentation, and better readability of code-like content and metadata.
- AC4: Existing functionality is preserved: snapshot selection/deletion/creation, bundle generation, candidate switching, file preview, workspace creation, prompt generation, stats rendering, search, modal behavior, toasts, and Mermaid integration continue to work without API changes.
- AC5: Task artifacts under `.agent/tasks/ui-tech-refresh/` are updated with a concise implementation record, concrete verification evidence, and any skipped risky items are explicitly noted rather than partially implemented.

## Constraints
- Do not ask clarification questions.
- Do not wait for confirmation before proceeding.
- Do not perform broad rewrites or restructure the SPA architecture.
- Preserve current functionality and API contracts.
- Prefer improvements that flow through shared UI primitives and visible screens first.
- If a change is risky, skip it and note the risk instead of blocking.
- Keep task workflow artifacts inside `.agent/tasks/ui-tech-refresh/`.

## Non-goals
- No backend endpoint changes unless strictly required for safe UI presentation.
- No frontend framework migration, bundler change, or multi-file componentization.
- No redesign of application flow, information architecture, or feature scope.
- No speculative accessibility or internationalization overhaul beyond safe presentational improvements already touched by the first pass.
- No screenshot-goldening or browser automation setup unless already present locally.

## Assumptions
- The current frontend is the FastAPI-served static SPA under `lsa/web/static/`, so the first pass should focus on `index.html`, `style.css`, and targeted `app.js` markup updates.
- "Professional, denser, more technical" means moving away from soft consumer-SaaS styling toward sharper borders, tighter spacing, monospaced metadata surfaces, and stronger section framing, not introducing a dark theme or a brand overhaul.
- "Highest-impact, lowest-risk" favors CSS and small markup improvements on shared primitives over changing data flow, API usage, or navigation behavior.

## Verification plan
- Build: Run the repo’s available local validation command(s) relevant to Python/FastAPI/static assets, if any.
- Unit tests: Run focused existing tests that cover the web server or general application behavior when available; otherwise run the project’s default test command.
- Integration tests: None expected for the static SPA unless an existing local check is already defined.
- Lint: Run any available local lint or static checks if configured; otherwise note that none are present.
- Manual checks:
  - Load the root page and verify the shell, navigation, cards, forms, modal, and content areas render.
  - Exercise the visible screens by inspecting generated markup in `app.js` and confirming event wiring remains unchanged.
  - Confirm empty/error/loading states still have valid containers and readable styling hooks.
