# Task Spec — Change Docs in the LSA Web UI

- TASK_ID: `changedocs-web`
- Status: FROZEN (specification only; no production code is changed by this artifact)
- Date frozen: 2026-06-05

---

## 1. Original task statement (preserved verbatim)

> Freeze a task spec at `.agent/tasks/changedocs-web/spec.md` (TASK_ID = `changedocs-web`) for adding a "Change Docs" feature to the LSA web UI. Do NOT implement anything — only produce the frozen spec.md with explicit acceptance criteria.
>
> ## Context: what we are building
> We are lifting an existing, mature, same-stack feature from another directory into the LSA web UI. The operator enters a **Parallel ID (PRID)** in the web UI; the backend fetches the change diff over ssh, drafts a **CAB Questionnaire** via the Claude API, and optionally renders a **PTF** and a **QA Checklist** (both deterministic, no API). Generated `.docx` files are saved server-side and downloadable from the UI.
>
> ## SOURCE to port (READ ALL OF THESE — they are the reference implementation)
> Directory: `<internal-cab-tool>/`
> - `generate_cab.py` — base CAB docx builder (`build_cab(content, out_path)`); python-docx; the CAB content schema is in its module docstring.
> - `change_docs/README.md` — overview of the diff-centric engine and guardrails.
> - `change_docs/cli.py` — orchestrator: context → draft CAB → render CAB/PTF/QA.
> - `change_docs/context.py` — diff gathering. `fetch(prid)` runs over ssh (alias `rhs`, reuses remote `lookup_pr_is.py`, deletes remote temp); `from_dir(folder)` for local; whitelist `CODE_EXTENSIONS`, size caps, `to_prompt(context)`, `REMOTE` config.
> - `change_docs/draft.py` — single bounded Claude API call (diff → CAB content JSON); MODELS (sonnet default, opus), MAX_OUTPUT_TOKENS, dry_run with cost estimate, usage.log, key from ANTHROPIC_API_KEY only.
> - `change_docs/render.py` — `render_cab`, `render_ptf`, `render_qa` (PTF/QA fill docx templates deterministically).
> - `change_docs/prompts/system_cab.md` — system prompt (asset to copy).
> - `change_docs/templates/ptf_template.docx`, `qa_template.docx` — assets to copy.
>
> ## TARGET codebase: LSA web UI (read these to ground integration points)
> Working dir: `/home/kts/lsa`
> - `lsa/web/server.py` — FastAPI app. Patterns to reuse: Pydantic request models; `@app.post`/`@app.get` routes; `StreamingResponse` + `_sse_event(...)` for long ops; config via `from lsa.config import load_user_config` (keys: `rhs_host`, `rhs_user`, `snaproot`, etc.); ssh target built as `{rhs_user}@{rhs_host}`. Static mounted at `/static`; `/` serves `static/index.html`.
> - `lsa/web/static/index.html`, `lsa/web/static/app.js`, `lsa/web/static/style.css` — the existing operator console UI (vanilla JS, panels). The new panel must match existing panel structure/aesthetic.
> - `pyproject.toml` — deps. The `web` optional-dependencies extra currently = fastapi + uvicorn. New deps `python-docx` and `anthropic` are REQUIRED for this feature.
>
> ## Agreed scope / decisions (bake these into the spec)
> 1. Diff source in the web UI = **ssh by Parallel ID only**. No local-folder input in the UI. Port `context.fetch`; make its `REMOTE` settings overridable from `~/.lsa/config.yaml` (fall back to the existing change_docs defaults / `ssh rhs` alias). Diff files are NOT persisted locally — read into memory, remote temp removed (already the behavior).
> 2. CAB is always drafted (LLM). PTF and QA are optional, chosen via UI checkboxes; PTF needs operator fields JIRA / hours / live-date. Default selection: CAB on; PTF/QA operator's choice.
> 3. Generated `.docx` saved to a server-side output dir (choose a sensible location, e.g. under snaproot or a dedicated changedocs output dir) and downloadable via a new endpoint. Re-download must work.
> 4. Port the package into `lsa/changedocs/` keeping internal logic and guardrails intact (extension whitelist, size caps, single bounded API call + one repair retry, dry-run/preview with cost estimate, usage.log, key only from ANTHROPIC_API_KEY, no tools to the model).
> 5. New deps: add `python-docx` and `anthropic` to the `web` optional-dependencies extra in pyproject (the feature lives in the web UI / `lsa serve`).
> 6. Keep a dry-run / preview capability (context + cost estimate, no API call) reachable from the web UI before spending on a real draft.
>
> ## What the spec.md must contain
> - Goal, scope, and explicit out-of-scope.
> - Constraints (minimal diff, preserve existing lsa patterns, guardrails preserved, no client data ever sent — only whitelisted code-extension diffs).
> - A concrete proposed surface: new module path `lsa/changedocs/`, new FastAPI routes (suggest: `POST /api/changedocs/preview` for dry-run, `POST /api/changedocs/generate`, `GET /api/changedocs/download`), request/response shapes, UI panel responsibilities.
> - Numbered acceptance criteria AC1, AC2, ... each independently verifiable.
> - A verification plan describing exact commands a fresh verifier would run.

