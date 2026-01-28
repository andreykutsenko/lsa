# LSA Technical Architecture

This document provides a detailed technical overview of how LSA works internally.

## Problem Statement

When a batch process fails in a legacy system (Papyrus/DocExec), developers spend significant time on **context gathering**:

1. **Find what failed** — hundreds of .procs files, scripts, docdefs
2. **Decode error codes** — PPCS1037F, PPDE0042E — what do they mean?
3. **Understand call chains** — proc calls script, script reads control file, control references docdef...
4. **Distinguish bug from config** — is it a code bug or just InfoTrac misconfiguration?
5. **Remember past solutions** — "we had this same issue six months ago..."

Only after this can actual debugging begin. **This context gathering takes 30-70% of debugging time.**

## Solution: Deterministic Preprocessing + Knowledge Accumulation

LSA automates context gathering through:
- **Indexing**: Build searchable graph from snapshot
- **Knowledge Base**: Import error code definitions and past cases
- **Analysis**: Match logs to graph, extract signals, generate hypotheses
- **Persistence**: Track incidents and similar cases over time

## Phase 1: Indexing (`lsa scan`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            lsa scan <SNAPSHOT>                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SNAPSHOT DIRECTORIES                                                       │
│  ├── procs/*.procs      ─────▶  Parse: extract RUNS, READS, CALLS          │
│  ├── master/scripts/*   ─────▶  Index: sha256, text_content                │
│  ├── control/*          ─────▶  Index + link to docdefs                    │
│  ├── insert/*           ─────▶  Index                                       │
│  └── docdef/*.dfa       ─────▶  Index                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SQLite DB: <SNAPSHOT>/.lsa/lsa.sqlite                                      │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │  artifacts  │    │    nodes    │    │    edges    │                     │
│  ├─────────────┤    ├─────────────┤    ├─────────────┤                     │
│  │ path        │    │ type=proc   │    │ src → dst   │                     │
│  │ kind        │    │ key         │───▶│ rel_type:   │                     │
│  │ text_content│    │ display_name│    │  RUNS       │                     │
│  │ sha256      │    │ canonical_  │    │  READS      │                     │
│  └─────────────┘    │   path      │    │  CALLS      │                     │
│         │           └─────────────┘    └─────────────┘                     │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │artifacts_fts│  ◀── FTS5 full-text search index                          │
│  └─────────────┘                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**What gets built:**
- **artifacts** — all files with metadata and content (for search)
- **nodes** — graph vertices (proc, script, control, docdef)
- **edges** — graph edges with relationship type (RUNS, READS, CALLS)
- **artifacts_fts** — FTS5 index for full-text search

## Phase 2: Knowledge Base Enrichment

### Message Codes (`lsa import-codes`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        lsa import-codes <SNAPSHOT>                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
    PDF: Papyrus_DocExec_           │
         message_codes.pdf           ▼
    ┌──────────────────┐    ┌─────────────────────────────────┐
    │ PPCS1037F        │    │  message_codes table            │
    │ Reason: Document │───▶│  ┌─────────────────────────────┐│
    │   not found      │    │  │ code: PPCS1037F            ││
    │ Solution: Check  │    │  │ severity: F (Fatal)        ││
    │   docdef path... │    │  │ body: "Document definition ││
    └──────────────────┘    │  │   not found. Check..."     ││
                            │  └─────────────────────────────┘│
                            └─────────────────────────────────┘
```

### Case Cards (`lsa import-histories`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     lsa import-histories <SNAPSHOT>                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
    histories/*.md                   │
    (Cursor/debugging sessions)      ▼
    ┌──────────────────┐    ┌─────────────────────────────────┐
    │ ## Issue: ORA-   │    │  case_cards table               │
    │ 12345 in bkfnds  │───▶│  ┌─────────────────────────────┐│
    │ Root cause:      │    │  │ signals: ["ORA-12345"]     ││
    │   missing index  │    │  │ root_cause: "missing index"││
    │ Fix: CREATE INDEX│    │  │ fix_summary: "CREATE INDEX"││
    └──────────────────┘    │  │ related_files: [...]       ││
                            │  └─────────────────────────────┘│
                            └─────────────────────────────────┘
```

## Phase 3: Analysis (`lsa explain`)

### Step 1: Parse Log

```
trace.log ──▶ LogAnalysis {
                prefix_tokens: ["bkfnds1"]      ◀── $PREFIX=bkfnds1
                script_paths: ["/home/master/scripts/bkfn_gen.sh"]
                error_codes: ["PPCS1037F", "PPDE0042E"]
                docdef_tokens: ["BKFNDS11"]
              }
```

### Step 2: Match to Graph Node

```
LogAnalysis.prefix_tokens ──┐
LogAnalysis.script_paths  ──┼──▶  SCORING ALGORITHM  ──▶  Best Match
LogAnalysis.docdef_tokens ──┘         │
                                      │
┌─────────────────────────────────────┴────────────────────────────────┐
│  SELECT * FROM nodes WHERE type='proc'                               │
│                                                                      │
│  Score each node:                                                    │
│    +50 pts: prefix_token matches node.key (bkfnds1 → proc:bkfnds1)  │
│    +30 pts: script_path in node's RUNS edges                        │
│    +20 pts: docdef_token in node's downstream                       │
│    +10 pts: log filename similarity                                  │
│                                                                      │
│  Result: proc:bkfnds1 (confidence: 87%)                             │
└──────────────────────────────────────────────────────────────────────┘
```

### Step 3: Get Execution Chain (Graph Traversal)

```
SELECT * FROM edges WHERE src = node_id OR dst = node_id

┌────────────┐      RUNS       ┌────────────┐      READS     ┌─────────┐
│ proc:      │ ───────────────▶│ script:    │ ──────────────▶│ control:│
│ bkfnds1    │                 │ bkfn_gen.sh│                │ bkfn.ctl│
└────────────┘                 └────────────┘                └─────────┘
      │                                                           │
      │ RUNS                                               REFERS_TO
      ▼                                                           ▼
┌────────────┐                                             ┌─────────┐
│ script:    │                                             │ docdef: │
│ bkfn_load  │                                             │ BKFNDS11│
└────────────┘                                             └─────────┘
```

### Step 4: Extract External Signals (Rules Engine)

```
FOR EACH rule IN external_signals.yaml:
    FOR EACH line IN log_text:
        IF regex.match(rule.pattern, line):
            signals.append(ExternalSignal{
                id: rule.id,
                severity: rule.severity,
                captures: regex.groups()   ◀── e.g., message_id=197131
            })

Example match:
┌──────────────────────────────────────────────────────────────────────┐
│ Rule: INFOTRAC_MISSING_MESSAGE_ID                                    │
│ Pattern: "No data found from message_id:\s*(?P<message_id>\d+)"     │
│ Match: "No data found from message_id: 197131 in infotrac db"       │
│ Captures: {message_id: "197131"}                                     │
│ Severity: F (Fatal) → This is CONFIG issue, not code bug            │
└──────────────────────────────────────────────────────────────────────┘
```

### Step 5: Decode Error Codes (KB Lookup)

```
SELECT * FROM message_codes WHERE code IN ('PPCS1037F', 'PPDE0042E')

┌─────────────────────────────────────────────────────────────────────┐
│ PPCS1037F [Fatal]                                                    │
│   Title: Document definition not found                               │
│   Body: The specified document definition file could not be located. │
│         Check the DOCDEF path in the control file...                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 6: Generate Hypotheses (Ranking)

```
Hypothesis sources (by priority):

1. External Signals (F severity)     ──▶  HIGHEST PRIORITY
   "InfoTrac message_id 197131 not found — CONFIG issue"

2. Fatal error codes (xxxF)          ──▶  HIGH
   "PPCS1037F: Document definition not found"

3. Error codes (xxxE)                ──▶  MEDIUM
   "PPDE0042E: Processing error"

4. Wrapper noise (demoted)           ──▶  LOW (FYI only)
   "ERROR: Generator returns non-zero" — wrapper, not root cause
```

### Step 7: Find Similar Cases (Similarity Search)

```
SELECT * FROM case_cards WHERE signals_json IS NOT NULL

FOR EACH case_card:
    overlap = current_signals ∩ card.signals
    score = |overlap| / max(|current|, |card|)
    IF score > 0.3: similar_cases.append(card)

Result:
┌─────────────────────────────────────────────────────────────────────┐
│ Case #42 (match: 75%)                                                │
│   Signals: ["PPCS1037F", "ORA-12345"]                               │
│   Root cause: "DOCDEF path wrong after migration"                    │
│   Fix: "Updated control file path from /old/ to /new/"              │
└─────────────────────────────────────────────────────────────────────┘
```

### Step 8: Persist Incident + Output Context Pack

```
INSERT OR REPLACE INTO incidents (log_path, top_node_key, confidence,
                                  hypotheses_json, similar_cases_json)

OUTPUT (stdout):
════════════════════════════════════════════════════════════════
LSA CONTEXT PACK
════════════════════════════════════════════════════════════════
1. MOST LIKELY FAILING NODE: proc:bkfnds1 (87%)
2. EXECUTION CHAIN: bkfnds1 → bkfn_gen.sh → bkfn.ctl → BKFNDS11
3. EVIDENCE: PPCS1037F, PPDE0042E
3b. DECODED CODES: PPCS1037F = "Document definition not found"
3d. EXTERNAL SIGNALS: INFOTRAC_MISSING_MESSAGE_ID (message_id=197131)
4. HYPOTHESES: 1) InfoTrac config  2) DOCDEF path  3) ...
5. FILES TO OPEN: procs/bkfnds1.procs, master/scripts/bkfn_gen.sh
7. SIMILAR CASES: Case #42 (75% match)
════════════════════════════════════════════════════════════════
```

## Database Schema (ER Diagram)

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    artifacts    │       │      nodes      │       │      edges      │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id PK           │       │ id PK           │◀──────│ src FK          │
│ kind            │       │ type            │       │ dst FK          │
│ path UNIQUE     │       │ key UNIQUE      │◀──────│ rel_type        │
│ text_content    │       │ display_name    │       │ confidence      │
│ sha256          │       │ canonical_path  │       │ evidence_json   │
│ mtime, size     │       │ confidence      │       └─────────────────┘
└─────────────────┘       └─────────────────┘
        │                         │
        │ FTS5                    │
        ▼                         │
┌─────────────────┐               │
│  artifacts_fts  │               │
└─────────────────┘               │
                                  │
┌─────────────────┐       ┌───────┴─────────┐       ┌─────────────────┐
│  message_codes  │       │    incidents    │       │   case_cards    │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ code PK         │       │ id PK           │       │ id PK           │
│ severity        │       │ log_path UNIQUE │       │ source_path     │
│ title           │       │ top_node_id FK──│───────│ chunk_id        │
│ body            │       │ top_node_key    │       │ content_hash    │
│ source_path     │       │ confidence      │       │ signals_json    │
└─────────────────┘       │ hypotheses_json │       │ root_cause      │
                          │ similar_cases   │───────│ fix_summary     │
                          │ created_at      │       │ tags_json       │
                          └─────────────────┘       └─────────────────┘
```

## Key Algorithms

| Component | Algorithm | Complexity |
|-----------|----------|-----------|
| Graph matching | Weighted scoring by tokens from log | O(nodes × tokens) |
| External signals | Regex scan against YAML rules | O(lines × rules) |
| Similar cases | Jaccard similarity on signals | O(cases × signals) |
| Full-text search | SQLite FTS5 | O(log n) |
| Code lookup | Hash lookup in message_codes | O(1) |

## Why This Is More Effective Than Direct AI

```
WITHOUT LSA:                          WITH LSA:
─────────────────────────────────     ─────────────────────────────────
User → AI                             User → LSA → AI
                                              │
Log (10KB raw text)                   Context Pack (2KB structured)
    │                                         │
    ▼                                         ▼
AI does:                              AI receives ready:
- Parses log itself (poorly)          ✓ Parsed & structured
- Guesses about PPCS1037F             ✓ Decoded: "Doc not found"
- Doesn't know about graph            ✓ Graph: bkfnds1→script→docdef
- Doesn't know about InfoTrac         ✓ Signal: CONFIG issue
- Doesn't remember past cases         ✓ Similar: Case #42

Result:                               Result:
5-15 clarification iterations         1-3 iterations
```

**LSA = deterministic preprocessing + knowledge accumulation**, providing AI with structured context instead of raw text.

## Improvement Metrics

| Metric | Without LSA | With LSA |
|--------|-------------|----------|
| Time to first hypothesis | 15-30 min | 2-3 min |
| Iterations with AI | 5-15 | 1-3 |
| Solving same problem again | From scratch | From case_cards |
| Bug vs config distinction | Manual | Automatic |

## Business Value

1. **Faster debugging** — less time on context gathering
2. **Knowledge retention** — incidents and case_cards don't get lost
3. **Better AI responses** — structured context → accurate answers
4. **Easier onboarding** — new developers get context immediately, no need to ask colleagues

## One-Sentence Summary

> LSA transforms an opaque error log into structured context with hypotheses and history, reducing legacy system debugging time and improving AI-assisted development quality.
