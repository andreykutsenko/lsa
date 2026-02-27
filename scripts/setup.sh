#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# setup.sh
#
# One-time interactive setup for LSA (Legacy Script Archaeologist).
# Run after git clone:
#   bash scripts/setup.sh
#
# What it does:
#   1. Installs UV (if needed) and syncs LSA dependencies
#   2. Configures SSH key auth for RHS server (~/.ssh/config)
#   3. Writes ~/.lsa/config.yaml
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# -----------------------------------------------------------------------------
# Colors (only if tput is available and we're in an interactive terminal)
# -----------------------------------------------------------------------------
if command -v tput >/dev/null 2>&1 && [[ -t 1 ]]; then
  BOLD="$(tput bold)"
  GREEN="$(tput setaf 2)"
  YELLOW="$(tput setaf 3)"
  RED="$(tput setaf 1)"
  CYAN="$(tput setaf 6)"
  RESET="$(tput sgr0)"
else
  BOLD=""
  GREEN=""
  YELLOW=""
  RED=""
  CYAN=""
  RESET=""
fi

info()    { echo "${GREEN}[INFO]${RESET} $*"; }
warn()    { echo "${YELLOW}[WARN]${RESET} $*" >&2; }
error()   { echo "${RED}[ERR]${RESET}  $*" >&2; }
section() { echo; echo "${BOLD}${CYAN}$*${RESET}"; }

# -----------------------------------------------------------------------------
# Ctrl+C handler
# -----------------------------------------------------------------------------
trap 'echo; warn "Setup interrupted. You can re-run scripts/setup.sh at any time."; exit 130' INT

# -----------------------------------------------------------------------------
# Step 1: Install UV and sync dependencies
# -----------------------------------------------------------------------------
section "--- Step 1: Installing UV and syncing LSA ---"

if ! command -v uv >/dev/null 2>&1; then
  info "Installing UV package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

info "UV found: $(uv --version)"

info "Syncing LSA dependencies (UV handles Python + venv + deps)..."
uv sync --project "$PROJECT_ROOT"

info "LSA synced."

# -----------------------------------------------------------------------------
# Step 2: SSH key auth for RHS server
# -----------------------------------------------------------------------------
section "--- Step 2: RHS server SSH key auth ---"
echo "LSA connects to the RHS server to create snapshots."
echo
echo "  Default server: ca-isis-pr-04.infoimageinc.com"
echo "  Default user:   oper1"
echo
echo "  Press Enter to use defaults, or type a new value to override."
echo

default_rhs_host="ca-isis-pr-04.infoimageinc.com"
default_rhs_user="oper1"

read -rp "RHS hostname [${default_rhs_host}]: " rhs_host
rhs_host="${rhs_host:-$default_rhs_host}"

read -rp "SSH username [${default_rhs_user}]: " rhs_user
rhs_user="${rhs_user:-$default_rhs_user}"

read -rp "Path to SSH private key (e.g. ~/.ssh/id_rsa): " key_path
while [[ -z "$key_path" ]]; do
  warn "Key path cannot be empty."
  read -rp "Path to SSH private key: " key_path
done

key_path="${key_path/#\~/$HOME}"

if [[ ! -f "$key_path" ]]; then
  error "Key file not found: $key_path"
  exit 1
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [[ "$key_path" != "$HOME/.ssh/id_rsa" ]]; then
  cp "$key_path" "$HOME/.ssh/id_rsa"
  key_path="$HOME/.ssh/id_rsa"
  info "Key copied to ~/.ssh/id_rsa"
fi

chmod 600 "$key_path"

if ! grep -q "^Host rhs$" "$HOME/.ssh/config" 2>/dev/null; then
cat >> "$HOME/.ssh/config" <<SSH_CONF

Host rhs
  HostName $rhs_host
  User $rhs_user
  IdentityFile ~/.ssh/id_rsa
  PubkeyAuthentication yes
  StrictHostKeyChecking no
  ServerAliveInterval 60
  ServerAliveCountMax 5
SSH_CONF
  chmod 600 "$HOME/.ssh/config"
  info "SSH config added: Host rhs -> $rhs_host"
else
  warn "Host rhs already exists in ~/.ssh/config — skipping."
fi

info "Testing SSH connection to rhs ..."
if ssh -o BatchMode=yes -o ConnectTimeout=10 rhs "echo OK" >/dev/null 2>&1; then
  info "SSH connection: OK"
else
  warn "SSH connection test failed. Check your key or re-run setup.sh later."
fi

# ---------- Directories ----------
echo
read -rp "Snapshots directory (default: ~/snapshots): " snaproot_input
snaproot="${snaproot_input:-$HOME/snapshots}"
# Expand ~ manually in case user typed it
snaproot="${snaproot/#\~/$HOME}"

read -rp "Workspaces directory (default: ~/workspaces): " workroot_input
workroot="${workroot_input:-$HOME/workspaces}"
workroot="${workroot/#\~/$HOME}"

# -----------------------------------------------------------------------------
# Step 3: Write ~/.lsa/config.yaml
# -----------------------------------------------------------------------------
section "--- Step 3: Writing ~/.lsa/config.yaml ---"

mkdir -p "$HOME/.lsa"
config_file="$HOME/.lsa/config.yaml"

cat > "$config_file" <<YAML
rhs_host: "$rhs_host"
rhs_user: "$rhs_user"
snaproot: "$snaproot"
workroot: "$workroot"
YAML

chmod 600 "$config_file"
info "Config written: $config_file"

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
section "--- Setup complete ---"
echo
echo "  ${BOLD}Config:${RESET}    ~/.lsa/config.yaml"
echo "  ${BOLD}SSH:${RESET}       ~/.ssh/config (Host rhs)"
echo
echo "  To start using LSA:"
echo "    source .venv/bin/activate"
echo "    lsa --help"
echo
echo "  To create a snapshot:"
echo "    ./scripts/lsa-snap.sh"
echo
echo "  Daily usage:"
echo "    source .venv/bin/activate"
echo "    lsa plan \$SNAP --title <keyword>"
echo "    lsa plan \$SNAP --title <keyword> --deep"