---

## 2. Goal

Port the mature `change_docs` engine from `<internal-cab-tool>/` into the LSA repository as `lsa/changedocs/`, and expose it through the LSA web UI (`lsa serve`) as a new "Change Docs" panel. The operator enters a Parallel ID (PRID); the backend:

1. fetches the change diff over ssh (whitelisted code-extension diffs only, into memory),
2. always drafts a **CAB Questionnaire** through a single bounded Claude API call,
3. optionally renders a **PTF** and a **QA Checklist** (both deterministic, no API),
4. saves the generated `.docx` files into a server-side output directory and exposes them for (re)download from the UI.

A dry-run / preview path (gathered context + cost estimate, **no** API call, **no** docx output) must be reachable from the UI before any paid draft.

---

## 3. Scope (in scope)

1. New Python package `lsa/changedocs/` containing the ported engine: context gathering, drafting, rendering, CAB builder, prompt asset, and docx templates. Internal logic and guardrails preserved.
2. The CAB docx builder currently living in the source root as `generate_cab.py` is ported into the package (e.g. `lsa/changedocs/generate_cab.py`) so `render_cab` reuses `build_cab` via a normal package import — no `sys.path` hacks.
3. New FastAPI routes in `lsa/web/server.py`:
   - `POST /api/changedocs/preview` — dry-run: gather context, return cost estimate, make NO API call and write NO files.
   - `POST /api/changedocs/generate` — gather context, draft CAB, render selected docs, return download references.
   - `GET /api/changedocs/download` — stream a previously generated `.docx` by reference.
4. `REMOTE` ssh-lookup settings overridable from `~/.lsa/config.yaml`, falling back to the ported `change_docs` defaults (ssh alias `rhs`, csv/script/paths.json locations, username).
5. New "Change Docs" panel in the web UI (`index.html`, `app.js`, `style.css`) matching the existing panel structure and aesthetic: PRID input, model selector (sonnet default / opus), preview button, CAB-always + PTF/QA checkboxes, PTF operator fields (JIRA / hours / live-date), and download links for the produced files.
6. Add `python-docx` and `anthropic` to the `web` optional-dependencies extra in `pyproject.toml`.
7. Tests for the deterministic, offline parts (context parsing/whitelist/caps, dry-run cost estimate with no API call, PTF/QA rendering), plus request-model and route-presence tests. No live ssh and no live Claude API call in tests.

---

## 4. Out of scope (non-goals)

1. Local-folder (`--from-dir`) diff input in the web UI. `from_dir` MAY be carried over inside the ported module for parity/tests, but the UI exposes PRID-over-ssh only.
2. Any change to the existing snapshot / plan / prompt / search / workspace features beyond additively wiring the new panel into the navigation and renderer.
3. Live calls to ssh `rhs` or the Claude API from automated tests / CI.
4. Editing the CAB content schema, the `system_cab.md` rules, or the PTF/QA template layouts (they are copied as-is).
5. Real Claude pricing accuracy — `PRICE_PER_MTOK` remains an estimate, as documented in the source.
6. Authentication / multi-user concerns, rate limiting beyond the existing single-bounded-call guardrail.
7. A standalone `lsa changedocs` CLI subcommand (the feature lives in the web UI; the ported orchestrator may exist as a module function but a new Typer command is not required).

