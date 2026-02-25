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
#   2. Collects RHS credentials (hostname, username, password)
#   3. Writes ~/.lsa/config.yaml
#   4. Adds lsa() shell function and scripts PATH to ~/.bashrc
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
uv sync --project "$PROJECT_ROOT/tools/lsa"

info "LSA synced."

# -----------------------------------------------------------------------------
# Step 2: SSH credentials for RHS server
# -----------------------------------------------------------------------------
section "--- Step 2: RHS server credentials ---"
echo "LSA connects to the RHS server to create snapshots."
echo "Press Enter to accept defaults shown in [brackets]."
echo

read -rp "RHS hostname (e.g. linux-server.company.com): " rhs_host
while [[ -z "$rhs_host" ]]; do
  warn "Hostname cannot be empty."
  read -rp "RHS hostname: " rhs_host
done

read -rp "SSH username: " rhs_user
while [[ -z "$rhs_user" ]]; do
  warn "Username cannot be empty."
  read -rp "SSH username: " rhs_user
done

read -rsp "SSH password: " rhs_pass
echo
while [[ -z "$rhs_pass" ]]; do
  warn "Password cannot be empty."
  read -rsp "SSH password: " rhs_pass
  echo
done

ssh_auth="password"

if ! command -v sshpass >/dev/null 2>&1; then
  warn "sshpass not found — password auth will not work."
  echo "       Install it:  sudo apt install sshpass"
fi

mkdir -p "$HOME/.lsa"
echo "$rhs_pass" > "$HOME/.lsa/.rhs_pass"
chmod 600 "$HOME/.lsa/.rhs_pass"
info "Password saved to ~/.lsa/.rhs_pass (mode 600)."

info "Testing SSH connection to $rhs_user@$rhs_host ..."
if command -v sshpass >/dev/null 2>&1; then
  if sshpass -f "$HOME/.lsa/.rhs_pass" ssh \
      -o StrictHostKeyChecking=accept-new \
      -o ConnectTimeout=10 \
      "$rhs_user@$rhs_host" "echo OK" >/dev/null 2>&1; then
    info "SSH connection: OK"
  else
    warn "SSH connection test failed. Check credentials or re-run setup.sh later."
  fi
else
  warn "Skipping SSH test (sshpass not installed)."
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
ssh_auth: "$ssh_auth"
snaproot: "$snaproot"
workroot: "$workroot"
YAML

chmod 600 "$config_file"
info "Config written: $config_file"

# -----------------------------------------------------------------------------
# Step 4: Shell function and PATH
# -----------------------------------------------------------------------------
section "--- Step 4: Updating ~/.bashrc ---"

bashrc="$HOME/.bashrc"

# lsa shell function (replaces old ~/.local/bin/lsa wrapper)
if ! grep -q 'lsa()' "$bashrc" 2>/dev/null; then
  cat >> "$bashrc" <<FUNC

# LSA command (added by setup.sh)
lsa() { uv run --project "$PROJECT_ROOT/tools/lsa" lsa "\$@"; }
FUNC
  info "Added lsa() shell function to $bashrc"
else
  info "lsa() shell function already in $bashrc — skipping."
fi

# $PROJECT_ROOT/scripts
scripts_dir="$PROJECT_ROOT/scripts"
if ! grep -q "$scripts_dir" "$bashrc" 2>/dev/null; then
  if ! grep -q "Added by lsa setup.sh" "$bashrc" 2>/dev/null; then
    echo '' >> "$bashrc"
    echo '# Added by lsa setup.sh' >> "$bashrc"
  fi
  echo "export PATH=\"$scripts_dir:\$PATH\"" >> "$bashrc"
fi

# -----------------------------------------------------------------------------
# Step 5: Summary
# -----------------------------------------------------------------------------
section "--- Setup complete ---"
echo
echo "  ${BOLD}Config:${RESET}   $config_file"
echo "  ${BOLD}Project:${RESET}  $PROJECT_ROOT/tools/lsa"
echo
echo "Next steps:"
echo "  1. Reload your shell:"
echo "       source ~/.bashrc"
echo
echo "  2. Verify the install:"
echo "       lsa --help"
echo
echo "  3. Create your first snapshot:"
echo "       ./scripts/lsa-snap.sh"
