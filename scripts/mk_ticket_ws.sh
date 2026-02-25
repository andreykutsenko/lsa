#!/usr/bin/env bash
set -euo pipefail

# Load config from ~/.lsa/config.yaml (if available)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/lsa_config.sh" ]]; then
    source "$SCRIPT_DIR/lsa_config.sh"
fi
UV_PROJECT="$SCRIPT_DIR/../tools/lsa"

# mk_ticket_ws.sh
# Create a ticket workspace and pull relevant files (from snapshot or via SSH) based on `lsa plan --json`.
#
# Usage:
#   mk_ticket_ws.sh TICKET --snap <SNAP> [--cid CID] [--jobid JOBID] [--pick PICK]
#                          [--title "..."] [--mode snap|ssh] [--rhs-host rhs] [--rhs HOST]
#                          [--root DIR]
#
# Shortcuts:
#   --ssh-copy  (same as --mode ssh)
#   --snap-copy (same as --mode snap)

usage() {
  cat <<EOF
Usage: $0 TICKET --snap <SNAP> [OPTIONS]

Arguments:
  TICKET              Ticket identifier (e.g. INC0123456)

Required:
  --snap DIR          Path to LSA snapshot directory (must contain .lsa/lsa.sqlite)

Options:
  --cid CID           Case/correlation ID filter passed to lsa plan
  --jobid JOBID       Job ID filter passed to lsa plan
  --pick PICK         Bundle pick expression passed to lsa plan
  --title TEXT        Ticket title (added to the note)
  --mode snap|ssh     Copy mode: snap (default) or ssh
  --snap-copy         Alias for --mode snap
  --ssh-copy          Alias for --mode ssh
  --rhs-host HOST     SSH host/alias for remote copy (default: rhs)
  --rhs HOST          Alias for --rhs-host
  --root DIR          Override workspace root directory (default: \$WORKROOT or ~/workspaces)
  -h, --help          Show this help and exit
EOF
}

WORKROOT="${WORKROOT:-$HOME/workspaces}"
MODE="snap"        # snap | ssh
RHS_HOST="${RHS_HOST:-rhs}"
CID=""
TITLE=""
SNAP=""
JOBID=""
PICK=""

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

TICKET="$1"; shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snap)      SNAP="$2"; shift 2 ;;
    --cid)       CID="$2"; shift 2 ;;
    --jobid)     JOBID="$2"; shift 2 ;;
    --pick)      PICK="$2"; shift 2 ;;
    --title)     TITLE="$2"; shift 2 ;;
    --mode)      MODE="$2"; shift 2 ;;
    --rhs-host)  RHS_HOST="$2"; shift 2 ;;
    --rhs)       RHS_HOST="$2"; shift 2 ;;
    --root)      WORKROOT="$2"; shift 2 ;;
    --ssh-copy)  MODE="ssh"; shift ;;
    --snap-copy) MODE="snap"; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

if [[ -z "$SNAP" ]]; then
  echo "[ERR] --snap is required"; exit 2
fi

SNAP="${SNAP%/}"

if [[ "$MODE" != "snap" && "$MODE" != "ssh" ]]; then
  echo "[ERR] --mode must be snap or ssh"; exit 2
fi

# Precondition checks
command -v uv >/dev/null || { echo "[ERR] uv not found. Run ./scripts/setup.sh first."; exit 1; }

command -v rsync >/dev/null || { echo "[ERR] rsync not found (install rsync first)"; exit 1; }

SNAP="$(cd "$SNAP" 2>/dev/null && pwd -P)" || { echo "[ERR] SNAP dir not found: $SNAP"; exit 1; }

if [[ ! -f "$SNAP/.lsa/lsa.sqlite" ]]; then
  echo "[ERR] LSA database not found: $SNAP/.lsa/lsa.sqlite"
  echo "      Hint: run 'lsa scan $SNAP' to build the index first"
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
WS="${WORKROOT}/${TICKET}_${TS}"

mkdir -p "$WS"

# Required structure
mkdir -p \
  "$WS/code" \
  "$WS/logs" \
  "$WS/process" \
  "$WS/samples" \
  "$WS/prj" \
  "$WS/mapping" \
  "$WS/notes" \
  "$WS/scripts"

# LSA files land under code/<kind>/...
mkdir -p "$WS/code/procs" "$WS/code/master" "$WS/code/insert" "$WS/code/control" "$WS/code/docdef" "$WS/code/other"

LOGFILE="$WS/logs/mk_ticket_ws.log"
log() {
  printf '%s | %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOGFILE"
}

log "WS=$WS"
log "SNAP=$SNAP"
log "MODE=${MODE^^}"

PLAN_JSON="$WS/logs/plan.json"

cmd=(uv run --project "$UV_PROJECT" lsa plan "$SNAP" --json)
[[ -n "$CID"   ]] && cmd+=(--cid "$CID")
[[ -n "$TITLE" ]] && cmd+=(--title "$TITLE")
[[ -n "$JOBID" ]] && cmd+=(--jobid "$JOBID")

log "Running: ${cmd[*]}"
"${cmd[@]}" > "$PLAN_JSON"

FILES_LIST="$WS/logs/files.list"
uv run --project "$UV_PROJECT" python - <<'PY' "$PLAN_JSON" > "$FILES_LIST"
import json, sys
p = sys.argv[1]
obj = json.load(open(p, 'r', encoding='utf-8'))
files = (obj.get('selected_bundle') or {}).get('files') or []
for f in files:
    kind = f.get('kind') or 'other'
    rel  = f.get('path') or ''
    absp = f.get('abs_path') or ''
    # kind|rel|abs
    print(f"{kind}|{rel}|{absp}")