---

## 5. Constraints

1. **Minimal diff.** Touch only: the new `lsa/changedocs/` package, additive routes/models in `lsa/web/server.py`, additive UI in the three static files, the `web` extra in `pyproject.toml`, and new test file(s). Do not refactor unrelated code.
2. **Preserve existing LSA patterns.** Reuse: Pydantic `BaseModel` request models, `@app.post` / `@app.get` decorators, `HTTPException` for errors, `load_user_config()` for config, ssh target built as `f"{rhs_user}@{rhs_host}"` when a user is set. Reuse `_sse_event(...)` + `StreamingResponse` only if a streaming UX is chosen; a plain JSON response is acceptable for these operations.
3. **Guardrails preserved exactly** (ported unchanged in spirit):
   - Input is code diffs only — `CODE_EXTENSIONS` whitelist plus `MAX_FILE_DIFF_BYTES` per-file and `MAX_TOTAL_DIFF_BYTES` total caps. Non-whitelisted / data-file diffs are skipped and never sent.
   - Exactly one bounded Claude call per ticket, with at most one repair retry on malformed JSON.
   - Output capped at `MAX_OUTPUT_TOKENS`.
   - No tools given to the model (pure text in, JSON out).
   - System prompt sent with prompt caching.
   - API key read only from `ANTHROPIC_API_KEY`; never logged or returned to the client.
   - Every real (non-dry-run) draft appends one line to a `usage.log`.
4. **No client data ever sent.** Only whitelisted code-extension diffs leave the machine. Diffs are read into memory; the remote temp folder is removed by `fetch` (existing behavior); no diff content is persisted to local disk by the web feature.
5. **Idempotency / safety.** Re-running generate for the same PRID overwrites the same named outputs deterministically; download must work on a previously generated file. The download route must reject path traversal and only serve files inside the configured output directory.
6. **PRID validation.** `fetch` requires a PRID of `>= 14 digits` (`\d{14,}`); the API must surface a clear 400 on an invalid PRID rather than a 500.
7. **Graceful degradation when unconfigured.** Missing `rhs_host` / ssh config, missing `ANTHROPIC_API_KEY`, or absent `anthropic` SDK must produce clear, operator-readable error responses, not stack traces — mirroring existing patterns (e.g. `raise HTTPException(400, "rhs_host not configured in ~/.lsa/config.yaml")`).

---

## 6. Proposed surface (reference for the builder; exact field names may be refined as long as ACs hold)

### 6.1 Module layout

```
lsa/changedocs/
  __init__.py            # exports the public API (e.g. context, draft, render, generate)
  context.py             # ported: parse_header, _collect_diffs, from_dir, fetch, to_prompt,
                         #         CODE_EXTENSIONS, MAX_*_BYTES, REMOTE, ContextError
  draft.py               # ported: dry_run, draft_cab, estimate_tokens, MODELS, DEFAULT_MODEL,
                         #         MAX_OUTPUT_TOKENS, PRICE_PER_MTOK, usage.log, DraftError
  render.py              # ported: render_cab, render_ptf, render_qa (uses build_cab)
  generate_cab.py        # ported build_cab (CAB docx builder); imported by render.py
  prompts/system_cab.md  # copied asset
  templates/ptf_template.docx   # copied asset
  templates/qa_template.docx    # copied asset
```

