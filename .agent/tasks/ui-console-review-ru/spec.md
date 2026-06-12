# Task Spec: ui-console-review-ru

## Metadata
- Task ID: ui-console-review-ru
- Created: 2026-03-25T15:15:36+00:00
- Repo root: /home/kts/lsa
- Working directory at init: /home/kts/lsa

## Guidance sources
- User task statement captured at init and in the active chat.
- /home/kts/lsa/AGENTS.md
- /home/kts/lsa/lsa/web/static/index.html
- /home/kts/lsa/lsa/web/static/style.css
- /home/kts/lsa/lsa/web/static/app.js
- /home/kts/lsa/lsa/web/server.py
- /home/kts/lsa/codex-ui-review-ru.txt

## Original task statement
Провести review текущего UI операторской консоли без внесения изменений в код. Цель: понять, что в интерфейсе перегружено, что выглядит как лишние псевдо-интерактивные информационные блоки, какие метрики и карточки не дают реальной пользы оператору, и как перестроить Overview / Search / Snapshots / Prompt в более полезный и зрелый рабочий интерфейс. Особое внимание уделить Overview: текущие counters вроде artifacts, nodes, edges, message codes и подобные внутренние метрики кажутся малоинформативными для оператора и, вероятно, должны быть либо понижены по приоритету, либо перенесены в diagnostics. Вместо этого важнее показать состав scope, список типов файлов, entry points, incidents/signals, действия с workspace/export/search/prompt/diagram, а также сделать правые информационные панели менее карточными и менее похожими на активные элементы. Нужен не код, а качественное предложение по UX/UI и IA.

## Acceptance criteria
- AC1: Provide a review of the current operator console IA and UI behavior grounded in the current repository implementation, not generic UX advice.
- AC2: Identify which current elements are useful to an operator/programmer and which are noise, with explicit attention to Overview metrics, passive right-side panels, repeated shell metadata, and candidate/prompt flow.
- AC3: Propose a V1 information architecture for Overview, Search, Snapshots, and Prompt that prioritizes operator utility over dashboard aesthetics.
- AC4: Define "Current scope" as the primary working block and specify its required contents: active snapshot, selected candidate/proc, concise scope composition, and the actions Open files, Create workspace, Copy file list, Generate prompt, and Open diagram.
- AC5: Propose a snapshot creation flow that covers Linux-server copy plus optional inputs for control/prox/insert/related files, Papyrus PDF, incidents folder, and research/log files, while explicitly explaining how to avoid overloading the UI.
- AC6: Propose Generate prompt as a feature with two distinct scenarios: incident/support analysis and change request analysis, and explain why each scenario is useful to the operator.
- AC7: Include a second-pass self-critique that removes weak, decorative, or low-value ideas from the proposal before presenting the final recommendation.
- AC8: Deliver the final output in Russian using the exact section structure requested by the user and without making production code changes.

## Constraints
- Do not modify production code, styling, or server behavior in this task.
- Base the review on the current implemented console structure and current available data/API surfaces in the repository.
- Prefer mature technical console patterns over promotional/dashboard presentation.
- Prioritize operator/programmer utility, fast orientation, and handoff value.
- Right-side informational panels must not be treated as primary interactive cards in the proposal.
- Dark mode is explicitly lower priority than usefulness and workflow clarity.
- Keep all workflow artifacts for this task inside /home/kts/lsa/.agent/tasks/ui-console-review-ru/.
- The final answer must be written in Russian.

## Assumptions
- "Current operator console" refers to the current web console implemented in /home/kts/lsa/lsa/web/static/ and backed by /home/kts/lsa/lsa/web/server.py.
- V1 is a redesign proposal, not an implementation plan with pixel-perfect mockups.
- "Practical benefit" means helping the operator identify scope, open the right files faster, create a workspace, search effectively, and generate a useful external-LLM handoff.

## Non-goals
- Do not implement the redesign.
- Do not redesign branding, visual identity, or theme system beyond recommendations directly tied to operator usefulness.
- Do not expand the task into a full design system, prototype, or exhaustive component inventory.
- Do not propose decorative metrics, hero panels, or dashboard widgets that lack direct operator value.
- Do not define backend contracts beyond what is needed to explain the V1 proposal.

## Verification plan
- Build: none; no production code changes are allowed in this task.
- Unit tests: none; analysis-only deliverable.
- Integration tests: none; analysis-only deliverable.
- Lint: none required unless task artifacts are programmatically validated later.
- Manual checks:
  - Confirm the review references the current implemented pages and flows: Snapshots, Bundle, Prompt, Overview, and Search.
  - Confirm the proposal explicitly covers Overview, Search, Snapshots, Prompt, Current scope, snapshot creation flow, and Generate prompt.
  - Confirm the proposal distinguishes useful operator-facing data from lower-priority diagnostics.
  - Confirm the final answer includes a self-critique pass and follows the user's 12-section Russian format.
  - Confirm no production files outside .agent/tasks/ui-console-review-ru/ were edited.
