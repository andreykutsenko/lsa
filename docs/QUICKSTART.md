# LSA Quick Start

**LSA** finds all files related to a batch job (scripts, controls, DFA templates) and packages
them into an AI-ready prompt — so you can ask Claude or Cursor to explain the job and help debug it.

---

## Prerequisites

- **VPN must be active** — all scripts connect to the RHS server over the corporate network
- **SSH private key** — get `id_rsa` from your team lead and save it (e.g. `~/id_rsa`)
- **Terminal:**
  - Linux / macOS — regular terminal
  - Windows — open **WSL** and run everything inside it

---

## Step 1 — Install (once)

```bash
git clone git@github.com:andreykutsenko/lsa.git
cd lsa
./scripts/setup.sh
```

When prompted: press **Enter** for the default server host/user, then enter the path to your SSH key.

Setup installs all dependencies and writes your config to `~/.lsa/config.yaml`.

---

## Step 2 — Create a Snapshot (when needed)

A **snapshot** is a local copy of all production scripts. LSA builds its search database on top of it.

```bash
./scripts/lsa-snap.sh
```

The script prints the snapshot path at the end — **copy it**:

```
SNAP=/home/you/snapshots/rhs_snapshot_20260225_114334
```

---

## Step 3 — Daily Workflow

**Activate LSA and set your snapshot path** (do this in every new terminal session):

```bash
cd lsa
source .venv/bin/activate
SNAP=<paste your snapshot path here>
```

### Find files and generate an AI prompt

Use CID (4 letters) + Job ID as the `--title` keyword — e.g. `mocume2` for CID `mocu` + job `me2`.

```bash
# See which files belong to a job
lsa plan $SNAP --title mocume2

# Generate an AI prompt for deep analysis (path to saved file is printed)
lsa plan $SNAP --title mocume2 --deep
```

Open the saved file, copy its contents, paste into Cursor or Claude.

### Copy files to a workspace

Provide the ticket ID as the first argument — the workspace folder will be named after it.

```bash
# From snapshot (fast, for reading/reviewing)
./scripts/lsa-workspace.sh INC0123456 --snap $SNAP --title mocume2

# From the production server (when you need to edit and push back)
./scripts/lsa-workspace.sh INC0123456 --snap $SNAP --title mocume2 --ssh-copy
```

> `--ssh-copy` copies files one by one via SSH. On a normal office/VPN connection it takes
> under a minute for a typical job.

The script prints the workspace path at the end. Open it in your IDE.

### Alternative: Web UI

Instead of the command line, you can use the browser-based interface:

```bash
lsa serve $SNAP
```

This opens a web UI at `http://127.0.0.1:18900`.

Recommended operator flow:
- **Snapshot** — select an existing snapshot or create a new one
- **Bundle** — run `Find scope`, choose the best candidate, then use **Current scope**
- **Current scope actions** — `Open files`, `Create workspace`, `Copy file list`, `Generate prompt`, `Open diagram`
- **Search** — switch between `Files`, `Knowledge`, or `All`; use `Path` vs `Content`; choose `Current scope` vs `Whole snapshot`

Prompt generation in the web UI supports two scenarios:
- `Incident analysis`
- `Change request analysis`

> On WSL, created snapshots and workspaces show a clickable Windows Explorer path.
>
> After restarting `lsa serve` or reloading the page, reselect the snapshot and run `Find scope` again. Current scope is not persisted across restarts in V1.

---

## Cheat Sheet

| Task | Command |
|------|---------|
| One-time setup | `./scripts/setup.sh` |
| Create/refresh snapshot | `./scripts/lsa-snap.sh` |
| Activate LSA | `source .venv/bin/activate` |
| Set snapshot path | `SNAP=<path from lsa-snap.sh>` |
| See file scope for a job | `lsa plan $SNAP --title <cid+jobid>` |
| AI deep-analysis prompt | `lsa plan $SNAP --title <cid+jobid> --deep` |
| Copy files (from snapshot) | `./scripts/lsa-workspace.sh <TICKET> --snap $SNAP --title <cid+jobid>` |
| Copy files (from prod server) | `./scripts/lsa-workspace.sh <TICKET> --snap $SNAP --title <cid+jobid> --ssh-copy` |
| Start web UI | `lsa serve $SNAP` |
| Start web UI (no snapshot) | `lsa serve` |

---

## Troubleshooting

**`lsa: command not found`** — activate the environment first:
```bash
source .venv/bin/activate
```

**`ssh rhs` asks for a password** — SSH key not configured. Re-run setup:
```bash
./scripts/setup.sh
```

**`Error: Database not found`** — snapshot has no DB yet. Re-run:
```bash
./scripts/lsa-snap.sh
```

**Snapshot is N days old** — reminder only, not an error. Update only when needed.

**First snapshot is slow** — it copies everything and can take 10–15 minutes. Subsequent runs are incremental and much faster.

**`lsa serve` shows "Web UI requires extra dependencies"** — install the web extras:
```bash
pip install 'lsa[web]'
```
