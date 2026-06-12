# Evidence — changedocs-fixes-v2

Date: 2026-06-12

## AC1 — remote cleanup non-fatal: PASS
- `lsa/changedocs/context.py`: remote command ends with
  `rm -rf "$F" >/dev/null 2>&1 || true` — an NFS "Directory not empty" on
  cleanup can no longer fail the lookup (the reported 400 case).
- Test: `test_remote_cleanup_failure_is_non_fatal` captures the actual remote
  command string and asserts the tolerant form.

## AC2 — CAB/PTF/QA independent: PASS
- `ChangeDocsGenerateRequest.cab: bool = True`; `cab=False` skips the draft
  call entirely (no API key needed), CAB file not rendered; ticket_id resolved
  from request/context. Zero documents selected → 400.
- UI: CAB checkbox enabled (default checked); inline `cd-docs-error` when
  generating with nothing selected (no request made).
- Tests: `test_generate_without_cab_renders_ptf_qa_only` (draft_cab
  monkeypatched to AssertionError — proves it is not called),
  `test_generate_requires_at_least_one_document`.

## AC3 — multi-provider: PASS
- `draft.py`: `provider="anthropic"|"openai"`; openai path =
  OpenAI-compatible `POST {base_url}/chat/completions` via httpx, same
  single-call + one JSON-repair retry, errors → DraftError, usage accumulated
  and logged as `model=openai:<id>`; base_url from
  `changedocs.openai_base_url` (default api.openai.com/v1).
- Anthropic path untouched (guardrail source test still passes); Opus pricing
  corrected to the current sheet (5/25 $/MTok, was 15/75).
- `dry_run(provider=...)`; unknown model → `estimated_cost_usd: None`
  (UI already renders "—" for non-numeric).
- Key management per provider: `~/.lsa/anthropic_key` / `~/.lsa/openai_key`
  (0600), env fallbacks; `sk-ant-` format check anthropic-only; unknown
  provider → 400.
- UI: provider select; free-text model id for openai; provider-aware key block.
- `httpx>=0.27.0` declared in `[web]` extras and dev group (was transitive).
- Tests: openai success+usage log, HTTP 401 → DraftError, network error →
  DraftError, `_resolve_model` defaults, dry_run None cost, per-provider key
  endpoints (separate files, bogus provider 400).

## AC4 — output folder out of snaproot: PASS
- `_changedocs_out_root`: saved setting (`~/.lsa/changedocs_outdir`) →
  `changedocs.out_root` config → `~/.lsa/changedocs`. snaproot-based default
  removed (it polluted the Snapshot table).
- `GET/POST /api/changedocs/outdir`: returns/saves absolute path (expanduser,
  mkdir); relative path → 400; returns Windows path via `_to_windows_path`.
- `/api/snapshots` filters via `_looks_like_snapshot` (LSA db or any of
  procs/master/control/insert/docdef) — a `changedocs` dir in snaproot no
  longer appears.
- UI: Output folder field with Save + Windows-path hint; generate result shows
  `out_dir_win` with click-to-copy.
- Tests: `test_out_root_resolution_order`,
  `test_outdir_endpoints_save_and_validate`,
  `test_snapshots_listing_skips_non_snapshot_dirs`.

## AC5 — tests/checks: PASS
- Full suite: **212 passed** (was 200; +12 new) — `raw/pytest_full.txt`.
- `node --check app.js`: OK — `raw/node_check.txt`.

## Notes / not verified
- Existing generated docs under the old `snaproot/changedocs` location are not
  migrated; they simply stop appearing as a fake snapshot. The user can pick a
  Windows folder (e.g. `/mnt/c/Users/<user>/Documents/ChangeDocs`) via the new
  Output folder field.
- Live ssh/Anthropic/OpenAI calls not exercised (mocked per repo convention).