PY

if [[ ! -s "$FILES_LIST" ]]; then
  log "[WARN] No files in selected_bundle.files. Nothing to copy."
else
  log "Files (from plan):"
  while IFS='|' read -r kind rel absp; do
    log "  - $kind  $rel"
  done < "$FILES_LIST"
fi

remote_base_for_kind() {
  case "$1" in
    procs)            printf '%s' "/home/procs" ;;
    script|master)    printf '%s' "/home/master" ;;
    insert)           printf '%s' "/home/insert" ;;
    control)          printf '%s' "/home/control" ;;
    docdef)           printf '%s' "/home/isis/docdef" ;;
    *)                printf '%s' "" ;;
  esac
}

copy_from_snapshot() {
  local kind="$1" rel="$2" absp="$3"
  local dst="$WS/code/$rel"

  mkdir -p "$(dirname "$dst")"

  if [[ -z "$absp" ]]; then
    log "[WARN] Missing abs_path for $kind $rel (skipped)"
    return 0
  fi
  if [[ ! -f "$absp" ]]; then
    log "[WARN] SNAP missing file: $absp"
    return 0
  fi

  log "SNAP COPY: $absp -> $dst"
  cp -a "$absp" "$dst"
}

copy_from_ssh() {
  local kind="$1" rel="$2"

  # rel like: procs/mocume2.procs -> strip top folder
  local subpath="$rel"
  subpath="${subpath#procs/}"
  subpath="${subpath#master/}"
  subpath="${subpath#insert/}"
  subpath="${subpath#control/}"
  subpath="${subpath#docdef/}"

  local base
  base="$(remote_base_for_kind "$kind")"
  if [[ -z "$base" ]]; then
    log "[WARN] No remote mapping for kind=$kind rel=$rel (skipped)"
    return 0
  fi

  local src="${RHS_HOST}:${base}/${subpath}"
  local dst="$WS/code/$rel"
  mkdir -p "$(dirname "$dst")"

  log "SSH COPY: $src -> $dst"
  rsync -az --timeout=30 "$src" "$dst"
}

if [[ -s "$FILES_LIST" ]]; then
  while IFS='|' read -r kind rel absp; do
    # Normalize kind
    [[ "$kind" == "script" ]] && kind="master"

    case "$MODE" in
      snap) copy_from_snapshot "$kind" "$rel" "$absp" ;;
      ssh)  copy_from_ssh      "$kind" "$rel" ;;
    esac
  done < "$FILES_LIST"
fi

PULL_SCRIPT="$WS/scripts/pull_from_rhs.sh"
cat > "$PULL_SCRIPT" <<PULL
#!/usr/bin/env bash
# Auto-generated by mk_ticket_ws.sh
# Pulls files from RHS host into code/ using rsync.
set -euo pipefail

RHS_HOST="${RHS_HOST}"
WS="\$(cd "\$(dirname "\$0")/.." && pwd -P)"
FILES_LIST="\$WS/logs/files.list"

while IFS='|' read -r kind rel absp; do
  dst="\$WS/code/\$rel"
  mkdir -p "\$(dirname "\$dst")"

  case "\$rel" in
    master/*)  src="\$RHS_HOST:/home/master/\${rel#master/}" ;;
    script/*)  src="\$RHS_HOST:/home/master/\${rel#script/}" ;;
    procs/*)   src="\$RHS_HOST:/home/procs/\${rel#procs/}" ;;
    control/*) src="\$RHS_HOST:/home/control/\${rel#control/}" ;;
    insert/*)  src="\$RHS_HOST:/home/insert/\${rel#insert/}" ;;
    docdef/*)  src="\$RHS_HOST:/home/isis/docdef/\${rel#docdef/}" ;;
    *)         echo "[SKIP] No remote mapping for: \$rel"; continue ;;
  esac

  echo "PULL: \$src -> \$dst"
  rsync -avz --timeout=30 "\$src" "\$dst" || true
done < "\$FILES_LIST"
PULL
chmod +x "$PULL_SCRIPT"
log "Generated: $PULL_SCRIPT"

NOTE="$WS/notes/${TICKET}.md"
{
  echo "# ${TICKET}"
  echo
  [[ -n "$TITLE" ]] && { echo "**Title:** ${TITLE}"; echo; }
  [[ -n "$PICK"  ]] && { echo "**Pick:** ${PICK}"; echo; }
  echo "## Workspace"
  echo "- Path: \`${WS}\`"
  echo
  echo "## Snapshot"
  echo "- SNAP: \`${SNAP}\`"
  echo "- DB:   \`${SNAP}/.lsa/lsa.sqlite\`"
  echo "- Copy mode: **${MODE}**"
  echo
  echo "## Files copied into code/"
  echo
  if [[ -s "$FILES_LIST" ]]; then
    while IFS='|' read -r kind rel absp; do
      echo "- \`${rel}\` *(kind=${kind})*"
    done < "$FILES_LIST"
  else
    echo "- (none)"
  fi
  echo
  echo "## Next steps"
  echo "- To pull latest versions from RHS: \`bash scripts/pull_from_rhs.sh\`"
  echo
  echo "## Logs"
  echo "- Script log: \`logs/mk_ticket_ws.log\`"
  echo "- Plan JSON:  \`logs/plan.json\`"
} > "$NOTE"

log "DONE. Note: $NOTE"
log "DONE. Log:  $LOGFILE"

printf 'WS=%s\n' "$WS"
printf 'NOTE=%s\n' "$NOTE"
printf 'LOG=%s\n' "$LOGFILE"
