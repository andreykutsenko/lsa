"""SQLite schema definitions for LSA."""

SCHEMA = """
-- Artifacts: files from snapshot
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,  -- 'procs', 'script', 'control', 'insert', 'docdef', 'history'
    path TEXT NOT NULL UNIQUE,  -- snapshot-relative path
    original_path TEXT,  -- original unix path if different
    sha256 TEXT,  -- nullable, computed only for text files
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    text_content TEXT  -- nullable, only for small UTF-8 files
);

-- Parsed .procs files
CREATE TABLE IF NOT EXISTS procs (
    id INTEGER PRIMARY KEY,
    proc_name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    sha256 TEXT
);

-- Graph nodes
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,  -- 'proc', 'script', 'control', 'insert', 'docdef', 'log'
    key TEXT NOT NULL UNIQUE,  -- canonical identifier
    display_name TEXT NOT NULL,
    canonical_path TEXT,  -- snapshot-relative path
    original_path TEXT,  -- unix path from source
    confidence REAL DEFAULT 1.0
);

-- Graph edges
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY,
    src INTEGER NOT NULL REFERENCES nodes(id),
    dst INTEGER NOT NULL REFERENCES nodes(id),
    rel_type TEXT NOT NULL,  -- 'RUNS', 'READS', 'CALLS', 'REFERS_TO'
    confidence REAL DEFAULT 1.0,
    evidence_json TEXT  -- {file, line_no, line_text}
);

-- Incidents (analyzed logs)
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY,
    log_path TEXT NOT NULL UNIQUE,  -- unique constraint for upsert
    parsed_json TEXT NOT NULL,
    top_node_id INTEGER REFERENCES nodes(id),
    top_node_key TEXT,  -- denormalized for quick lookup
    confidence REAL,
    hypotheses_json TEXT,  -- top hypotheses
    similar_cases_json TEXT,  -- similar case IDs
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- Case cards from histories
CREATE TABLE IF NOT EXISTS case_cards (
    id INTEGER PRIMARY KEY,
    source_path TEXT,
    chunk_id INTEGER,  -- position in source file
    content_hash TEXT,  -- SHA256 of chunk content for deduplication
    title TEXT,
    signals_json TEXT,  -- error codes, patterns
    root_cause TEXT,
    fix_summary TEXT,
    verify_commands_json TEXT,
    related_files_json TEXT,
    tags_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE(source_path, chunk_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_path ON artifacts(path);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_key ON nodes(key);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(rel_type);

-- FTS virtual table for text search
CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
    path,
    text_content,
    content=artifacts,
    content_rowid=id
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS artifacts_ai AFTER INSERT ON artifacts
WHEN NEW.text_content IS NOT NULL
BEGIN
    INSERT INTO artifacts_fts(rowid, path, text_content)
    VALUES (NEW.id, NEW.path, NEW.text_content);
END;

CREATE TRIGGER IF NOT EXISTS artifacts_ad AFTER DELETE ON artifacts
WHEN OLD.text_content IS NOT NULL
BEGIN
    INSERT INTO artifacts_fts(artifacts_fts, rowid, path, text_content)
    VALUES ('delete', OLD.id, OLD.path, OLD.text_content);
END;

CREATE TRIGGER IF NOT EXISTS artifacts_au AFTER UPDATE ON artifacts
WHEN OLD.text_content IS NOT NULL OR NEW.text_content IS NOT NULL
BEGIN
    INSERT INTO artifacts_fts(artifacts_fts, rowid, path, text_content)
    VALUES ('delete', OLD.id, OLD.path, COALESCE(OLD.text_content, ''));
    INSERT INTO artifacts_fts(rowid, path, text_content)
    VALUES (NEW.id, NEW.path, COALESCE(NEW.text_content, ''));
END;

-- Message codes from Papyrus/DocExec knowledge base
CREATE TABLE IF NOT EXISTS message_codes (
    code TEXT NOT NULL,
    severity TEXT NOT NULL,  -- I=Info, W=Warning, E=Error, F=Fatal
    title TEXT,  -- nullable, may not be reliably extractable
    body TEXT NOT NULL,  -- description/reason/solution text
    source_path TEXT NOT NULL,  -- path to source PDF
    created_at TEXT NOT NULL,
    PRIMARY KEY (code, source_path)
);

CREATE INDEX IF NOT EXISTS idx_message_codes_code ON message_codes(code);
CREATE INDEX IF NOT EXISTS idx_message_codes_severity ON message_codes(severity);

-- Additional indexes for case_cards and incidents
CREATE INDEX IF NOT EXISTS idx_case_cards_source ON case_cards(source_path);
CREATE INDEX IF NOT EXISTS idx_case_cards_hash ON case_cards(content_hash);
CREATE INDEX IF NOT EXISTS idx_incidents_log_path ON incidents(log_path);
"""
