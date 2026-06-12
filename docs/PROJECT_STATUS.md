# LSA Project Status

**Last Updated:** 2026-06-11

Use this file to restore context when starting a new Claude Code session.

---

## Project Overview

LSA (Legacy Script Archaeologist) is a CLI tool for analyzing Papyrus/DocExec batch system snapshots. It builds an execution graph, indexes files, and generates "context packs" for debugging.

**Repository:** https://github.com/andreykutsenko/lsa
**Location:** `~/code/lsa`
**Snapshots:** `$SNAPROOT/` (separate, not in git)

---

## Done (2026-06-12 session, task: changedocs-fixes-v2)

- [x] ssh context fetch no longer fails when remote cleanup hits NFS lock
      files (`rm` failure is non-fatal)
- [x] CAB / PTF / QA selectable independently; PTF/QA-only needs no API key
- [x] Pluggable LLM provider: Anthropic (default) or any OpenAI-compatible
      endpoint (`changedocs.openai_base_url`); per-provider key storage
      (`~/.lsa/anthropic_key` / `~/.lsa/openai_key`)
- [x] Opus price estimate corrected (5/25 $/MTok)
- [x] Output folder configurable from the UI (Windows path friendly on WSL),
      default `~/.lsa/changedocs` — no longer inside snaproot
- [x] Snapshot table no longer shows non-snapshot directories (the old
      `changedocs` output dir polluted it)
- [x] 212 tests passing (+12)

---

## Done (v0.4.0 — 2026-06-11 session)

All tasks below went through the repo-task-proof-loop workflow: frozen spec,
implementation, evidence, and an independent fresh-session verification.
Artifacts live in `.agent/tasks/<task>/` (spec.md, evidence.md, verdict.json).

### Change Docs generator (`lsa/changedocs/`, task: changedocs-web)
- [x] CAB Questionnaire drafted via a single bounded Claude API call
      (Sonnet default, Opus optional; concise/detailed styles; one
      JSON-repair retry; prompt caching for the system prompt)
- [x] PTF and QA Checklist rendered deterministically from bundled
      `.docx` templates (no API)
- [x] Context fetched over ssh by PRID; only whitelisted code-extension
      diffs, per-file and total size caps
- [x] Dry-run Preview: token estimate + worst-case cost, zero API calls
- [x] Web UI tab: PRID input, model/detail selectors, API key management
      (`~/.lsa/anthropic_key`, chmod 600, env fallback), PTF/QA toggles,
      extra-context with load-from-file, `.docx` downloads
- [x] Token usage logged to `~/.lsa/changedocs/usage.log` (accumulated
      across retries, logged even on failure)

### Security & correctness fixes (task: critical-fixes-v1)
- [x] Path containment via `Path.is_relative_to` (string-prefix bypass via
      sibling dirs closed); deleting snaproot itself rejected
- [x] User-supplied path components sanitized (snapshot name, workspace
      ticket/title, changedocs ticket_id)
- [x] changedocs prompts/templates included in the wheel build
- [x] Hardcoded personal PDF path removed; `codes_pdf` read from
      `~/.lsa/config.yaml`

### Robustness fixes (task: medium-fixes-v1)
- [x] changedocs errors surface as HTTP 400 (ssh timeout → ContextError,
      anthropic.APIError / double-malformed JSON → DraftError)
- [x] Snapshot-create SSE stream survives rsync timeouts (done event
      always arrives)
- [x] Cross-origin POST/PUT/PATCH/DELETE rejected unless Origin is
      localhost (CSRF guard)
- [x] SQLite: get_connection commits on success / rolls back on error;
      scan, graph build, and import-codes batch writes (one commit per
      loop instead of one per row)
- [x] FTS search failures print a warning instead of silent "no results"
- [x] Redactor preserves date/timestamp tokens (YYYYMMDD[HHMMSS]) instead
      of mangling them into [ACCT]
- [x] Plan handlers take a local snapshot of shared plan state

### Web UX fixes (task: ux-fixes-v1)
- [x] Amber progress bar + warn callout when rsync/scan/copy errors occur
- [x] Search filter changes re-run the query immediately
- [x] Form inputs survive navigation and re-renders (Scope Builder,
      Change Docs, Prompt textarea)
