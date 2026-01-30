# LSA Project Status

**Last Updated:** 2026-01-30

Use this file to restore context when starting a new Claude Code session.

---

## Project Overview

LSA (Legacy Script Archaeologist) is a CLI tool for analyzing Papyrus/DocExec batch system snapshots. It builds an execution graph, indexes files, and generates "context packs" for debugging.

**Repository:** https://github.com/andreykutsenko/lsa
**Location:** `/mnt/c/Users/akutsenko/code/lsa_project/tools/lsa`
**Snapshots:** `/mnt/c/Users/akutsenko/code/rhs_snapshot_project/` (separate, not in git)

---

## Done (v0.1.0)

### Core Commands
- [x] `lsa scan` — index snapshot, build execution graph from .procs
- [x] `lsa stats` — show artifact/graph/KB statistics
- [x] `lsa search` — full-text search in artifacts (FTS5)
- [x] `lsa explain` — analyze log, generate context pack
- [x] `lsa import-codes` — import Papyrus/DocExec codes from PDF
- [x] `lsa import-histories` — import case cards from debugging sessions
- [x] `lsa incidents` — list analyzed log incidents
- [x] `lsa plan` — bundle planner: find proc, collect files, rank candidates

### Features
- [x] Execution graph: nodes (proc, script, control, docdef) + edges (RUNS, READS, CALLS)
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

### Tests
- [x] 130 tests passing
- [x] test_wrapper_noise.py
- [x] test_message_codes.py
- [x] test_external_signals.py
- [x] test_context_pack.py
- [x] test_import_codes.py
- [x] test_incidents.py
- [x] test_planner.py (25 tests: scoring, DFA filtering, JSON/cursor output, i18n)

---

## `lsa plan` Design Notes

**What it does:** Given CID / jobid / free-text title, finds matching proc(s) and bundles related files:
1. `.procs` file
2. Scripts (via RUNS edges)
3. Inserts (via READS edges)
4. Control files (job-family prefix match + letter_number filter)
5. DFA/docdef files (from control `*_format_dfa` + procs DFA tokens)

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
- `--lang en|ru`: i18n for all text output (JSON keys always English)

**Verify on real snapshot:**
```bash
SNAP="/mnt/c/Users/akutsenko/code/rhs_snapshot_project/rhs_snapshot_20260127_170100"
uv run lsa plan "$SNAP" --cid WCCU --title "WCCU Letter 14 - Business Rate/Payment Change Notice" --debug
uv run lsa plan "$SNAP" --cid WCCU --title "Letter 14" --json
uv run lsa plan "$SNAP" --cid WCCU --title "Letter 14" --cursor --lang ru
```

---

## Completed (previously "In Progress")

### DFA Search Fix (committed in 4f2072f)
- Added `.dfa` to TEXT_EXTENSIONS in config.py
- DFA file content now indexed by FTS

---

## Planned (Next Session)

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
- [ ] `lsa bundle` — copy bundled files to temp dir for quick access
- [ ] `lsa export` — export context pack to file (for automation)
- [ ] `lsa plan --lang zh` — add more languages as needed
- [ ] Web UI (optional, low priority)

---

## Known Issues

1. **Old `lsa` entrypoint** — if `lsa` shows old behavior, run:
   ```bash
   pip install -e ./tools/lsa
   ```

2. **Schema changes** — after updating LSA, may need to re-scan:
   ```bash
   rm -rf "$SNAP/.lsa"
   lsa scan "$SNAP"
   lsa import-codes "$SNAP"
   lsa import-histories "$SNAP"
   ```

---

## File Locations

| What | Path |
|------|------|
| CLI entrypoint | `tools/lsa/lsa/cli.py` |
| Database schema | `tools/lsa/lsa/db/schema.py` |
| External signals rules | `tools/lsa/lsa/rules/external_signals.yaml` |
| Config (TEXT_EXTENSIONS) | `tools/lsa/lsa/config.py` |
| Context pack generator | `tools/lsa/lsa/output/context_pack.py` |
| Hypotheses generator | `tools/lsa/lsa/analysis/hypotheses.py` |
| Plan/bundle logic | `tools/lsa/lsa/analysis/planner.py` |
| Log parser | `tools/lsa/lsa/parsers/log_parser.py` |
| PDF parser | `tools/lsa/lsa/parsers/pdf_parser.py` |
| Tests | `tools/lsa/tests/` |

---

## How to Continue

1. Read this file to restore context
2. Check "In Progress" section for pending work
3. Check "Planned" for next features
4. Run tests: `cd tools/lsa && uv run pytest`
