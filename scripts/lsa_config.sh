#!/usr/bin/env bash
# lsa_config.sh
#
# Loads LSA configuration from ~/.lsa/config.yaml into environment variables.
# Source this file from other scripts:
#
#   source "$(dirname "$0")/lsa_config.sh"
#
# Config file (~/.lsa/config.yaml) example:
#   rhs_host: "linux-server.company.com"
#   rhs_user: "jsmith"
#   ssh_auth: "password"
#   snaproot: "/home/jsmith/snapshots"
#   workroot: "/home/jsmith/workspaces"
#
# Already-set env vars are NOT overwritten (safe to override before sourcing).

_lsa_config_parse_key() {
  local key="$1" file="$2"
  grep "^${key}:" "$file" | sed "s/^${key}:[[:space:]]*//" | tr -d '"'
}

load_lsa_config() {
  local config_file="$HOME/.lsa/config.yaml"

  if [[ -f "$config_file" ]]; then
    RHS_HOST="${RHS_HOST:-$(_lsa_config_parse_key rhs_host "$config_file")}"
    RHS_USER="${RHS_USER:-$(_lsa_config_parse_key rhs_user "$config_file")}"
    SSH_AUTH="${SSH_AUTH:-$(_lsa_config_parse_key ssh_auth "$config_file")}"
    SNAPROOT="${SNAPROOT:-$(_lsa_config_parse_key snaproot "$config_file")}"
    WORKROOT="${WORKROOT:-$(_lsa_config_parse_key workroot "$config_file")}"
  fi

  SSH_TARGET="${RHS_USER:+$RHS_USER@}${RHS_HOST}"

  if [[ "${SSH_AUTH:-}" == "password" ]]; then
    if command -v sshpass >/dev/null 2>&1; then
      RSYNC_RSH="sshpass -f $HOME/.lsa/.rhs_pass ssh"
    else
      echo "[WARN] sshpass not found — rsync will prompt for password each time" >&2
      RSYNC_RSH=""
    fi
  else
    RSYNC_RSH=""
  fi

  export RHS_HOST RHS_USER SSH_AUTH SNAPROOT WORKROOT SSH_TARGET RSYNC_RSH
}

load_lsa_config
