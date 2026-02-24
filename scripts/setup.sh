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
#   1. Checks Python 3.11+
#   2. Creates .venv and installs LSA in editable mode
#   3. Writes ~/.local/bin/lsa wrapper
#   4. Collects RHS connection config interactively
#   5. Writes ~/.lsa/config.yaml
#   6. Optionally updates ~/.bashrc PATH
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
# Step 1: Python 3.11+ check
# -----------------------------------------------------------------------------
section "--- Step 1: Checking Python version ---"

if ! command -v python3 >/dev/null 2>&1; then
  error "python3 not found."
  echo "  Install it first:"
  echo "    Ubuntu/Debian:  sudo apt install python3.11"
  echo "    macOS:          brew install python@3.11"
  exit 1
fi

py_version="$(python3 --version 2>&1 | sed 's/Python //')"
py_major="$(echo "$py_version" | cut -d. -f1)"
py_minor="$(echo "$py_version" | cut -d. -f2)"

if [[ "$py_major" -lt 3 ]] || { [[ "$py_major" -eq 3 ]] && [[ "$py_minor" -lt 11 ]]; }; then
  error "Python 3.11+ required, found $py_version."
  echo "  Install a newer version:"
  echo "    Ubuntu/Debian:  sudo apt install python3.11"
  echo "    macOS:          brew install python@3.11"
  exit 1
fi

info "Python $py_version — OK"

# -----------------------------------------------------------------------------
# Step 2: Create venv and install LSA
# -----------------------------------------------------------------------------
section "--- Step 2: Creating virtualenv and installing LSA ---"

venv_dir="$PROJECT_ROOT/.venv"

if [[ -d "$venv_dir" ]]; then
  info "Virtualenv already exists at $venv_dir — skipping creation."
else
  info "Creating virtualenv at $venv_dir ..."
  python3 -m venv "$venv_dir"
fi

info "Upgrading pip ..."
"$venv_dir/bin/pip" install --upgrade pip --quiet

info "Installing LSA in editable mode from $PROJECT_ROOT/tools/lsa ..."
"$venv_dir/bin/pip" install -e "$PROJECT_ROOT/tools/lsa" --quiet

info "LSA installed."

# -----------------------------------------------------------------------------
# Step 3: Write ~/.local/bin/lsa wrapper
# -----------------------------------------------------------------------------
section "--- Step 3: Creating ~/.local/bin/lsa wrapper ---"

mkdir -p "$HOME/.local/bin"
wrapper="$HOME/.local/bin/lsa"

cat > "$wrapper" <<WRAPPER
#!/bin/bash
exec "$venv_dir/bin/python" -m lsa.cli "\$@"
WRAPPER

chmod +x "$wrapper"
info "Wrapper written: $wrapper"

# -----------------------------------------------------------------------------
# Step 4: Interactive config collection
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
# Step 5: Write ~/.lsa/config.yaml
# -----------------------------------------------------------------------------
section "--- Step 5: Writing ~/.lsa/config.yaml ---"

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
# Step 6: PATH updates in ~/.bashrc
# -----------------------------------------------------------------------------
section "--- Step 6: Updating PATH ---"

bashrc="$HOME/.bashrc"

# ~/.local/bin
if echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/.local/bin"; then
  info "~/.local/bin is already in PATH — skipping."
else
  read -rp "Add ~/.local/bin to PATH in ~/.bashrc? [Y/n]: " add_local_bin
  add_local_bin="${add_local_bin:-Y}"
  if [[ "$add_local_bin" =~ ^[Yy]$ ]]; then
    echo '' >> "$bashrc"
    echo '# Added by lsa setup.sh' >> "$bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$bashrc"
    info "Added ~/.local/bin to PATH in $bashrc"
  else
    info "Skipped ~/.local/bin PATH update."
  fi
fi

# $PROJECT_ROOT/scripts
scripts_dir="$PROJECT_ROOT/scripts"
if echo "$PATH" | tr ':' '\n' | grep -qx "$scripts_dir"; then
  info "$scripts_dir is already in PATH — skipping."
else
  read -rp "Add $scripts_dir to PATH in ~/.bashrc? [Y/n]: " add_scripts
  add_scripts="${add_scripts:-Y}"
  if [[ "$add_scripts" =~ ^[Yy]$ ]]; then
    # Avoid duplicate comment if we already wrote it above
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
# Step 7: Summary
# -----------------------------------------------------------------------------
section "--- Setup complete ---"
echo
echo "  ${BOLD}Config:${RESET}   $config_file"
echo "  ${BOLD}Wrapper:${RESET}  $wrapper"
echo "  ${BOLD}Venv:${RESET}     $venv_dir"
echo
echo "Next steps:"
echo "  1. Reload your shell:"
echo "       source ~/.bashrc"
echo
echo "  2. Verify the install:"
echo "       lsa --help"
echo
echo "  3. Create your first snapshot:"
echo "       ./scripts/mk_snap_and_scan.sh"
