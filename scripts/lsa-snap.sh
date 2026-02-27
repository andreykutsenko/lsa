#!/usr/bin/env bash
set -euo pipefail

# Load config from ~/.lsa/config.yaml (if available)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/lsa_config.sh" ]]; then
    source "$SCRIPT_DIR/lsa_config.sh"
fi
UV_PROJECT="$SCRIPT_DIR/.."

# -----------------------------------------------------------------------------
# lsa-snap.sh
#
# Creates a lightweight RHS snapshot (NO logs copy), then runs:
#   - lsa scan
#   - optional: lsa import-codes (PDF)
#   - optional: lsa import-histories
#
# Expected usage (requires UV: https://docs.astral.sh/uv/):
#   lsa-snap.sh [YYYYMMDD] [options]
#
# Examples:
#   lsa-snap.sh
#   lsa-snap.sh 20260123
#   lsa-snap.sh 20260123 --no-codes
#   lsa-snap.sh 20260123 --codes /path/to/codes.pdf
#   lsa-snap.sh 20260123 --histories /path/to/histories --histories-glob "**/*.md"
# -----------------------------------------------------------------------------

# -----------------------------
# Config (override via env vars)
# -----------------------------
RHS_HOST="${RHS_HOST:-rhs}"
SNAPROOT="${SNAPROOT:-$HOME/snapshots}"

# One shared PDF for all snapshots (but DB is per-snapshot, so we import per snapshot).
PDF_CODES_DEFAULT="${PDF_CODES_DEFAULT:-$SNAPROOT/refs/papyrus/Papyrus_DocExec_message_codes.pdf}"

# Histories live in the snapshot project root by default (NOT inside each snapshot).
HIST_DIR_DEFAULT="${HIST_DIR_DEFAULT:-$SNAPROOT/histories}"
HIST_GLOB_DEFAULT="${HIST_GLOB_DEFAULT:-**/*.md}"

# -----------------------------
# Args
# -----------------------------
DATE="${1:-$(date +%Y%m%d)}"
TS="$(date +%H%M%S)"
SNAP="$SNAPROOT/rhs_snapshot_${DATE}_${TS}"

IMPORT_CODES=1
PDF_CODES="$PDF_CODES_DEFAULT"

IMPORT_HISTORIES=1
HIST_DIR="$HIST_DIR_DEFAULT"
HIST_GLOB="$HIST_GLOB_DEFAULT"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [YYYYMMDD] [options]

Options:
  --no-codes
  --codes PATH | --codes=PATH

  --no-histories
  --histories DIR | --histories=DIR
  --histories-glob GLOB | --histories-glob=GLOB

Env overrides:
  RHS_HOST, SNAPROOT, PDF_CODES_DEFAULT, HIST_DIR_DEFAULT, HIST_GLOB_DEFAULT
EOF
}

# Robust args parsing (supports both "--k=v" and "--k v")
shift_count=1
if [[ $# -ge 1 && "${1:-}" =~ ^[0-9]{8}$ ]]; then
  # If first arg is a date, we already consumed it via DATE="${1:-...}"
  shift
else
  # No explicit date passed => do not shift
  shift_count=0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --no-codes)
      IMPORT_CODES=0
      shift
      ;;
    --codes=*)
      PDF_CODES="${1#*=}"
      shift
      ;;
    --codes)
      PDF_CODES="${2:-}"
      shift 2
      ;;
    --no-histories)
      IMPORT_HISTORIES=0
      shift
      ;;
    --histories=*)
      HIST_DIR="${1#*=}"
      shift
      ;;
    --histories)
      HIST_DIR="${2:-}"
      shift 2
      ;;
    --histories-glob=*)
      HIST_GLOB="${1#*=}"
      shift
      ;;
    --histories-glob)
      HIST_GLOB="${2:-}"
      shift 2
      ;;
    *)
      echo "[WARN] Unknown argument: $1"
      shift
      ;;
  esac
done

# -----------------------------
# Preconditions
# -----------------------------
mkdir -p "$SNAPROOT"

command -v rsync >/dev/null || { echo "[ERR] rsync not found"; exit 1; }
command -v ssh   >/dev/null || { echo "[ERR] ssh not found"; exit 1; }
command -v uv >/dev/null || { echo "[ERR] uv not found. Run ./scripts/setup.sh first."; exit 1; }

