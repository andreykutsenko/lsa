# LSA (Legacy Script Archaeologist) — status @ 2026-01-27

## Goal
Local CLI tool to analyze a legacy snapshot (master/procs/control/insert/docdef/logs) and produce:
- execution graph from .procs
- log-to-proc matching
- single-block "context pack" for pasting into an IDE for deeper work

## Repo layout
- Repo root: lsa_project/
- Python package: tools/lsa/lsa/
- Snapshot example:
  /mnt/c/Users/akutsenko/code/rhs_snapshot_project/rhs_snapshot_20260123_172741
- Snapshot DB:
  <SNAP>/.lsa/lsa.sqlite  (one DB per snapshot)

## Commands
- lsa scan <SNAP>
- lsa explain <SNAP> --log <LOG> [--debug] [--proc <procname>]
- lsa search <SNAP> "<query>"
- lsa import-histories <SNAP>
- lsa import-codes <SNAP> --pdf <PDF>

## Papyrus codes KB
- Global PDF path example:
  /mnt/c/Users/akutsenko/code/rhs_snapshot_project/refs/papyrus/Papyrus_DocExec_message_codes.pdf
- Imported into snapshot DB table: message_codes

## External config signals (rules)
- External signals rules: tools/lsa/lsa/rules/external_signals.yaml
- Example: InfoTrac message manager failure detection
  Pattern: "No data found from message_id: <id> in infotrac db"
  + JSON: "success": false
- Expected: should surface in context pack section "3d. EXTERNAL CONFIG SIGNALS" and top hypotheses.

## Known gotcha: entrypoint vs module run
- Reliable dev run:
  python -m lsa.cli explain <SNAP> --log <LOG>
- If `lsa explain` behaves differently, reinstall editable package into repo venv:
  python -m pip install -e ./tools/lsa --no-user

## Next steps
1) Remove extra venvs (keep only repo root .venv)
2) Add incidents persistence on `lsa explain` (store parsed_json + top node + timestamp)
3) Grow external signals rules library based on real trace logs
