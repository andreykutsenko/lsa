# LSA Quick Start

## Prerequisites

- **VPN must be active.** All scripts connect to the RHS Linux server over the corporate
  network. Without VPN, SSH and rsync will fail.

- **SSH private key** — obtain the `id_rsa` key for the RHS server and place it somewhere
  accessible (e.g. `~/id_rsa`) **before** running setup.

- **Terminal:**
  - Linux / macOS — use your regular terminal.
  - Windows — open **WSL** (Windows Subsystem for Linux) and run all commands inside WSL.

## 1. Install

```bash
git clone git@github.com:andreykutsenko/lsa.git
cd lsa
./scripts/setup.sh
```

During setup:
- Press **Enter** to accept the default RHS host and user.
- Enter the path to your SSH private key when prompted (e.g. `~/id_rsa`).

Setup will:
- Install [UV](https://docs.astral.sh/uv/) package manager (if not present)
- Sync LSA Python dependencies
- Configure SSH key authentication (`~/.ssh/config`, `Host rhs`)
- Write config to `~/.lsa/config.yaml`

## 2. Create Snapshot

Snapshot = local copy of production scripts pulled from the RHS server via rsync.
Re-run **only after a deployment to production**, not daily.

```bash
./scripts/lsa-snap.sh
```

At the end of the output the script prints the snapshot path:

```
SNAP=/home/kts/snapshots/rhs_snapshot_20260227_143012
```

Copy the **exact absolute path** from that line and export it:

```bash
export SNAP=/home/kts/snapshots/rhs_snapshot_20260227_143012
```

> **Important:** paste the full path as-is — no quotes, no extra spaces, no `~`.
> Tilde (`~`) is not expanded inside quotes and causes a "path does not exist" error.
> Use the path exactly as printed by `lsa-snap.sh`.
>
> `$SNAP` must be set in every new terminal session before running LSA commands.

## 3. Daily Workflow

```bash
# Activate LSA environment
source .venv/bin/activate

# Set SNAP — paste the exact path printed by lsa-snap.sh (no quotes, no ~)
export SNAP=/home/kts/snapshots/rhs_snapshot_20260227_143012

# Find a bundle by keyword
lsa plan $SNAP --title mocume2

# AI deep-analysis prompt (output saved to file)
lsa plan $SNAP --title mocume2 --deep

# Copy files to a workspace for a Change Request
./scripts/lsa-workspace.sh --snap $SNAP --title mocume2
```

## Cheat Sheet

| Task | Command |
|------|---------|
| First-time setup | `./scripts/setup.sh` |
| Create snapshot | `./scripts/lsa-snap.sh` |
| Activate LSA | `source .venv/bin/activate` |
| Set snapshot path | `export SNAP=~/snapshots/rhs_snapshot_...` |
| Find bundle by keyword | `lsa plan $SNAP --title <keyword>` |
| Find bundle by CID+JobID | `lsa plan $SNAP --cid WCCU --jobid ds1` |
| AI deep analysis prompt | `lsa plan $SNAP --title <keyword> --deep` |
| Mermaid diagram | `lsa plan $SNAP --title <keyword> --mermaid` |
| JSON output | `lsa plan $SNAP --title <keyword> --json` |
| Copy files to workspace | `./scripts/lsa-workspace.sh --snap $SNAP --title <keyword>` |
| Full snapshot + import | `./scripts/mk_snap_and_scan.sh` |
| Full workspace + SSH | `./scripts/mk_ticket_ws.sh TICKET --snap $SNAP --title "..."` |

## Troubleshooting

### Activating LSA environment

```bash
source .venv/bin/activate
lsa --help
```

If `.venv` doesn't exist, re-run setup:

```bash
./scripts/setup.sh
```

### SSH connection issues

`setup.sh` configures `~/.ssh/config` with `Host rhs`. Test with:

```bash
ssh rhs "echo OK"
```

If it fails:
- Make sure VPN is active.
- Check that `~/.ssh/id_rsa` exists and has permissions `600`.
- Re-run `./scripts/setup.sh` to reconfigure.

### rsync asks for a password

This means the SSH key is not being picked up. Verify:

```bash
ls -la ~/.ssh/id_rsa    # must exist, permissions 600
ssh rhs "echo OK"       # must succeed without a password prompt
```

### Slow rsync

First snapshot copies everything and can take 10–15 minutes.
Subsequent runs are incremental and much faster.

### Snapshot is N days old

This is a reminder, not an error. Update the snapshot only when
production scripts have actually changed (after a deployment):

```bash
./scripts/lsa-snap.sh
```