- [x] Client-side PRID validation with inline field error
- [x] "Copy raw" button in file preview modal (strips line numbers)
- [x] Merged Captured/Freshness into one column (absolute date in tooltip)
- [x] Busy state on snapshot "Use" button
- [x] escapeHtml escapes quotes (attribute-injection hardening)
- [x] Search Preview button maps to the correct result across
      Knowledge/Files sections

### Test suite
- [x] 200 tests passing (was 177 before this session); new coverage:
      changedocs engine/routes, path safety, origin guard, SSE resilience,
      DB transactions, redactor, FTS error reporting

---

## Done (earlier sessions)

### Core Commands
- [x] `lsa scan` — index snapshot, build execution graph from .procs
- [x] `lsa stats` — show artifact/graph/KB statistics
- [x] `lsa search` — full-text search in artifacts (FTS5)
- [x] `lsa explain` — analyze log, generate context pack; `--prompt [--lang ru]` outputs AI-ready prompt
- [x] `lsa import-codes` — import Papyrus/DocExec codes from PDF
- [x] `lsa import-histories` — import case cards from debugging sessions
- [x] `lsa incidents` — list analyzed log incidents
- [x] `lsa plan` — bundle planner: find proc, collect files, rank candidates

### Features
- [x] Execution graph: nodes (proc, script) + edges (RUNS); other file types resolved via artifact lookup
- [x] Log-to-proc matching with confidence scoring
- [x] External signals detection (YAML rules engine)
  - InfoTrac missing message_id
  - API success=false
  - HTTP errors, connection refused, auth failures
- [x] Wrapper noise de-noising ("ERROR: Generator returns non-zero")
- [x] Hypotheses ranking (external signals > fatal codes > errors > wrapper noise)
- [x] Message codes KB (PDF parsing with definition vs cross-reference distinction)
- [x] Case cards from histories (Cursor/SpecStory sessions)
- [x] Similar cases matching (Jaccard similarity on error signals)
- [x] Incidents persistence (upsert by log_path)
- [x] import-histories auto-detection (snapshot + parent directories)
- [x] Upsert logic with content_hash for idempotent re-imports
- [x] Bundle planner: CID/jobid/title → ranked proc candidates with file bundles
- [x] DFA letter-number filtering: Letter 14 excludes DL015 even if in .procs
- [x] Plan output modes: default (winner + compact), `--all`, `--json`, `--cursor`
- [x] i18n for plan output: `--lang en` (default) / `--lang ru`
- [x] explain output cleanup: sections 3b/3c/3d conditional, section 6 removed, section 7 deduplicated by source
- [x] explain `--prompt [--lang en|ru]`: AI-ready prompt with instruction + context pack + log snippet + source files
- [x] plan --deep: AI prompt for full Papyrus flow analysis (saved to file in .lsa/ai_prompts/)
- [x] plan: snapshot age warning (>7d INFO, >30d WARN)
- [x] plan: secondary scripts discovery — CID+JobID wildcard match + call graph from RUNS scripts
- [x] Onboarding: setup.sh (SSH key auth), lsa_config.sh, lsa-snap.sh, lsa-workspace.sh
- [x] explain --prompt: simplified — removed log snippet, instruction says "open FILES TO OPEN"
- [x] `lsa serve` — web UI for interactive snapshot analysis (FastAPI + vanilla JS)

### Web UI (`lsa serve`)
- [x] Snapshot management: list, select, create (rsync from RHS), delete with confirmation
- [x] SSE progress bars for snapshot creation and workspace creation
- [x] Operator-console V1: Overview is centered on **Current scope** instead of index statistics
- [x] Bundle: plan generation, candidate selection, Current scope summary, file preview, Mermaid graph
- [x] Current scope actions: Open files, Create workspace, Copy file list, Generate prompt, Open diagram
- [x] Bundle action deduplication: one clear entry point per function, duplicate workspace/diagram/prompt surfaces removed
- [x] Prompt: generated from the selected Current scope with two scenarios only:
  - Incident analysis
  - Change request analysis
