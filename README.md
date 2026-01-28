# LSA — Legacy Script Archaeologist

Local CLI tool for analyzing legacy RHS/Papyrus script snapshots. Produces execution graphs, matches logs to processes, and generates "context packs" — structured summaries that can be pasted into an IDE or LLM for deeper investigation.

## Why This Exists

Debugging legacy batch systems (Papyrus, DocExec, shell scripts) typically involves:
1. Searching through thousands of files for execution paths
2. Decoding cryptic error codes (PPCS, PPDE, AFPR)
3. Identifying whether failures are code bugs or external config issues (InfoTrac, Message Manager)
4. Remembering past solutions for similar problems

LSA automates this preprocessing step:
- Scans snapshot directories and builds a searchable execution graph
- Parses trace logs and matches them to probable failing processes
- Detects external configuration signals (not code bugs) vs actual script failures
- Generates a single copy-paste "context pack" with hypotheses and related files
- Tracks analyzed incidents and similar past cases

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────────────────┐
│  RHS Snapshot   │────▶│  lsa scan  ──▶  SQLite DB (.lsa/lsa.sqlite)     │
│  (no logs)      │     │                 - artifacts, procs, nodes, edges │
└─────────────────┘     │                 - FTS index for search           │
                        │                                                  │
┌─────────────────┐     │  lsa import-codes  ──▶  message_codes table     │
│  PDF (codes KB) │────▶│                         (PPCS, PPDE, AFPR...)    │
└─────────────────┘     │                                                  │
                        │  lsa import-histories ──▶ case_cards table       │
