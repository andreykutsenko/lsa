# Task: critical-fixes-v1 — Critical security/packaging fixes

Frozen: 2026-06-11

## Scope

Four critical findings from the project review. Minimal diffs only; no refactors,
no behavior changes beyond the listed acceptance criteria.

## Acceptance criteria

### AC1 — Path containment uses `Path.is_relative_to`, not string `startswith`
- `lsa/web/server.py` `delete_snapshot` (~line 260), `read_file` (~line 560),
  `changedocs_download` (~line 1558) must reject paths outside the respective root
  using `Path.is_relative_to()` on resolved paths.
- Sibling-prefix paths (e.g. `<root>_evil/...`, which pass the old `startswith`
  check) must be rejected with 403.
- `DELETE /api/snapshot` must additionally reject deleting the snaproot directory
  itself (`snap == root`).

### AC2 — User-controlled path components are sanitized
- A single helper in `lsa/web/server.py` reduces a user-supplied string to a safe
  single path component: only `[A-Za-z0-9._-]`, other chars replaced with `_`,
  leading dots stripped; empty or dot/underscore-only results raise HTTP 400.
- `POST /api/snapshot/create`: `req.name` must be rejected with 400 if it is not
  already a safe component (explicit reject, no silent rename).
- `POST /api/workspace/create`: `req.ticket` / `req.title` are sanitized before
  becoming part of the workspace directory name (silent normalization is OK —
  these are free-text fields).
- `POST /api/changedocs/generate`: the resolved `ticket_id` is sanitized before
  it is used as a directory/file-name component.

### AC3 — changedocs data files included in wheel build
- `pyproject.toml` `[tool.hatch.build].include` covers
  `lsa/changedocs/prompts/*.md` and `lsa/changedocs/templates/*.docx`.

### AC4 — No personal hardcoded path in `lsa/cli.py`
- The `<local-dir>/...` entry is removed from `DEFAULT_PDF_PATHS`
  (constant stays, default empty — tests patch it).
- `_find_pdf_path` additionally consults optional `codes_pdf` key from
  `~/.lsa/config.yaml` (via `load_user_config`), expanded with `expanduser`,
  between the snapshot-local lookup and `DEFAULT_PDF_PATHS`.
- `import-codes` docstring and the "PDF not found" error output reflect the new
  lookup order.

### AC5 — Tests
- New tests cover: sibling-prefix rejection for `read_file` and
  `changedocs_download`; snaproot-itself deletion rejection; invalid snapshot
  name rejection in `create_snapshot`; `ticket_id` sanitization in
  `changedocs_generate`; sanitizer helper edge cases (empty, dots-only,
  separators).
- Existing suite (177 tests) still passes; `lsa.cli` auto-detection tests in
  `tests/test_import_codes.py` keep passing unmodified.

## Constraints
- No new dependencies.
- No changes to frontend files (out of scope for this task).
- Python >= 3.11 (so `Path.is_relative_to` is available).