- [x] Search is operator-oriented:
  - Space: All / Files / Knowledge
  - Mode: Path / Content
  - Scope: Current scope / Whole snapshot
  - Kind filters for artifact types
- [x] Knowledge search includes Papyrus/PDF message codes in Search, including `space=all` with `scope=current`
- [x] Snapshot creation supports optional enrichments via progressive disclosure:
  - control / prox / insert / related files
  - Papyrus PDF
  - incidents folder
  - research/log files folder
- [x] Workspace creation: snap/SSH copy modes, pull script generation
- [x] Diagnostics keeps secondary counters out of the main operator surface
- [x] Light theme (OpenClaw-inspired: Inter + JetBrains Mono, teal accent)
- [x] WSL support: Windows Explorer paths (`\\wsl.localhost\...`) with copy-to-clipboard
- [x] Live smoke-tested flow after server restart/reload:
  - snapshot select
  - bundle/scope selection
  - open file
  - create workspace
  - copy file list
  - generate prompt
  - open diagram
  - search Papyrus/PDF message codes

### Tests
- [x] Core Python test suite remains in place
- [x] Web regression tests cover:
  - `server.py` bootstrap and API behavior
  - `app.js` syntax parse check (`node --check`, when Node is available)
  - Search regression: `space=all` + `scope=current` must keep knowledge hits
- [x] test_wrapper_noise.py
- [x] test_message_codes.py
- [x] test_external_signals.py
- [x] test_context_pack.py
- [x] test_import_codes.py
- [x] test_incidents.py
- [x] test_planner.py (27 tests: scoring, DFA filtering, JSON/cursor output, i18n, CID+JobID wildcard, call graph)

---

## `lsa plan` Design Notes

**What it does:** Given CID / jobid / free-text title, finds matching proc(s) and bundles related files:
1. `.procs` file
2. Scripts (via RUNS edges)
3. Inserts (via artifact lookup from procs parsed_json)
4. Control files (job-family prefix match + letter_number filter)
5. DFA/docdef files (from control `*_format_dfa` + procs DFA tokens)
6. Helper scripts (master/{proc_name}_* pattern)
7. Secondary scripts (CID+JobID wildcard match)
8. Call graph discovery (scripts called by RUNS scripts)

**Scoring:** exact key (+50), title phrase match (+30), CID prefix (+15),
has scripts/inserts/control (+10 each), has DFA (+5), keywords (+2 each).

**Key design decisions:**
- Control attachment uses job-family prefix (`wccudl` for `wccudla`), not bare CID — prevents noise
- DFA letter filtering: when title has "Letter 14", only DFA codes ending with "014" are kept (DL015 excluded)
- DFA resolution: two sources — `*_format_dfa="..."` from controls + DFA tokens from `.procs` parsed_json
- Title phrase match: strips CID + "Letter NN", searches remainder in parsed_json (+30 bonus)
- Job family prefix: `wccudla→wccudl`, `wccuds1→wccuds`

**Output modes:**
- Default: winner details + compact one-liner for other candidates
- `--all`: full details for all candidates (legacy)
- `--json`: machine-readable JSON (schema: snapshot_root, intent, selected_bundle, other_candidates_summary)
- `--cursor`: Markdown prompt for Cursor IDE with embedded JSON
- `--mermaid`: Mermaid graph + ASCII call tree
- `--deep`: AI prompt for full Papyrus flow analysis (DFA per job_sel, Mermaid)
- `--lang en|ru`: i18n for all text output (JSON keys always English)

**Verify on real snapshot:**
```bash
SNAP="$SNAPROOT/rhs_snapshot_20260127_170100"
uv run lsa plan "$SNAP" --cid WCCU --title "WCCU Letter 14" --debug
uv run lsa plan "$SNAP" --cid WCCU --title "Letter 14" --json
uv run lsa plan "$SNAP" --cid WCCU --title "Letter 14" --cursor --lang ru
```

---

## `lsa explain --prompt` Design Notes

**What it does:** Generates a ready-to-paste AI prompt from a log analysis.