┌─────────────────┐────▶│                          (past debugging cases)  │
│  histories/*.md │     │                                                  │
└─────────────────┘     └──────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────┐     ┌──────────────────────────────────────────────────┐
│  Single Log     │────▶│  lsa explain --log <file>                        │
│  (trace/error)  │     │    - Match log to graph node (proc)              │
└─────────────────┘     │    - Extract external signals (InfoTrac, API)    │
                        │    - Generate hypotheses (ranked)                │
                        │    - Find similar past cases                     │
                        │    - Persist to incidents table                  │
                        │    - Output: Context Pack (stdout)               │
                        └──────────────────────────────────────────────────┘
```

## Repository Layout

```
lsa_project/                    # This repo (Git tracked)
├── tools/lsa/                  # Python package
│   ├── lsa/
│   │   ├── cli.py             # Typer CLI entrypoint
│   │   ├── db/schema.py       # SQLite tables
│   │   ├── rules/external_signals.yaml  # Detection rules
│   │   └── ...
│   ├── tests/
│   └── pyproject.toml
├── docs/
└── README.md

rhs_snapshot_project/           # NOT in Git (see .gitignore)
├── rhs_snapshot_20260127_*/   # Actual snapshots
│   ├── procs/
│   ├── master/
│   ├── control/
│   ├── docdef/
│   └── .lsa/lsa.sqlite        # Per-snapshot DB
├── refs/
│   ├── papyrus/*.pdf          # Message codes PDF
│   └── histories/             # Shared debugging histories
└── logs_inbox/                # Drop logs here for analysis
```

## Installation

**Prerequisites:** Python 3.11+, WSL recommended.

```bash
# Clone and enter repo
cd /mnt/c/Users/<you>/code
git clone <repo-url> lsa_project
cd lsa_project

# Create venv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./tools/lsa

# Verify
lsa --version
```

### Dev Setup (with tests)

```bash
# Using uv (recommended)
cd tools/lsa
uv sync --dev
uv run pytest

# Or pip
pip install -e ./tools/lsa[dev]
pytest tools/lsa/tests/
```

## Snapshot Workflow

### Creating a Snapshot (without logs)

Snapshots capture RHS system state at a point in time. **Do not copy logs into the snapshot** — logs are analyzed separately.

Recommended helper script (`~/bin/mk_snap_and_scan.sh`):

```bash
#!/bin/bash
# Usage: mk_snap_and_scan.sh <source_host>
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SNAP_DIR="/mnt/c/Users/$USER/code/rhs_snapshot_project/rhs_snapshot_${TIMESTAMP}"

# rsync from source (exclude logs, tmp, etc.)
rsync -avz --exclude='*.log' --exclude='tmp/' \
    "${1}:/home/master/" "${SNAP_DIR}/master/"
rsync -avz "${1}:/home/procs/" "${SNAP_DIR}/procs/"
# ... other directories

# Index immediately
source /mnt/c/Users/$USER/code/lsa_project/.venv/bin/activate
lsa scan "$SNAP_DIR"
lsa import-codes "$SNAP_DIR"  # Auto-detects PDF
lsa import-histories "$SNAP_DIR"  # Auto-detects histories dir
```

### Typical Usage

```bash
SNAP=/mnt/c/Users/akutsenko/code/rhs_snapshot_project/rhs_snapshot_20260127_120000

# 1. Scan snapshot (builds graph, indexes files)
lsa scan "$SNAP"

# 2. Import knowledge base (message codes from PDF)
lsa import-codes "$SNAP"
# Auto-detects: <SNAP>/refs/papyrus/*.pdf or global default

# 3. Import debugging histories (past cases)
lsa import-histories "$SNAP"
# Auto-detects: <SNAP>/histories/, <SNAP>/refs/histories/,
#               <SNAP_PARENT>/histories/, <SNAP_PARENT>/refs/histories/

# 4. Check statistics
lsa stats "$SNAP"

# 5. Analyze a log file
lsa explain "$SNAP" --log /path/to/trace.log

# 6. View incident history
lsa incidents "$SNAP"
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `lsa scan <SNAP>` | Index snapshot, build execution graph |
| `lsa stats <SNAP>` | Show artifact/graph/KB statistics |
| `lsa search <SNAP> "<query>"` | Full-text search in artifacts |
| `lsa explain <SNAP> --log <FILE>` | Analyze log, generate context pack |
| `lsa import-codes <SNAP> [--pdf PATH]` | Import message codes from PDF |
| `lsa import-histories <SNAP> [--path DIR] [--glob PATTERN]` | Import case cards |
| `lsa incidents <SNAP> [--limit N]` | List analyzed incidents |

### `lsa explain` Options

```bash
lsa explain "$SNAP" --log trace.log          # Standard analysis
lsa explain "$SNAP" --log trace.log --debug  # Show matching candidates
lsa explain "$SNAP" --log trace.log --no-persist  # Don't save to incidents
lsa explain "$SNAP" --log trace.log --proc bkfnds1  # Force specific proc
```

## Using Logs: The "Drop a Single Log" Approach

Instead of copying all logs into snapshots, keep logs separate:

```
rhs_snapshot_project/
└── logs_inbox/           # Drop logs here
    ├── issue_20260127_bkfnds1.log
    └── customer_complaint_trace.log
```

Then analyze:
```bash
lsa explain "$SNAP" --log ../logs_inbox/issue_20260127_bkfnds1.log
```

This keeps snapshots clean and reusable across multiple log analyses.

## Incidents & Case Cards

### Incidents Table

Every `lsa explain` run persists analysis results:

| Column | Description |
|--------|-------------|
| `log_path` | Analyzed log file path (unique key) |
| `top_node_key` | Best matching proc/script |
| `confidence` | Match confidence (0.0-1.0) |
| `hypotheses_json` | Top failure hypotheses |
| `similar_cases_json` | Matching case card IDs |
| `created_at` / `updated_at` | Timestamps |

Re-analyzing the same log updates the existing incident.

```bash
# List recent incidents
lsa incidents "$SNAP" --limit 10

# Disable persistence
lsa explain "$SNAP" --log file.log --no-persist
```

### Case Cards (from Histories)

Case cards are extracted from debugging history files (Cursor/SpecStory sessions):

| Column | Description |
|--------|-------------|
| `source_path` | Origin file |
| `content_hash` | For idempotent re-imports |
| `signals_json` | Error codes/patterns found |
| `root_cause` | Extracted root cause (if any) |
| `fix_summary` | Extracted fix (if any) |
| `tags_json` | Auto-tags (oracle, perl, shell, etc.) |

During `lsa explain`, similar cases are matched by error signals and shown in the context pack.

## External Signals Detection

LSA detects external configuration issues (not code bugs) using rules in `lsa/rules/external_signals.yaml`:

| Signal ID | Category | Example Pattern |
|-----------|----------|-----------------|
| `INFOTRAC_MISSING_MESSAGE_ID` | CONFIG | `No data found from message_id: 197131 in infotrac db` |
| `API_SUCCESS_FALSE_JSON` | EXTERNAL_API | `"success": false` |
| `HTTP_ERROR_STATUS` | EXTERNAL_API | `HTTP/1.1 503` |
| `CONNECTION_REFUSED` | NETWORK | `Connection refused` |
| `AUTH_FAILURE` | AUTH | `401 Unauthorized` |

These signals are:
- Shown in context pack section "EXTERNAL CONFIG SIGNALS"
- Prioritized over generic wrapper noise in hypotheses
- Useful for distinguishing "fix the code" vs "fix the config"

## Integration with IDE/LLM Workflows

LSA is a **preprocessing step** before using Claude Code, Cursor, or other AI tools:

1. Run `lsa explain` to generate context pack
2. Copy the output (or pipe to clipboard)
3. Paste into IDE/LLM with your question

The context pack provides:
- Most likely failing node with file path
- Execution chain (upstream/downstream dependencies)
- Error evidence with decoded message codes
- External signals (config vs code issues)
- Ranked hypotheses with confirmation steps
- Similar past cases with known fixes
- Relevant files to open

This saves significant context-gathering time and focuses the AI on the actual problem.

## Troubleshooting

### `lsa` command shows old behavior

The `lsa` entrypoint might be cached or point to wrong venv.

```bash
# Check which lsa is being used
which lsa
head -n 1 $(which lsa)  # Check shebang

# Reliable alternative: run as module
python -m lsa.cli explain "$SNAP" --log file.log

# Reinstall to fix
pip install -e ./tools/lsa
```

### When do I need `pip install -e` again?

- After modifying `pyproject.toml` (dependencies, entry points)
- After pulling changes that modify package structure
- NOT needed for code changes in existing files (editable install handles this)

### Python/python3 alias issues

```bash
# If python3 works but python doesn't
alias python=python3

# Or use explicit path
/usr/bin/python3 -m lsa.cli --help
```

### Database errors after schema changes

If you get SQLite errors after updating LSA, the schema may have changed:

```bash
# Delete old DB and rescan
rm -rf "$SNAP/.lsa"
lsa scan "$SNAP"
lsa import-codes "$SNAP"
lsa import-histories "$SNAP"
```

### import-histories can't find histories

Check the auto-detection order:
1. `<snapshot>/histories/`
2. `<snapshot>/refs/histories/`
3. `<snapshot_parent>/histories/`
4. `<snapshot_parent>/refs/histories/`

Or specify explicitly:
```bash
lsa import-histories "$SNAP" --path /path/to/histories
```

## License

Internal use only. Not for distribution.

---

*Generated for LSA v0.1.0 — Legacy Script Archaeologist*
