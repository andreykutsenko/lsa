# Evidence — changedocs-web

TASK_ID: `changedocs-web`
Mode: BUILD + evidence
Date: 2026-06-08
Interpreter: project `.venv` (Python 3.14) via `uv run`
Working dir: `/home/kts/lsa`

Overall: **PASS** — every acceptance criterion AC1–AC13 is PASS in this environment.
Live ssh `rhs` and live Claude API are not runnable here and are covered by mocks
(per spec section 8.7), not live calls.

Raw command outputs are under `.agent/tasks/changedocs-web/artifacts/`.

---

## AC1 — Package exists and is importable (no sys.path) — PASS
Command:
```
uv run python -c "import lsa.changedocs; import lsa.changedocs.context as c; import lsa.changedocs.draft as d; import lsa.changedocs.render as r; from lsa.changedocs.generate_cab import build_cab; print('import ok')"
```
Output: `import ok`. `draft.py` uses `from .context import to_prompt`; `render.py`
uses `from .generate_cab import build_cab`. No `sys.path` manipulation in the package
(`grep -rn "sys.path" lsa/changedocs` → none).
Artifact: `artifacts/ac1_import.txt`.

## AC2 — Assets ported and loadable — PASS
Command:
```
uv run python -c "import pathlib; print('assets', all(p.exists() and p.stat().st_size>0 for p in [...prompts/system_cab.md, templates/ptf_template.docx, templates/qa_template.docx]))"
```
Output: `assets True`. `render_ptf`/`render_qa` open their templates in AC7 tests;
`draft.dry_run` loads `system_cab.md` in AC5 test.
Artifact: `artifacts/ac2_assets.txt`.

## AC3 — Whitelist and size caps enforced — PASS
`tests/test_changedocs.py::test_collect_diffs_whitelist_and_caps` and
`test_ported_constants_unchanged`. A whitelisted file is included (not truncated),
an oversized `.dfa` is truncated to `MAX_FILE_DIFF_BYTES`, a `.csv` is skipped
(non-code), an empty `.sh` is skipped (empty), and files past the total cap are
skipped (total diff size cap). Constants confirmed:
`MAX_TOTAL_DIFF_BYTES==200_000`, `MAX_FILE_DIFF_BYTES==60_000`,
`CODE_EXTENSIONS=={dfa,sh,pl,py,procs,control,ovl,ins,lis,300}`.
Artifact: `artifacts/ac3-9_changedocs_tests.txt`.

## AC4 — Header parsing — PASS
`tests/test_changedocs.py::test_parse_header_extracts_fields`. Description,
Parallel ID, and the numbered Files list (stopping at the `*` line) are extracted.

## AC5 — Dry-run/preview makes no API call and returns a cost estimate — PASS
`test_dry_run_returns_estimate_no_api` (unit) and
`test_preview_route_no_api_no_usage_log` (route). The preview route monkeypatches
`context.fetch` and sets `draft.draft_cab` to raise if called; it is never invoked.
Response carries `model_id`, `estimated_input_tokens`, `max_output_tokens`,
`estimated_cost_usd`, and `no_api_call=True`. `usage.log` is NOT created on preview.

## AC6 — Generate returns download references for requested docs — PASS
`test_generate_cab_only` (CAB only) and `test_generate_cab_ptf_qa` (CAB+PTF+QA),
both with `context.fetch` and `draft.draft_cab` mocked (no ssh, no API). Exactly the
requested `.docx` files are written to the output dir; CAB is always produced; each
produced file returns one `/api/changedocs/download?...` reference.

## AC7 — PTF and QA render deterministically (no API) — PASS
`test_render_ptf_fills_fields` (JIRA, hours, parallel id, and the
`Total # File(s) Transferred: 2` line present) and `test_render_qa_clones_l_rows`
(L1..L3 cloned and filled). No Claude API involved.

## AC8 — Download route works and is path-safe — PASS
`test_download_streams_and_rejects_traversal`. Streams the `.docx` with content type
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`; re-download
of the same file succeeds; missing file → 404; `../../etc/passwd` → 403/404
(traversal rejected via the `startswith(out_root)` guard mirroring `/api/file`).

## AC9 — Guardrails intact in code — PASS
`test_draft_guardrails_present_in_source` asserts on `inspect.getsource(draft_cab)`:
key read only from `ANTHROPIC_API_KEY`, no `tools` passed, system block uses
`cache_control`/`ephemeral`, `max_tokens=MAX_OUTPUT_TOKENS`, exactly two
`resp = _call(` sites (one bounded call + one repair retry), and `_log_usage(` is
called. `test_default_model_and_output_cap` confirms `DEFAULT_MODEL=="sonnet"`,
`MAX_OUTPUT_TOKENS==4000`. `test_fetch_rejects_short_prid` confirms a short PRID
raises `ContextError`; routes map `ContextError` → `HTTPException(400, ...)`.

## AC10 — pyproject web extra updated and resolvable — PASS
`pyproject.toml [project.optional-dependencies].web` contains `fastapi`, `uvicorn`,
`python-docx`, `anthropic`.
```
uv run python -c "import docx, anthropic; print('deps ok')"  ->  deps ok
```
(docx 1.2.0, anthropic 0.106.0 resolved in the test env.)
Artifacts: `artifacts/ac10_deps.txt`, `artifacts/ac10_pyproject.txt`.

## AC11 — Existing web tests pass + routes registered — PASS
`uv run pytest tests/test_web_server.py -q` → `10 passed`.
Routes `/api/changedocs/preview`, `/api/changedocs/generate`,
`/api/changedocs/download` are registered on `server.app`.
Artifacts: `artifacts/ac11_routes.txt`, `artifacts/ac11-12_web_tests.txt`.

## AC12 — UI panel present and valid — PASS
`index.html` adds a `data-step="changedocs"` nav entry; `app.js` adds the
`case 'changedocs'` render dispatch and `renderChangeDocsStep` with PRID input,
model select (sonnet default), Preview button, PTF/QA checkboxes, PTF JIRA/hours/
live-date fields, optional QA job/items, and a download-links result area.
`node --check lsa/web/static/app.js` exits 0; `test_app_js_parses_when_node_is_available`
passes.
Artifact: `artifacts/ac12_node_check.txt`.

## AC13 — Whole suite green — PASS
`uv run pytest -q` → `170 passed`.
Artifact: `artifacts/ac13_full_suite.txt`.
