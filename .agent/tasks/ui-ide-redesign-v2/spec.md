# Task Spec: ui-ide-redesign-v2

## Metadata
- Task ID: ui-ide-redesign-v2
- Created: 2026-03-25T01:36:48+00:00
- Repo root: /home/kts/lsa
- Working directory at init: /home/kts/lsa

## Guidance sources
- User task text captured during `init`
- `lsa/web/static/index.html`
- `lsa/web/static/style.css`
- `lsa/web/static/app.js`

## Original task statement
Сделать заметный редизайн веб-интерфейса в стиле professional developer tool: IDE-like, terminal-inspired, GitHub-tech UI. Не косметический polish, а ощутимое новое визуальное направление. Цель: убрать toy-like ощущение, уменьшить чрезмерные отступы, большие скругления, мягкость и декоративность. Сделать интерфейс плотнее, строже, технологичнее и ближе к рабочему инструменту для разработчиков. Разрешается заметно менять layout, spacing, radii, typography, panel system, headers, navigation chrome, tables, forms, cards, search/file/code surfaces, empty/loading/error states. Обязательно заметно переработать минимум 2–3 ключевых экрана. Можно менять shared UI primitives и композицию ключевых экранов, если не ломается основной функционал. Не трогать backend/API и бизнес-логику без необходимости. Результат должен быть визуально заметным, а не косметическим.

## Frozen visual direction
Operator Workbench: a light-theme engineering console that combines IDE chrome, terminal density, and GitHub-style surface discipline. The redesign should use sharper borders, compact spacing, mono-first metadata treatment, restrained shadows, and stronger panel segmentation so the app reads like a production developer tool rather than a soft dashboard.

## Acceptance criteria
- AC1: The application shell is visibly redesigned into a denser IDE-like workbench with stronger top bar and sidebar chrome, smaller radii, restrained shadows, and clearer panel boundaries while preserving the existing single-page navigation and API-driven behavior.
- AC2: Shared UI primitives in `lsa/web/static/style.css` are updated so buttons, form controls, cards, panels, section headers, modals, tables or list-like file/search surfaces, and empty/loading/error states consistently follow the frozen `Operator Workbench` direction instead of the current softer aesthetic.
- AC3: At least three key screens receive a noticeable visual redesign through production markup and styling updates: `Snapshots`, `Build Bundle`, and `Search` are required, and additional improvements to `Generate Prompt` and `Overview` are encouraged when they can safely reuse the same primitive system.
- AC4: Technical-content surfaces are made meaningfully more mature and readable, including stronger treatments for file lists, search hits, code or prompt output blocks, metadata badges, status messages, progress displays, and modal previews.
- AC5: The redesign keeps functionality intact: snapshot creation, selection, deletion, bundle generation, candidate switching, file preview, workspace creation, prompt generation, stats rendering, search, modal close behavior, toast notifications, and Mermaid-related actions continue to work without backend or API changes unless strictly required for safe presentation.
- AC6: Task artifacts under `.agent/tasks/ui-ide-redesign-v2/` are updated with concise evidence, verification results, and a final verdict grounded in local checks and current repository state.

## Constraints
- Do not ask clarification questions.
- Do not wait for confirmation before proceeding.
- Do not stay conservative when choosing the visual direction; prioritize visible, meaningful UI change over minor polish.
- Keep core functionality and client-side behavior intact.
- Avoid backend or API changes unless required for safe UI presentation.
- Prefer changes that flow through shared layout and UI primitives first, with targeted markup updates in `app.js` where presentation needs stronger structure.
- Keep all workflow artifacts inside `.agent/tasks/ui-ide-redesign-v2/`.

## Non-goals
- No frontend framework migration or SPA architecture rewrite.
- No backend feature work, data-model changes, or API contract redesign unless strictly required.
- No feature-scope expansion beyond the existing screens and flows.
- No speculative accessibility, localization, or state-management overhaul outside the touched presentation code.
- No attempt to make the UI look playful, consumer-SaaS, or visually soft.

## Assumptions
- The production frontend surface for this task is the FastAPI-served static SPA in `lsa/web/static/`, so the redesign should be implemented by editing `index.html`, `style.css`, and selective render markup in `app.js`.
- A "mature technical style" is best satisfied here by a light operator-console direction rather than a dark theme, because the existing app already uses a light palette and the user emphasized technical maturity more than theme inversion.
- "At least 2-3 key screens" should be interpreted as visibly changing multiple route renderers and the shared shell, not just adjusting global colors.
- The safest way to preserve functionality is to keep current API calls and event wiring in place while altering layout wrappers, class structure, and shared CSS tokens.

## Verification plan
- Build: Run the most relevant local project validation command(s) available for this repo and capture outputs in task artifacts.
- Unit tests: Run the project test suite, or the closest focused local tests if the full suite is unnecessarily broad.
- Integration tests: None expected for the static SPA unless an existing repo command already covers end-to-end web behavior.
- Lint: Run any available local lint or static-check command if present; otherwise record that no dedicated frontend lint step exists.
- Manual checks:
  - Review the rendered shell and route markup for `Snapshots`, `Build Bundle`, `Search`, and any additional touched screens to confirm the redesign is visibly stronger and denser.
  - Confirm forms, buttons, modal previews, code-like outputs, progress states, empty states, error states, and metadata surfaces still have valid hooks and readable structure.
  - Verify existing interactions remain wired to the same actions and API calls in `app.js`.
