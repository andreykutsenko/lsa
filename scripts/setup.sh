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
#   2. Collects RHS connection config interactively
#   3. Writes ~/.lsa/config.yaml
#   4. Adds lsa() shell function and scripts to PATH
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
# Step 2: Interactive config collection
# -----------------------------------------------------------------------------
section "--- LSA Configuration ---"
echo "Enter your RHS server connection details."
echo "Press Enter to accept defaults shown in brackets."
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

read -rp "SSH authentication [password/key] (default: password): " ssh_auth
ssh_auth="${ssh_auth:-password}"
# Normalize to lowercase and validate
ssh_auth="$(echo "$ssh_auth" | tr '[:upper:]' '[:lower:]')"
if [[ "$ssh_auth" != "password" && "$ssh_auth" != "key" ]]; then
  warn "Unrecognized auth type '$ssh_auth', defaulting to 'password'."
  ssh_auth="password"
fi

# ---------- Password auth ----------
if [[ "$ssh_auth" == "password" ]]; then
  read -rsp "RHS password (will be stored in ~/.lsa/.rhs_pass): " rhs_pass
  echo

  if ! command -v sshpass >/dev/null 2>&1; then
    warn "sshpass not found — password auth will not work."
    echo "       Install it first:"
    echo "         Ubuntu/Debian:  sudo apt install sshpass"
    echo "         macOS:          brew install hudochenkov/sshpass/sshpass"
  fi

  mkdir -p "$HOME/.lsa"
  echo "$rhs_pass" > "$HOME/.lsa/.rhs_pass"
  chmod 600 "$HOME/.lsa/.rhs_pass"
  info "Password stored in ~/.lsa/.rhs_pass (mode 600)."

  info "Testing SSH connection to $rhs_user@$rhs_host ..."
  if command -v sshpass >/dev/null 2>&1; then
    if sshpass -f "$HOME/.lsa/.rhs_pass" ssh \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=10 \
        "$rhs_user@$rhs_host" "echo OK" >/dev/null 2>&1; then
      info "SSH connection: OK"
    else
      warn "SSH connection test failed. Check hostname, username, and password."
      warn "You can re-run setup.sh after fixing the issue."
    fi
  else
    warn "Skipping SSH test (sshpass not installed)."
  fi

# ---------- Key auth ----------
else
  info "Testing SSH connection to $rhs_user@$rhs_host (key auth) ..."
  if ssh -o BatchMode=yes -o ConnectTimeout=5 "$rhs_user@$rhs_host" "echo OK" >/dev/null 2>&1; then
    info "SSH connection: OK"
  else
    warn "SSH key connection test failed."
    warn "Make sure your key is loaded (ssh-add) or configured in ~/.ssh/config."
    warn "Continuing setup — you can fix this later."
  fi
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
# Step 5: Shell function and PATH updates
# -----------------------------------------------------------------------------
section "--- Step 5: Shell function and PATH ---"

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
if echo "$PATH" | tr ':' '\n' | grep -qx "$scripts_dir"; then
  info "$scripts_dir is already in PATH — skipping."
else
  read -rp "Add $scripts_dir to PATH in ~/.bashrc? [Y/n]: " add_scripts
  add_scripts="${add_scripts:-Y}"
  if [[ "$add_scripts" =~ ^[Yy]$ ]]; then
    if ! grep -q "Added by lsa setup.sh" "$bashrc" 2>/dev/null; then
      echo '' >> "$bashrc"
      echo '# Added by lsa setup.sh' >> "$bashrc"
    fi
    echo "export PATH=\"$scripts_dir:\$PATH\"" >> "$bashrc"
    info "Added $scripts_dir to PATH in $bashrc"
  else
    info "Skipped scripts PATH update."
  fi
fi

# -----------------------------------------------------------------------------
# Step 6: Summary
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