**Output structure:**
1. Instruction block (role + task description + output format) — in English or Russian
2. Full context pack (sections 1–7, filtered) — FILES TO OPEN includes analyzed log path

**Flags:**
- `--prompt` — activate AI prompt mode (default: plain context pack)
- `--lang en|ru` — instruction language (default: `en`)

**Verify on real snapshot:**
```bash
SNAP="$SNAPROOT/rhs_snapshot_20260127_170100"
LOG="/d/daily/<job>/<job>.log"
uv run lsa explain "$SNAP" "$LOG" --prompt --lang ru
```

**Source:** `lsa/output/prompt_pack.py`

---

## Completed (previously "In Progress")

### DFA Search Fix (committed in 4f2072f)
- Added `.dfa` to TEXT_EXTENSIONS in config.py
- DFA file content now indexed by FTS

---

## Planned (Next Session)

### From the 2026-06-11 review (graded backlog)

Functional improvements grounded in the current code (see review findings in
`.agent/tasks/*/spec.md` for context):

- [ ] **Richer graph edges (HIGH)** — `.procs` parsing already extracts
      `print_files`, `file_setup`, `all_paths`, but only `shell_script`
      becomes a RUNS edge. Adding USES/READS edges would improve
      `lsa plan` bundle discovery.
- [ ] **Similarity normalization (MEDIUM)** — group signal codes by family
      (`ORA-*`, `PPCS*`), wildcard numeric parts; unify the metric
      (`find_similar_cases` uses max-denominator, `compute_signal_similarity`
      uses Jaccard — they disagree today).
- [ ] **`lsa scan --clean` (MEDIUM)** — procs deleted from the snapshot
      currently stay in the graph forever; add a drop-and-rebuild flag.
- [ ] **FTS over procs parsed_json (LOW)** — planner keyword fallback scans
      all procs in Python (O(N) per query).
- [ ] **Cache `rglob` lookups in paths.py (LOW)** — unmapped-path resolution
      rescans the snapshot directory per path per proc during scan.
- [ ] **Web: persist plan state per session (LOW)** — current scope is
      lost on server restart/page reload (known V1 limitation).

### `lsa cases` Command (HIGH PRIORITY)
Search through past debugging cases proactively:
```bash
lsa cases "$SNAP" "inline insert"      # Search in title, root_cause, fix_summary
lsa cases "$SNAP" --file "bkfnds"      # Search by related_files
lsa cases "$SNAP" --tag oracle         # Filter by tags
lsa cases "$SNAP" --signal "ORA-"      # Search by error signals
lsa cases "$SNAP" --id 42              # Show details of case #42
```

**Needs:**
- FTS index on case_cards (title + root_cause + fix_summary)
- New CLI command with search options
- Tests

### Incidents as Quality Journal (MEDIUM)
Use incidents table as a log of analyses and quality benchmark over time:
- [ ] Track analysis quality metrics (confidence, hypothesis accuracy)
- [ ] Compare LSA output across snapshots/time — regression detection
- [ ] `lsa incidents --stats` — summary stats (avg confidence, top error codes)
- [ ] `lsa incidents --export` — export for external dashboards

### Case Cards Similarity Enhancement (MEDIUM)
Strengthen case_cards as a solutions knowledge base:
- [ ] Better similarity search (beyond Jaccard on error signals)
- [ ] TF-IDF or embedding-based matching on root_cause + fix_summary
- [ ] Auto-suggest similar cases during `lsa explain` (before user asks)
- [ ] Link incidents ↔ case_cards (track which case resolved which incident)
- [ ] Improved case_cards: store full chunk content for better search

### Other Ideas
- [ ] `lsa export` — export context pack to file (for automation)
- [ ] `lsa plan --lang zh` — add more languages as needed
- [ ] Web UI V2:
  - stronger persistence across restart/reload for selected snapshot/scope
  - richer knowledge navigation beyond Files / Knowledge / All
  - dark mode only if it stays nearly free

---

## Known Issues

1. **Old `lsa` entrypoint** — if `lsa` shows old behavior, re-sync:
   ```bash
   uv sync
   ```

