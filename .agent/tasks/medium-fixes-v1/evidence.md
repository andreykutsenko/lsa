# Evidence — medium-fixes-v1

Date: 2026-06-11

## AC1 — changedocs errors -> 400, not raw 500: PASS
- `lsa/changedocs/context.py` `fetch()`: `subprocess.TimeoutExpired` and `OSError`
  wrapped into `ContextError`.
- `lsa/changedocs/draft.py` `draft_cab()`: `anthropic.APIError` -> `DraftError`;
  double malformed JSON -> `DraftError("Model returned malformed JSON twice...")`.
- Tests: `test_fetch_converts_ssh_timeout_to_context_error`,
  `test_draft_cab_converts_api_error`,
  `test_draft_cab_raises_draft_error_on_double_malformed_json`.

## AC2 — usage accumulated across repair retry: PASS
- `draft_cab` tracks usage per call via `_track()`; `usage.log` written in
  `finally` (spend logged even when the draft ultimately fails).
- Tests: `test_draft_cab_accumulates_usage_across_repair_retry` (250/50 = sum of
  both calls), double-malformed test also asserts summed usage (220/30).

## AC3 — snapshot SSE stream survives rsync timeout: PASS
- rsync loop in `_snapshot_create_stream` wraps `subprocess.run` in
  `except TimeoutExpired/OSError`, records into `rsync_errors`, continues.
- Test: `test_snapshot_stream_survives_rsync_timeout` — all 5 jobs raise
  TimeoutExpired, final event still has `done: true` and 5 rsync_errors.
- Workspace stream unchanged (already `except Exception` around its rsync).

## AC4 — FTS failures reported: PASS
- `_search_fts` catches only `sqlite3.OperationalError`, prints
  `Warning: FTS query ... failed: <msg>`, returns `[]`.
- Test: `test_search_fts_warns_and_returns_empty_on_operational_error`.

## AC5 — SQLite batching + rollback: PASS
- `get_connection`: commit on success, rollback on `BaseException`, then close.
- `insert_artifact/proc/node/edge/message_code`: `commit: bool = True` keyword;
  hot loops (scan, builder, import-codes) pass `commit=False` with one commit at
  the end of each loop.
- Tests: `tests/test_db_transactions.py` (3 tests: batched commit on success,
  rollback on exception, default-commit unchanged).

## AC6 — plan-state local snapshots: PASS
- `/api/plan` assigns `_last_intent, _last_candidates` in one tuple assignment.
- `plan_mermaid`, `generate_prompt`, workspace create, `_current_scope_paths`
  copy globals to locals at entry; all bounds checks and element accesses use
  the locals. Verified by grep: remaining `_last_*` reads are only the initial
  local captures.

## AC7 — cross-origin mutation guard: PASS
- `_origin_allowed` helper + `@app.middleware("http")` rejecting
  POST/PUT/PATCH/DELETE with non-local Origin (403). No-Origin and GET
  unaffected; opaque `null` origin rejected.
- Tests: `test_origin_allowed_accepts_local_and_absent`,
  `test_origin_allowed_rejects_foreign_and_opaque`.

## AC8 — redactor keeps timestamps: PASS
- `_is_timestamp_like` validates 8/14-digit YYYYMMDD[HHMMSS] (year 1970–2099,
  month/day/hour/minute/second ranges); ACCT replacement is now a callable.
- Tests: `tests/test_redactor.py` (4 tests: accounts still redacted, dates and
  timestamps preserved, invalid date-likes redacted, email/SSN unaffected).

## AC9 — tests: PASS
- Full suite: **200 passed** (was 185; +15 new) — `raw/pytest_full.txt`.
- Targeted files: **53 passed** — `raw/pytest_targeted.txt`.

## Not verified
- Live `lsa serve` middleware behavior over real HTTP (helper unit-tested; no
  httpx/TestClient dependency in the project).
- Real Anthropic API / real ssh behavior (mocked per test conventions).