Notes for the builder:
- Replace source-level `sys.path.insert(...)` + bare `from context import ...` / `from generate_cab import build_cab` with proper intra-package imports (relative or `lsa.changedocs.*`).
- `REMOTE` defaults are kept; the web layer overlays config from `~/.lsa/config.yaml` before calling `fetch`. Suggested config keys (additive, optional): a `changedocs` mapping mirroring `REMOTE` (`ssh_alias`, `csv`, `script`, `dest_base`, `paths_json`, `username`). The ssh alias SHOULD default to `rhs` to match the existing `change_docs` default; if the repo prefers, it MAY also honor existing `rhs_host`/`rhs_user` — but at minimum the ported defaults must remain the fallback so an unconfigured site still behaves like the source.
- `usage.log` location must be writable at runtime (e.g. inside the package dir as in source, or under the output dir). Wherever it lives, a real draft appends to it and a dry-run does not.

### 6.2 Output location

Generated `.docx` files are written to a dedicated server-side directory, suggested:
`{snaproot}/changedocs/<ticket_id>/` when `snaproot` is configured, otherwise a sensible fallback under the user home (e.g. `~/.lsa/changedocs/<ticket_id>/`). File names follow the source convention:
- `<ticket_id>_CAB_Questionnaire.docx`
- `<ticket_id>_PTF.docx`
- `<ticket_id>_QA_Checklist.docx`

### 6.3 Routes and shapes

`POST /api/changedocs/preview`
- Request: `{ "prid": "<14+ digits>", "model": "sonnet"|"opus" }`
- Behavior: `fetch(prid)` → if no code diffs, return a clear message; else compute dry-run estimate via `draft.dry_run` / `estimate_tokens`. NO API call, NO files written.
- Response (shape illustrative): `{ "parallel_id": str, "description": str, "files": [str], "diffs": [{"file": str, "truncated": bool}], "skipped": [str], "model_id": str, "estimated_input_tokens": int, "max_output_tokens": int, "estimated_cost_usd": float }`

`POST /api/changedocs/generate`
- Request: `{ "prid": str, "model": "sonnet"|"opus", "ticket_id": str|null, "ptf": bool, "qa": bool, "jira": str, "hours": str, "live_date": str, "qa_job": str|null, "qa_items": [str]|null }`
- Behavior: `fetch(prid)` → `draft_cab` (CAB always) → `render_cab`; if `ptf`: `render_ptf` with operator fields; if `qa`: `render_qa`. Write into the output dir.
- Response (shape illustrative): `{ "ticket_id": str, "out_dir": str, "files": [{"kind": "cab"|"ptf"|"qa", "name": str, "download": "/api/changedocs/download?...", "path": str}], "skipped": [str], "usage": {"input_tokens": int, "output_tokens": int} }`

`GET /api/changedocs/download`
- Query: a reference identifying a generated file (e.g. `ticket_id` + `name`, or a relative path under the output dir).
- Behavior: validate the resolved path is inside the output dir (reject traversal, mirror `/api/file` guard at `server.py` ~L533), 404 if absent, else stream the `.docx` with `application/vnd.openxmlformats-officedocument.wordprocessingml.document` and a `Content-Disposition: attachment` header.

### 6.4 UI panel responsibilities (`Change Docs`)

- New sidebar nav entry and a `render()` switch case in `app.js` (the renderer dispatches on `data-step`, see `app.js` ~L377-L386); panel markup matching existing panels' structure/classes.
- Controls: PRID text input; model select (default sonnet); "Preview (no API call)" button; checkboxes `PTF` and `QA` (CAB is implied/always-on and shown as such); PTF operator fields JIRA / hours / live-date (relevant when PTF checked); optional QA job / QA items; "Generate" button.
- Preview result area shows: parallel id, description, file list, included-diff count, skipped list, model, estimated tokens and estimated cost — explicitly labeled as an estimate and "no API call made".
- Generate result area shows download links for each produced file; links must re-download on repeat clicks.
- Errors (unconfigured ssh, missing key, invalid PRID, no code diffs) shown via the existing toast/error pattern, not raw stack traces.
- `app.js` must remain syntactically valid (the repo has a `node --check` test).

---

## 7. Acceptance criteria

Each criterion is independently verifiable. "Test env" = the project venv used by `uv run pytest` (Python 3.14 `.venv`), which must have the `web` extra (including the newly added `python-docx` and `anthropic`) installed.

