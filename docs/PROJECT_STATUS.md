# LSA Project Status

**Last Updated:** 2026-01-28

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

### Tests
- [x] 106 tests passing
- [x] test_wrapper_noise.py
- [x] test_message_codes.py
- [x] test_external_signals.py
- [x] test_context_pack.py
- [x] test_import_codes.py
- [x] test_incidents.py

---

## In Progress

### DFA Search Fix
- **Issue:** `.dfa` files were marked as metadata-only, content not indexed
- **Fix:** Added `.dfa` to TEXT_EXTENSIONS in config.py
- **Status:** Code changed, waiting for verification
- **To verify:**
  ```bash
  rm -rf "$SNAP/.lsa"
  lsa scan "$SNAP"
  lsa search "$SNAP" "PRINT_ACCOUNTS"  # Should find DFA files now
  ```

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

### Other Ideas
- [ ] `lsa export` — export context pack to file (for automation)
- [ ] Improved case_cards: store full chunk content for better search
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
| Log parser | `tools/lsa/lsa/parsers/log_parser.py` |
| PDF parser | `tools/lsa/lsa/parsers/pdf_parser.py` |
| Tests | `tools/lsa/tests/` |

---

## How to Continue

1. Read this file to restore context
2. Check "In Progress" section for pending work
3. Check "Planned" for next features
4. Run tests: `cd tools/lsa && uv run pytest`
