# LSA Quick Start

## 1. Install

```bash
git clone <repo-url>
cd lsa_project
./scripts/setup.sh
```

Setup will:
- Install [UV](https://docs.astral.sh/uv/) package manager (if not present)
- Sync LSA dependencies
- Configure SSH key authentication for RHS server (`~/.ssh/config`)
- Write config to `~/.lsa/config.yaml`

## 2. Create Snapshot

Snapshot = copy of production scripts from RHS server.
Re-run only after a deployment to production (not daily).

```bash
./scripts/lsa-snap.sh
```

The script will print the `SNAP=...` path. Save it for the next steps.

## 3. Daily Workflow

```bash
source .venv/bin/activate

# Look at a bundle (quick)
lsa plan $SNAP --title mocume2

# AI prompt for deep analysis (saved to file)
lsa plan $SNAP --title mocume2 --deep

# Copy files for a Change Request
./scripts/lsa-workspace.sh --snap $SNAP --title mocume2
```

## Cheat Sheet

| Task | Command |
|------|---------|
| First-time setup | `./scripts/setup.sh` |
| Create snapshot | `./scripts/lsa-snap.sh` |
| Activate LSA | `source .venv/bin/activate` |
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

setup.sh configures `~/.ssh/config` with `Host rhs`. Test with:

```bash
ssh rhs "echo OK"
```

If it fails, check your SSH key and `~/.ssh/config` settings.

### Slow rsync

First run copies everything and can take 10-15 minutes.
Subsequent runs are incremental and much faster.

### Snapshot is N days old

This is a reminder, not an error. Update the snapshot only when
production scripts have actually changed (after a deployment):

```bash
./scripts/lsa-snap.sh
```