- **AC1 — Package exists and is importable.** `lsa/changedocs/__init__.py` exists and `import lsa.changedocs` succeeds with no `sys.path` manipulation. Submodules `lsa.changedocs.context`, `lsa.changedocs.draft`, `lsa.changedocs.render`, and the ported CAB builder all import cleanly.

- **AC2 — Assets ported.** `lsa/changedocs/prompts/system_cab.md`, `lsa/changedocs/templates/ptf_template.docx`, and `lsa/changedocs/templates/qa_template.docx` exist and are non-empty; `draft` loads the system prompt and `render_ptf` / `render_qa` open their templates without error.

- **AC3 — Whitelist and size caps enforced.** Given a synthetic set of `(filename, diff_text)` pairs containing a whitelisted code file, a non-whitelisted/data extension, an empty diff, an oversized per-file diff, and pairs exceeding the total cap, the context collector includes only valid whitelisted diffs, marks oversized ones truncated, and records the rest in `skipped`. `CODE_EXTENSIONS`, `MAX_FILE_DIFF_BYTES`, and `MAX_TOTAL_DIFF_BYTES` retain the ported values. Verified by a unit test with no ssh/API.

- **AC4 — Header parsing.** `parse_header` extracts Description, Parallel ID, and the numbered Files list from a sample report text. Verified by a unit test.

- **AC5 — Dry-run / preview makes no API call and returns a cost estimate.** A unit test (and the `POST /api/changedocs/preview` route, exercised with `fetch` and `draft.dry_run`/estimate mocked) confirms: no `anthropic` client is constructed, no `usage.log` line is appended, and the response contains a model id, estimated input tokens, `max_output_tokens`, and an estimated cost (USD). Asserting "no API call" is done by monkeypatching the anthropic client/`draft_cab` and verifying it is never invoked on the preview path.

- **AC6 — Generate returns download references for the requested docs.** With `context.fetch` and `draft.draft_cab` mocked (so no ssh and no API), calling `POST /api/changedocs/generate` with a valid PRID and a selection (e.g. CAB only; CAB+PTF; CAB+PTF+QA) writes exactly the requested `.docx` files to the output dir and returns one download reference per produced file. CAB is always produced. Verified without ssh/API.

- **AC7 — PTF and QA render deterministically (no API).** Unit tests call `render_ptf` and `render_qa` against the ported templates with a synthetic context (parallel_id, description, files) and operator fields, producing valid `.docx` files; `render_qa` clones the `L1` row per item and fills `L1..Ln`; `render_ptf` fills JIRA/hours/live-date/parallel-id/description/files and the file-count line. No Claude API involved.

- **AC8 — Download route works and is path-safe.** `GET /api/changedocs/download` streams a previously generated `.docx` (correct content type + attachment disposition), returns 404 for a missing file, and rejects path traversal outside the output dir (mirroring the `/api/file` guard). Re-download of the same file succeeds.

- **AC9 — Guardrails intact in code.** Static/behavioral verification that the ported `draft.draft_cab` reads the key only from `ANTHROPIC_API_KEY`, passes no `tools` to the model, sends the system prompt with `cache_control` (prompt caching), caps output at `MAX_OUTPUT_TOKENS`, performs at most one repair retry on malformed JSON, and appends to `usage.log` only on a real call. PRID shorter than 14 digits raises `ContextError` (and the API maps it to a 400).

- **AC10 — pyproject web extra updated.** `pyproject.toml` `[project.optional-dependencies].web` includes `fastapi`, `uvicorn`, `python-docx`, and `anthropic`. The lockfile/env used by `uv run pytest` resolves these so `import docx` and `import anthropic` succeed in the test env.

- **AC11 — Existing web tests still pass.** `uv run pytest tests/test_web_server.py` passes with no regressions, and the new routes/models are present on the FastAPI `app` (route paths `/api/changedocs/preview`, `/api/changedocs/generate`, `/api/changedocs/download` are registered).

