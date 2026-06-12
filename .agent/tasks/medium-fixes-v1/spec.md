# Task: medium-fixes-v1 — Medium-severity fixes from project review

Frozen: 2026-06-11

## Scope

Medium findings from the 2026-06-11 review. Minimal diffs; no refactors beyond
what each AC requires. No frontend changes. No dependency changes.

## Acceptance criteria

### AC1 — changedocs errors surface as 400, not raw 500
- `lsa/changedocs/context.py` `fetch()`: `subprocess.TimeoutExpired` and
  `OSError` from the ssh call are converted to `ContextError` with a readable
  message.
- `lsa/changedocs/draft.py` `draft_cab()`: any `anthropic.APIError` (auth,
  rate limit, network, timeout) is converted to `DraftError`; a second
  malformed-JSON response (after the repair retry) raises `DraftError`, not a
  raw `json.JSONDecodeError`.

### AC2 — usage log accumulates tokens across the repair retry
- In `draft_cab`, when the JSON-repair second call happens, `usage.log`
  records the sum of input/output tokens of both calls, not only the second.

### AC3 — snapshot-create SSE stream survives subprocess timeouts
- In `lsa/web/server.py` `_snapshot_create_stream`, a `TimeoutExpired` /
  `OSError` from an rsync job is recorded in `rsync_errors` and the stream
  continues; the final `done: true` event is always emitted.
- (Workspace stream already wraps its rsync in `except Exception` — no change.)

### AC4 — FTS search failures are reported, not silenced
- `lsa/cli.py` `_search_fts`: only `sqlite3.OperationalError` is caught; it
  prints a yellow warning with the SQLite message and returns `[]`. Other
  exceptions propagate.

### AC5 — SQLite write batching and rollback
- `get_connection` commits on successful exit and rolls back on exception
  (then closes).
- `insert_artifact`, `insert_proc`, `insert_node`, `insert_edge`,
  `insert_message_code` accept keyword `commit: bool = True`; default
  behavior unchanged for all other callers.
- Hot loops pass `commit=False` with a single commit at the end:
  scan loop in `lsa/cli.py`, `build_graph_from_procs` in
  `lsa/graph/builder.py` (final commit already exists), import-codes loop in
  `lsa/cli.py`.

### AC6 — plan-state reads take a local snapshot
- In `lsa/web/server.py`, `/api/plan` assigns `_last_intent, _last_candidates`
  in a single tuple assignment; every handler that reads them copies the
  globals into locals once at entry and uses only the locals afterwards
  (bounds check and element access see the same list).

### AC7 — cross-origin mutating requests are rejected
- An HTTP middleware in `lsa/web/server.py` rejects POST/PUT/PATCH/DELETE
  requests whose `Origin` header is present and whose origin host is not
  `localhost`, `127.0.0.1`, or `::1` (403). Requests without an `Origin`
  header (curl, CLI) and all GETs are unaffected.
- Logic lives in a pure helper `_origin_allowed(origin: str | None) -> bool`
  so it is unit-testable without an HTTP client.

### AC8 — redactor keeps date/timestamp tokens
- `lsa/utils/redactor.py`: the 8–16 digit account pattern no longer replaces
  tokens that parse as plausible timestamps: 8-digit `YYYYMMDD` or 14-digit
  `YYYYMMDDHHMMSS` with year 1970–2099, month 01–12, day 01–31 (and
  HH<24/MM<60/SS<60 for the 14-digit form). All other 8–16 digit runs are
  still redacted. Trade-off accepted: an account number that happens to be a
  valid date-like string will no longer be redacted.

### AC9 — tests
- New tests cover: ContextError on ssh timeout; DraftError on anthropic API
  error and on double malformed JSON; summed usage on retry; snapshot SSE
  stream completing with `done` + populated `rsync_errors` when rsync raises
  TimeoutExpired; `_search_fts` returning `[]` with a warning on a broken FTS
  query; `commit=False` + rollback behavior of `get_connection`;
  `_origin_allowed` accept/reject cases; redactor timestamp preservation and
  continued account redaction.
- Full suite passes (185 tests before this task).

## Constraints
- No new dependencies (tests may use `anthropic`/`httpx` already present in
  the dev environment).
- No changes to `lsa/web/static/**`.
- Idempotent behavior of scan/import commands must be preserved.