# Quick check RHS connectivity
SSH_TARGET="${SSH_TARGET:-$RHS_HOST}"
ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_TARGET" "true" >/dev/null 2>&1 || {
  echo "[ERR] Can't SSH to '$SSH_TARGET'. Check config or run ./scripts/setup.sh."
  exit 1
}

# -----------------------------
# Create dirs
# -----------------------------
mkdir -p "$SNAP/master" "$SNAP/procs" "$SNAP/control" "$SNAP/insert" "$SNAP/docdef" "$SNAP/logs_inbox"
echo "SNAP=$SNAP"

RSYNC_COMMON=(
  -avz
  --timeout=30
  --info=progress2
  --prune-empty-dirs
  --exclude='**/.nfs*'
  --exclude='**/*.swp'
  --exclude='**/*.swo'
  --exclude='**/*~'
)

# -----------------------------
# Copy master scripts (only scripts)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --include='*/' \
  --include='*.sh' --include='*.bash' --include='*.py' --include='*.pl' --include='*.pm' \
  --exclude='*' \
  "$SSH_TARGET:/home/master/" "$SNAP/master/"

# -----------------------------
# Copy procs (ONLY *.procs, exclude backup)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --exclude='**/backup/**' \
  --include='*/' --include='*.procs' --exclude='*' \
  "$SSH_TARGET:/home/procs/" "$SNAP/procs/"

# -----------------------------
# Copy control (safe-ish: max 5MB, exclude binaries)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --max-size=5m \
  --exclude='**/*.tif' --exclude='**/*.tiff' --exclude='**/*.pdf' \
  --exclude='**/*.zip' --exclude='**/*.gz' --exclude='**/*.tar' \
  "$SSH_TARGET:/home/control/" "$SNAP/control/"

# -----------------------------
# Copy insert (safe-ish: max 5MB, exclude binaries)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --max-size=5m \
  --exclude='**/*.tif' --exclude='**/*.tiff' --exclude='**/*.pdf' \
  --exclude='**/*.zip' --exclude='**/*.gz' --exclude='**/*.tar' \
  "$SSH_TARGET:/home/insert/" "$SNAP/insert/"

# -----------------------------
# Copy docdef (ONLY *.dfa*)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --include='*/' --include='*.dfa*' --exclude='*' \
  "$SSH_TARGET:/home/isis/docdef/" "$SNAP/docdef/"

# -----------------------------
# Minimal "copied OK" summary (no manifests)
# -----------------------------
echo
echo "==== SNAPSHOT SUMMARY ===="
du -sh "$SNAP"/* 2>/dev/null | sort -h || true
echo
echo "File counts:"
for d in master procs control insert docdef; do
  c=$(find "$SNAP/$d" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "  $d: $c"
done
echo "=========================="
echo

# -----------------------------
# Index (scan)
# -----------------------------
echo "Running: lsa scan (DB -> $SNAP/.lsa/lsa.sqlite)"
uv run --project "$UV_PROJECT" lsa scan "$SNAP"
uv run --project "$UV_PROJECT" lsa stats "$SNAP" || true

# -----------------------------
# Import codes from PDF
# -----------------------------
if [[ "$IMPORT_CODES" == "1" ]]; then
  if [[ -f "$PDF_CODES" ]]; then
    echo
    echo "Importing message codes from PDF:"
    echo "  PDF=$PDF_CODES"
    uv run --project "$UV_PROJECT" lsa import-codes "$SNAP" --pdf "$PDF_CODES"
  else
    echo
    echo "[WARN] PDF not found, skipping import-codes:"
    echo "  $PDF_CODES"
  fi
fi

# -----------------------------
# Import histories
# -----------------------------
if [[ "$IMPORT_HISTORIES" == "1" ]]; then
  if [[ -d "$HIST_DIR" ]]; then
    echo
    echo "Importing histories:"
    echo "  DIR=$HIST_DIR"
    echo "  GLOB=$HIST_GLOB"
    uv run --project "$UV_PROJECT" lsa import-histories "$SNAP" --path "$HIST_DIR" --glob "$HIST_GLOB"
  else
    echo
    echo "[WARN] Histories dir not found, skipping import-histories:"
    echo "  $HIST_DIR"
  fi
fi

echo
echo "SNAPSHOT_READY=$SNAP"
echo
echo "Next:"
echo "  1) Drop a specific log here (optional): $SNAP/logs_inbox/"
echo "  2) Run analysis:"
echo "     lsa explain \"$SNAP\" --log /path/to/your.log"
