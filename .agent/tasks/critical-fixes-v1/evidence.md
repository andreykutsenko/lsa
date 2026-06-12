# Evidence — critical-fixes-v1

Date: 2026-06-11

## AC1 — `is_relative_to` containment checks: PASS
- `lsa/web/server.py`: all three checks converted; `grep -n "startswith(str(" lsa/web/server.py` returns nothing (raw/pytest_full.txt context; grep exit 1).
  - `delete_snapshot`: rejects `snap == snaproot` and non-descendants with 403.
  - `read_file`: `file_path.is_relative_to(snapshot.resolve())`.
  - `changedocs_download`: `file_path.is_relative_to(out_root)`.
- Tests: `test_read_file_rejects_sibling_prefix_dir`,
  `test_delete_snapshot_rejects_snaproot_and_siblings`,
  `test_download_rejects_sibling_prefix_dir` — all pass.

## AC2 — Component sanitization: PASS
- Helper `_sanitize_component` added in `lsa/web/server.py` (charset
  `[A-Za-z0-9._-]`, unsafe → `_`, leading dots stripped, empty/dot-underscore-only
  → HTTP 400).
- `create_snapshot`: explicit 400 reject when `req.name` is not already safe.
- `workspace create`: `req.ticket` / `req.title` sanitized into `ws_name`.
- `changedocs_generate`: resolved `ticket_id` sanitized before path use.
- Tests: `test_sanitize_component_*` (3), `test_create_snapshot_rejects_unsafe_name`,
  `test_generate_sanitizes_ticket_id` — all pass.

## AC3 — Wheel includes changedocs data files: PASS
- `pyproject.toml` include extended with `lsa/changedocs/prompts/*.md` and
  `lsa/changedocs/templates/*.docx`.
- Verified by real build: `uv build --wheel` → `raw/wheel_contents.txt` shows
  `system_cab.md`, `ptf_template.docx`, `qa_template.docx` inside the wheel.

## AC4 — Hardcoded personal path removed: PASS
- `grep -rn "<username>" lsa/ --include="*.py"` → no matches.
- `DEFAULT_PDF_PATHS` now empty list (kept for test patchability;
  `tests/test_import_codes.py` passes unmodified).
- `_find_pdf_path` consults `codes_pdf` from `~/.lsa/config.yaml`
  (via new `_configured_pdf_path`); docstring and error output updated.

## AC5 — Tests: PASS
- Full suite: **185 passed** (was 177; +8 new) — `raw/pytest_full.txt`.
- Targeted web/changedocs: **38 passed** — `raw/pytest_targeted.txt`.

## Not verified
- Live `lsa serve` manual exploitation attempts (covered by unit tests on the
  route coroutines instead).
