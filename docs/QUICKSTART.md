# LSA Quick Start

## 1. Install

```bash
git clone <repo-url>
cd lsa_project
./scripts/setup.sh
```

Setup installs:
- [UV](https://docs.astral.sh/uv/) package manager (if not present)
- LSA dependencies synced via `uv sync`
- Config file `~/.lsa/config.yaml` with SSH settings

## 2. Create Snapshot

Snapshot = copy of production scripts from RHS server.
Re-run only after a deployment to production (not daily).

```bash
./scripts/lsa-snap.sh
```

The script will print the `SNAP=...` path. Save it for the next steps.

## 3. Daily Workflow

### Look at a bundle (quick)

```bash
uv run --project tools/lsa lsa plan $SNAP --title mocume2
```

### AI prompt + Mermaid diagram (deep analysis)

```bash
uv run --project tools/lsa lsa plan $SNAP --title mocume2 --deep
```

### Copy files for a Change Request

```bash
./scripts/lsa-workspace.sh --snap $SNAP --title mocume2
```

## Cheat Sheet

| Task | Command |
|------|---------|
| First-time setup | `./scripts/setup.sh` |
| Create snapshot | `./scripts/lsa-snap.sh` |
| Find bundle by keyword | `uv run --project tools/lsa lsa plan $SNAP --title <keyword>` |
| Find bundle by CID+JobID | `uv run --project tools/lsa lsa plan $SNAP --cid WCCU --jobid ds1` |
| AI analysis prompt | `uv run --project tools/lsa lsa plan $SNAP --title <keyword> --deep` |
| Mermaid diagram | `uv run --project tools/lsa lsa plan $SNAP --title <keyword> --mermaid` |
| JSON output | `uv run --project tools/lsa lsa plan $SNAP --title <keyword> --json` |
| Copy files to workspace | `./scripts/lsa-workspace.sh --snap $SNAP --title <keyword>` |
| Full snapshot + import | `./scripts/mk_snap_and_scan.sh` |
| Full workspace + SSH | `./scripts/mk_ticket_ws.sh TICKET --snap $SNAP --title "..."` |

## Troubleshooting

### Running LSA commands

LSA commands are run via UV:

```bash
uv run --project tools/lsa lsa --help
uv run --project tools/lsa lsa plan $SNAP --title <keyword>
```

Or use the wrapper scripts directly:
```bash
./scripts/lsa-snap.sh
./scripts/lsa-workspace.sh --snap $SNAP --title <keyword>
```

### SSH password prompt every time

Install `sshpass` for automatic password authentication:

```bash
sudo apt install sshpass
```

Then re-run `./scripts/setup.sh` to reconfigure.

### Slow rsync

First run copies everything and can take 10-15 minutes.
Subsequent runs are incremental and much faster.

### Snapshot is N days old

This is a reminder, not an error. Update the snapshot only when
production scripts have actually changed (after a deployment):

```bash
./scripts/lsa-snap.sh
```