2. **Schema changes** — after updating LSA, may need to re-scan:
   ```bash
   rm -rf "$SNAP/.lsa"
   lsa scan "$SNAP"
   lsa import-codes "$SNAP"
   lsa import-histories "$SNAP"
   ```

3. **Current scope is not persisted across restart/reload** — after restarting `lsa serve` or reloading the page, reselect the snapshot and run `Find scope` again. This is a known V1 limitation, not a backend failure.

---

## File Locations

| What | Path |
|------|------|
| CLI entrypoint | `lsa/cli.py` |
| Database schema | `lsa/db/schema.py` |
| External signals rules | `lsa/rules/external_signals.yaml` |
| Config (TEXT_EXTENSIONS) | `lsa/config.py` |
| Context pack generator | `lsa/output/context_pack.py` |
| Hypotheses generator | `lsa/analysis/hypotheses.py` |
| Plan/bundle logic | `lsa/analysis/planner.py` |
| Log parser | `lsa/parsers/log_parser.py` |
| PDF parser | `lsa/parsers/pdf_parser.py` |
| Tests | `tests/` |
| Web UI backend | `lsa/web/server.py` |
| Web UI frontend | `lsa/web/static/` (app.js, style.css, index.html) |
| Web UI launcher | `lsa/web/launcher.py` |
| User config loader | `lsa/config.py` → `load_user_config()` |
| Change Docs: ssh context | `lsa/changedocs/context.py` |
| Change Docs: LLM draft | `lsa/changedocs/draft.py` |
| Change Docs: .docx render | `lsa/changedocs/render.py`, `generate_cab.py` |
| Change Docs: templates/prompt | `lsa/changedocs/templates/`, `prompts/system_cab.md` |
| Task artifacts (proof loop) | `.agent/tasks/<task>/` (spec, evidence, verdict) |

---

## Workflow Scripts

Shell scripts in `scripts/` for day-to-day work with LSA. Config via `~/.lsa/config.yaml` (created by `setup.sh`); env vars override as fallback.

| Script | Purpose |
|--------|---------|
| `scripts/setup.sh` | One-time interactive setup: UV install, `uv sync`, SSH key config (`~/.ssh/config`), `~/.lsa/config.yaml` |
| `scripts/lsa_config.sh` | Config loader — sourced by other scripts, parses `~/.lsa/config.yaml` |
| `scripts/lsa-snap.sh` | Full snapshot: rsync + `lsa scan` + optional import-codes (PDF) + import-histories |
| `scripts/lsa-workspace.sh` | Full workspace: optional ticket ID, snap/SSH copy mode (`--ssh-copy`/`--rhs-copy`), `mermaid/` dir, notes, pull script |

**Quick start:**
```bash
./scripts/setup.sh                                                 # 1. one-time setup
./scripts/lsa-snap.sh                                              # 2. create snapshot
source .venv/bin/activate                                          # 3. activate LSA
lsa plan $SNAP --title mocume2                                     # 4. view bundle
lsa plan $SNAP --title mocume2 --deep                              # 5. AI prompt (saved to file)
./scripts/lsa-workspace.sh --snap $SNAP --title mocume2            # 6. copy files for CR
lsa serve $SNAP                                                    # 7. web UI (alternative to CLI)
```

---

## Development Workflow

Substantial features/refactors/bug fixes go through the **repo-task-proof-loop**
(see `CLAUDE.md` / `AGENTS.md`):

1. Freeze `.agent/tasks/<TASK_ID>/spec.md` with acceptance criteria (AC1, AC2, ...)
2. Implement against the frozen criteria
3. Produce `evidence.md` / `evidence.json` + raw command outputs
4. Independent fresh-session verification writes `verdict.json`
   (and `problems.md` on FAIL → smallest safe fix → reverify)

Config lives in `~/.lsa/config.yaml`: `snaproot`, `workroot`, `rhs_host`,
`rhs_user`, optional `codes_pdf`, plus changedocs remote overrides.

---

## How to Continue

1. Read this file to restore context
2. Check "Planned" for next features (review backlog is graded by priority)
3. Run tests: `uv run pytest` (expect 200 passing)
4. Task history with specs/evidence: `.agent/tasks/`