- **AC12 — UI panel present and valid.** `index.html` + `app.js` add a "Change Docs" panel reachable from the sidebar nav (new `data-step` and `render()` case): PRID input, model selector, a preview action, PTF and QA checkboxes with PTF JIRA/hours/live-date fields, and a download-links result area, styled consistently with existing panels. `node --check lsa/web/static/app.js` passes (the existing `test_app_js_parses_when_node_is_available` test still passes).

- **AC13 — Whole suite green.** `uv run pytest` (full suite) passes with no new failures versus the pre-change baseline.

---

## 8. Verification plan (exact commands a fresh verifier runs)

All commands run from `/home/kts/lsa`. The canonical interpreter is the project `.venv` driven by `uv run` (confirmed: `uv run pytest tests/test_web_server.py` passes today on Python 3.14). Live ssh `rhs` and live Claude API calls are NOT runnable here and MUST be covered by mocks/unit tests, never live calls.

1. **Baseline (before judging the change):**
   - `uv run pytest -q` — record the current pass/fail baseline.

2. **Dependencies / extra (AC10):**
   - `uv run python -c "import docx, anthropic; print('deps ok')"`
   - Inspect `pyproject.toml` `[project.optional-dependencies].web` contains `python-docx` and `anthropic` (in addition to fastapi/uvicorn).

3. **Package import (AC1, AC2):**
   - `uv run python -c "import lsa.changedocs; import lsa.changedocs.context as c; import lsa.changedocs.draft as d; import lsa.changedocs.render as r; print('import ok')"`
   - `uv run python -c "import importlib.resources as ir, pathlib; print('assets',  all(p.exists() for p in [pathlib.Path('lsa/changedocs/prompts/system_cab.md'), pathlib.Path('lsa/changedocs/templates/ptf_template.docx'), pathlib.Path('lsa/changedocs/templates/qa_template.docx')]))"`

4. **Routes registered (AC11):**
   - `uv run python -c "from lsa.web import server; paths={r.path for r in server.app.routes}; assert {'/api/changedocs/preview','/api/changedocs/generate','/api/changedocs/download'} <= paths, sorted(paths); print('routes ok')"`

5. **New unit tests (AC3–AC9, deterministic, mocked):**
   - `uv run pytest tests/test_changedocs.py -q` (or whatever the new test module is named) — covers: whitelist/caps (AC3), header parse (AC4), dry-run no-API + cost estimate (AC5), generate writes requested files with `fetch`/`draft_cab` mocked (AC6), PTF/QA rendering (AC7), download path-safety (AC8), and guardrail assertions (AC9).
   - The preview/generate route tests follow the existing async-test convention in `tests/test_web_server.py` (`@pytest.mark.anyio`, calling the route coroutine directly with `_get_snapshot` / config / `context.fetch` / `draft.draft_cab` monkeypatched). No `httpx`/TestClient required.

6. **Existing web tests + JS check (AC11, AC12, AC13):**
   - `uv run pytest tests/test_web_server.py -q` — must stay green (includes `node --check` on `app.js` when node is available).
   - `node --check lsa/web/static/app.js` (if node present) — must exit 0.
   - `uv run pytest -q` — full suite green vs baseline.

7. **Manual / non-CI confirmations (documented, not automated):**
   - ssh fetch and a live CAB draft are validated manually by the operator (real PRID + `ANTHROPIC_API_KEY`); these are explicitly excluded from automated verification.

---

## 9. Assumptions and narrowly-resolved ambiguities

