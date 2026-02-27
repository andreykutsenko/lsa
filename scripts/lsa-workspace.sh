#!/usr/bin/env bash
set -euo pipefail

# lsa-workspace.sh
# Create a workspace directory and copy relevant files based on `lsa plan --json`.
#
# Usage:
#   lsa-workspace.sh --snap <SNAP> [--cid CID] [--jobid JOBID] [--title "..."]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lsa_config.sh"
UV_PROJECT="$SCRIPT_DIR/.."

usage() {
  cat <<EOF
Usage: $0 --snap <SNAP> [OPTIONS]

Required:
  --snap DIR     Path to LSA snapshot directory (must contain .lsa/lsa.sqlite)

Options:
  --cid CID      Client ID filter passed to lsa plan
  --jobid JOBID  Job ID filter passed to lsa plan
  --title TEXT   Free-text title/keyword passed to lsa plan (also appended to workspace name)
  -h, --help     Show this help and exit
EOF
}

SNAP=""
CID=""
JOBID=""
TITLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snap)
      if [[ -z "${2:-}" || "${2:-}" == --* ]]; then
        echo "[ERR] --snap requires a path value. \$SNAP is empty or not set."
        echo "      Set it first: SNAP=/path/to/snapshot"
        exit 2
      fi
      SNAP="$2"; shift 2
      ;;
    --cid)     CID="$2";   shift 2 ;;
    --jobid)   JOBID="$2"; shift 2 ;;
    --title)   TITLE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERR] Unknown argument: $1"; exit 2 ;;
  esac
done

if [[ -z "$SNAP" ]]; then
  echo "[ERR] --snap is required (SNAP variable is not set or --snap value is missing)"
  echo "      Set it first: SNAP=/path/to/snapshot"
  usage
  exit 2
fi

if [[ "$SNAP" == --* ]]; then
  echo "[ERR] --snap value looks like a flag ('$SNAP'). Did you forget to set \$SNAP?"
  echo "      Set it first: SNAP=/path/to/snapshot"
  exit 2
fi

SNAP="${SNAP%/}"
SNAP="$(cd "$SNAP" 2>/dev/null && pwd -P)" || { echo "[ERR] SNAP dir not found: $SNAP"; exit 1; }

if [[ ! -f "$SNAP/.lsa/lsa.sqlite" ]]; then
  echo "[ERR] LSA database not found: $SNAP/.lsa/lsa.sqlite"
  echo "      Hint: run 'lsa scan $SNAP' to build the index first"
  exit 1
fi

command -v uv >/dev/null || { echo "[ERR] uv not found. Run ./scripts/setup.sh first."; exit 1; }

if [[ -z "${WORKROOT:-}" ]]; then
  echo "[ERR] WORKROOT is not set. Define it in ~/.lsa/config.yaml or export WORKROOT=..."
  exit 1
fi

SNAP_BASE="$(basename "$SNAP")"
WS_NAME="${SNAP_BASE}"
[[ -n "$TITLE" ]] && WS_NAME="${WS_NAME}_${TITLE// /_}"
WS="$WORKROOT/$WS_NAME"

mkdir -p "$WS/code"

PLAN_JSON="$WS/plan.json"

cmd=(uv run --project "$UV_PROJECT" lsa plan "$SNAP" --json)
[[ -n "$CID"   ]] && cmd+=(--cid "$CID")
[[ -n "$JOBID" ]] && cmd+=(--jobid "$JOBID")
[[ -n "$TITLE" ]] && cmd+=(--title "$TITLE")
"${cmd[@]}" > "$PLAN_JSON"

FILES_LIST="$WS/files.list"
uv run --project "$UV_PROJECT" python -c "
import json, sys
obj = json.load(open(sys.argv[1]))
files = (obj.get('selected_bundle') or {}).get('files') or []
for f in files:
    print(f\"{f.get('kind','other')}|{f.get('path','')}|{f.get('abs_path','')}\")
" "$PLAN_JSON" > "$FILES_LIST"

COPIED=()
while IFS='|' read -r kind rel absp; do
  dst="$WS/code/$rel"
  mkdir -p "$(dirname "$dst")"
  if [[ -f "$absp" ]]; then
    cp -a "$absp" "$dst"
    COPIED+=("$rel")
  fi
done < "$FILES_LIST"

printf '════════════════════════════════\n'
printf 'Workspace: %s\n' "$WS"
printf 'Files copied:\n'
if [[ ${#COPIED[@]} -gt 0 ]]; then
  for f in "${COPIED[@]}"; do
    printf '  %s\n' "$f"
  done
else
  printf '  (none)\n'
fi
printf 'Plan JSON: %s\n' "$PLAN_JSON"
printf '\n'
printf 'Next steps:\n'
printf '  cd "%s/code"\n' "$WS"
printf '  # Edit files, then deploy\n'
printf '════════════════════════════════\n'
