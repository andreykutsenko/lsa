#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# mk_snap_and_scan.sh
#
# Creates a lightweight RHS snapshot (NO logs copy), then runs:
#   - lsa scan
#   - optional: lsa import-codes (PDF)
#   - optional: lsa import-histories
#
# Expected usage (from an activated venv where LSA is importable):
#   mk_snap_and_scan.sh [YYYYMMDD] [options]
#
# Examples:
#   mk_snap_and_scan.sh
#   mk_snap_and_scan.sh 20260123
#   mk_snap_and_scan.sh 20260123 --no-codes
#   mk_snap_and_scan.sh 20260123 --codes /path/to/codes.pdf
#   mk_snap_and_scan.sh 20260123 --histories /path/to/histories --histories-glob "**/*.md"
# -----------------------------------------------------------------------------

# -----------------------------
# Config (override via env vars)
# -----------------------------
RHS_HOST="${RHS_HOST:-rhs}"  # ssh alias/host
SNAPROOT="${SNAPROOT:-/mnt/c/Users/akutsenko/code/rhs_snapshot_project}"

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

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "[WARN] VIRTUAL_ENV is not set (venv not activated)."
  echo "       Recommended:"
  echo "         cd /mnt/c/Users/akutsenko/code/lsa_project && source .venv/bin/activate"
fi

command -v rsync >/dev/null || { echo "[ERR] rsync not found"; exit 1; }
command -v ssh   >/dev/null || { echo "[ERR] ssh not found"; exit 1; }
command -v python >/dev/null || { echo "[ERR] python not found"; exit 1; }

# Quick check RHS connectivity
ssh -o BatchMode=yes -o ConnectTimeout=5 "$RHS_HOST" "true" >/dev/null 2>&1 || {
  echo "[ERR] Can't SSH to '$RHS_HOST'. Check ssh config/alias."
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
  "$RHS_HOST:/home/master/" "$SNAP/master/"

# -----------------------------
# Copy procs (ONLY *.procs, exclude backup)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --exclude='**/backup/**' \
  --include='*/' --include='*.procs' --exclude='*' \
  "$RHS_HOST:/home/procs/" "$SNAP/procs/"

# -----------------------------
# Copy control (safe-ish: max 5MB, exclude binaries)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --max-size=5m \
  --exclude='**/*.tif' --exclude='**/*.tiff' --exclude='**/*.pdf' \
  --exclude='**/*.zip' --exclude='**/*.gz' --exclude='**/*.tar' \
  "$RHS_HOST:/home/control/" "$SNAP/control/"

# -----------------------------
# Copy insert (safe-ish: max 5MB, exclude binaries)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --max-size=5m \
  --exclude='**/*.tif' --exclude='**/*.tiff' --exclude='**/*.pdf' \
  --exclude='**/*.zip' --exclude='**/*.gz' --exclude='**/*.tar' \
  "$RHS_HOST:/home/insert/" "$SNAP/insert/"

# -----------------------------
# Copy docdef (ONLY *.dfa*)
# -----------------------------
rsync "${RSYNC_COMMON[@]}" \
  --include='*/' --include='*.dfa*' --exclude='*' \
  "$RHS_HOST:/home/isis/docdef/" "$SNAP/docdef/"

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
# Use python -m lsa.cli to guarantee we hit the current venv interpreter.
# -----------------------------
echo "Running: lsa scan (DB -> $SNAP/.lsa/lsa.sqlite)"
python -m lsa.cli scan "$SNAP"
python -m lsa.cli stats "$SNAP" || true

# -----------------------------
# Import codes from PDF
# -----------------------------
if [[ "$IMPORT_CODES" == "1" ]]; then
  if [[ -f "$PDF_CODES" ]]; then
    echo
    echo "Importing message codes from PDF:"
    echo "  PDF=$PDF_CODES"
    python -m lsa.cli import-codes "$SNAP" --pdf "$PDF_CODES"
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
    python -m lsa.cli import-histories "$SNAP" --path "$HIST_DIR" --glob "$HIST_GLOB"
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
echo "     python -m lsa.cli explain \"$SNAP\" --log /path/to/your.log"
