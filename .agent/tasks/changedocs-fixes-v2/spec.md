# Task: changedocs-fixes-v2 — ssh cleanup bug, optional docs, multi-provider, output folder

Frozen: 2026-06-12

## Scope

Four user-reported items for the Change Docs feature plus one pricing correction.
Minimal diffs; follow existing patterns. Public-repo policy applies: no internal
hostnames/paths/client names in code or tests.

## Acceptance criteria

### AC1 — remote cleanup failure no longer fails the lookup
- In `lsa/changedocs/context.py`, the remote command's final `rm -rf "$F"` is
  made non-fatal (`>/dev/null 2>&1 || true`): an NFS "Directory not empty"
  during cleanup must not turn a successful diff fetch into a 400.
- A test asserts the remote command contains the tolerant cleanup form.

### AC2 — CAB / PTF / QA selectable independently
- `ChangeDocsGenerateRequest` gains `cab: bool = True`.
- When `cab` is false: no LLM call is made, no API key is required, and
  `ticket_id` resolves from `req.ticket_id` or the parallel-run context.
- Selecting no documents at all returns 400.
- UI: the CAB checkbox is enabled (default checked); PTF/QA work without CAB;
  Generate with nothing selected shows an error and makes no request.

### AC3 — pluggable LLM provider (Anthropic + OpenAI-compatible)
- `draft.py` accepts `provider: "anthropic" | "openai"`.
  - anthropic: existing SDK path unchanged (Sonnet default, Opus option;
    PRICE_PER_MTOK corrected to current sheet: sonnet 3/15, opus 5/25).
  - openai: OpenAI-compatible `POST {base_url}/chat/completions` via httpx
    (covers OpenAI, OpenRouter, DeepSeek, Ollama, etc.); base_url from
    `changedocs.openai_base_url` in ~/.lsa/config.yaml (default
    `https://api.openai.com/v1`); model is a free-form string from the request;
    same single-call + one JSON-repair-retry semantics; HTTP/network errors →
    `DraftError`; usage (prompt/completion tokens) accumulated and logged with
    a provider/model tag.
- `dry_run` accepts provider/model; unknown pricing → `estimated_cost_usd: None`
  (UI renders "—").
- Key management is per provider: `/api/changedocs/key` endpoints take
  `provider` (`anthropic` default | `openai`); keys stored in
  `~/.lsa/anthropic_key` / `~/.lsa/openai_key` (0600); env fallbacks
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`; the `sk-ant-` format check applies
  only to the anthropic provider.
- UI: provider select; anthropic shows the existing model select, openai shows
  a free-text model input; key block reflects the selected provider.
- `httpx` declared explicitly in `[web]` extras and dev group (it is already a
  transitive dependency of anthropic — lock change is minimal).

### AC4 — output folder out of snaproot, configurable, Windows-friendly
- `_changedocs_out_root` resolution order: saved setting file
  `~/.lsa/changedocs_outdir` → `changedocs.out_root` in config →
  `~/.lsa/changedocs`. The old `snaproot/changedocs` default is removed.
- New endpoints: `GET /api/changedocs/outdir` (current value + windows path),
  `POST /api/changedocs/outdir` (validate absolute path after expanduser,
  create directory, persist to the setting file).
- `/api/snapshots` lists only directories that look like snapshots (contain at
  least one of: `procs`, `master`, `control`, `insert`, `docdef` subdirs, or an
  LSA database). A `changedocs` (or any other non-snapshot) directory inside
  snaproot no longer appears in the Snapshot table.
- UI: Change Docs form shows an editable "Output folder" with Save; the
  generate result shows the output dir as a Windows path (via
  `_to_windows_path`) with copy affordance. Per-ticket subfolder behavior kept.

### AC5 — tests and checks
- New/updated tests cover: AC1 command form; cab=False generates PTF/QA only
  with no draft call and no key; no-docs 400; openai provider path (httpx
  mocked: success, API error → DraftError, usage logged); per-provider key
  endpoints; out_root resolution order; snapshots listing filters non-snapshot
  dirs; outdir endpoints (save/validate).
- Full pytest suite passes; `node --check app.js` passes.

## Constraints
- No new heavyweight dependencies (httpx only, already present transitively).
- Anthropic SDK path stays on the official SDK (no shims).
- Existing generated docs under the old location are not migrated automatically
  (documented in evidence; user can set the output folder in the UI).