1. **Test runner.** The canonical test environment is the project `.venv` (Python 3.14) invoked via `uv run pytest`; a plain `uv run python` may resolve a different interpreter without the web deps, so verification commands use `uv run` against pytest's interpreter. Today that venv has `fastapi`/`anyio`/`starlette` but NOT `httpx`/`docx`/`anthropic`; this task adds `python-docx` and `anthropic` to the `web` extra and they must be present in the test env for AC10/AC13.
2. **No TestClient dependency added.** Async route tests follow the existing pattern of awaiting the route coroutine directly with monkeypatched collaborators (the repo currently has no `httpx`); adding `httpx`/TestClient is not required and is out of scope.
3. **Config overlay.** `REMOTE` ssh settings are overridable via an optional `changedocs` mapping in `~/.lsa/config.yaml`; when absent, the ported `change_docs` defaults (ssh alias `rhs`, etc.) apply. Existing `rhs_host`/`rhs_user` MAY additionally be honored, but the ported defaults remain the guaranteed fallback. Exact key names are an implementation detail provided they satisfy the ACs and keep the source defaults working.
4. **Output directory.** Generated docs go under `{snaproot}/changedocs/<ticket_id>/` when `snaproot` is set, else `~/.lsa/changedocs/<ticket_id>/`. The download route confines serving to this directory.
5. **`from_dir` retained but unexposed.** The local-folder code path is kept inside the ported module (useful for deterministic tests of context parsing) but is not surfaced in the web UI, per the agreed scope.
6. **`generate_cab.py` is ported into the package** (not imported from the external source tree), so `render_cab` reuses `build_cab` through a clean package import and the feature is self-contained in `lsa/`.
7. **Response field names in section 6.3 are illustrative.** The builder may adjust exact JSON keys as long as each acceptance criterion remains satisfiable.

---

## 10. Source/target reference index (read during freezing)

Source (reference implementation, do not modify):
- `<internal-cab-tool>/generate_cab.py` — `build_cab(content, out_path)`; CAB content schema in docstring.
- `<internal-cab-tool>/change_docs/context.py` — `CODE_EXTENSIONS`, `MAX_TOTAL_DIFF_BYTES=200_000`, `MAX_FILE_DIFF_BYTES=60_000`, `REMOTE`, `parse_header`, `_collect_diffs`, `from_dir`, `fetch` (PRID `\d{14,}`, ssh alias `rhs`, removes remote temp), `to_prompt`, `ContextError`.
- `<internal-cab-tool>/change_docs/draft.py` — `MODELS` (sonnet/opus), `DEFAULT_MODEL="sonnet"`, `MAX_OUTPUT_TOKENS=4000`, `PRICE_PER_MTOK`, `dry_run`, `draft_cab` (single call + one repair retry, prompt caching, key from `ANTHROPIC_API_KEY`, no tools, `usage.log`), `DraftError`. NOTE: source uses `from context import to_prompt` — must become a package import when ported.
- `<internal-cab-tool>/change_docs/render.py` — `render_cab`, `render_ptf`, `render_qa`. NOTE: source uses `sys.path.insert(...)` + `from generate_cab import build_cab` — must become a package import when ported.
- `<internal-cab-tool>/change_docs/cli.py` — orchestration order (context → draft → render CAB/PTF/QA) and output file naming.
- `<internal-cab-tool>/change_docs/README.md` — guardrails summary.
- `<internal-cab-tool>/change_docs/prompts/system_cab.md` — CAB system prompt (copy as-is).
- `<internal-cab-tool>/change_docs/templates/ptf_template.docx`, `qa_template.docx` — copy as-is.

Target (LSA repo, integration points):
- `/home/kts/lsa/lsa/web/server.py` — FastAPI `app`, Pydantic models, `@app.post`/`@app.get`, `HTTPException`, `_sse_event`, `StreamingResponse`, `load_user_config()`, ssh target `f"{rhs_user}@{rhs_host}"`, path-traversal guard at `read_file` (~L533).
- `/home/kts/lsa/lsa/config.py` — `load_user_config()`; config keys `snaproot`, `rhs_host`, `rhs_user`, `workroot`.
- `/home/kts/lsa/lsa/cli.py` — `serve` command (~L1003) wires `create_app` and runs `lsa.web.server:app`.
- `/home/kts/lsa/lsa/web/static/index.html`, `app.js` (renderer switch ~L377-L386, `data-step` nav), `style.css` — UI panel host.
- `/home/kts/lsa/pyproject.toml` — `[project.optional-dependencies].web` (currently `fastapi`, `uvicorn`).
- `/home/kts/lsa/tests/test_web_server.py` — existing web test patterns (`@pytest.mark.anyio`, direct coroutine await with monkeypatch; `node --check` for `app.js`).
