#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# lsa-snap.sh
#
# Simplified snapshot script. Creates an RHS snapshot, then runs:
#   - lsa scan
#   - lsa stats
#
# NO import-codes, NO import-histories.
#
# Usage:
#   lsa-snap.sh [YYYYMMDD]
#
# Examples:
#   lsa-snap.sh
#   lsa-snap.sh 20260123
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lsa_config.sh"
UV_PROJECT="$SCRIPT_DIR/.."

# -----------------------------
# Date and snapshot path
# -----------------------------
DATE="${1:-$(date +%Y%m%d)}"
TS="$(date +%H%M%S)"
SNAP="$SNAPROOT/rhs_snapshot_${DATE}_${TS}"

# -----------------------------
# Preconditions
# -----------------------------
mkdir -p "$SNAPROOT"

command -v rsync >/dev/null || { echo "[ERR] rsync not found"; exit 1; }
command -v ssh   >/dev/null || { echo "[ERR] ssh not found"; exit 1; }

# -----------------------------
# Create dirs
# -----------------------------
mkdir -p "$SNAP/master" "$SNAP/procs" "$SNAP/control" "$SNAP/insert" "$SNAP/docdef"
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
# Summary
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
# Scan
# -----------------------------
echo "Running: lsa scan (DB -> $SNAP/.lsa/lsa.sqlite)"
uv run --project "$UV_PROJECT" lsa scan "$SNAP"
uv run --project "$UV_PROJECT" lsa stats "$SNAP" || true

echo
echo "════════════════════════════════"
echo "SNAP=$SNAP"
echo "Created: $(date)"
echo
echo "Tip: Re-run lsa-snap.sh only after a deployment to production."
echo
echo "Next steps:"
echo "  lsa plan \"$SNAP\" --title <keyword>"
echo "  lsa plan \"$SNAP\" --title <keyword> --deep"
echo "════════════════════════════════"
