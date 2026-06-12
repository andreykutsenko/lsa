"""PR context gathering for CAB/PTF generation.

The single input to the whole pipeline is the change diff plus the parallel-run
header (Description + Files). This module produces that context from one of two
sources, with no side effects beyond an optional remote temp folder that is
removed after reading:

  1. from_dir  : an already-synced local "<USER>.<PRID>.<ts>" folder
                 (the output of lookup_pr_is.bat). No network access.
  2. fetch     : fetch on the build server by reusing lookup_pr_is.py over ssh,
                 read the diffs back, and delete the remote temp folder.

Only code diffs are ever collected. Data-file diffs and unknown extensions are
skipped so client data never leaves the machine, and a hard size cap bounds what
can be sent downstream.
"""

import glob
import os
import re
import subprocess

# Extensions whose diffs are safe and relevant to send downstream.
CODE_EXTENSIONS = {
    "dfa", "sh", "pl", "py", "procs", "control", "ovl", "ins", "lis", "300",
}

# Hard caps (anti-abuse): bound total and per-file diff size sent to the LLM.
MAX_TOTAL_DIFF_BYTES = 200_000
MAX_FILE_DIFF_BYTES = 60_000

# Remote lookup configuration (matches lookup_pr_is.bat). Override per site.
REMOTE = {
    "ssh_alias": "rhs",
    "csv": "/path/to/pr_lookup.csv",
    "script": "python /path/to/lookup_pr.py",
    "dest_base": "/tmp/pr_context/",
    "paths_json": "/path/to/paths.json",
    "username": "youruser",
}


class ContextError(Exception):
    """Raised when PR context cannot be gathered."""


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def parse_header(report_text):
    """Extract Description, Files and Parallel ID from a <PRID>.txt report."""
    description = ""
    parallel_id = ""
    files = []

    m = re.search(r"^\s*Description:\s*(.+)$", report_text, re.MULTILINE)
    if m:
        description = m.group(1).strip()
    m = re.search(r"^\s*Parallel ID:\s*(\S+)", report_text, re.MULTILINE)
    if m:
        parallel_id = m.group(1).strip()

    in_files = False
    for line in report_text.splitlines():
        if re.match(r"^\s*Files:\s*$", line):
            in_files = True
            continue
        if in_files:
            fm = re.match(r"^\s*\d+\)\s*(.+?)\s*$", line)
            if fm:
                files.append(fm.group(1).strip())
            elif line.strip().startswith("*"):
                break
    return {"description": description, "parallel_id": parallel_id, "files": files}


def _collect_diffs(pairs):
    """pairs: iterable of (filename, diff_text). Apply whitelist + size caps."""
    diffs = []
    skipped = []
    total = 0
    for filename, diff_text in pairs:
        if _ext(filename) not in CODE_EXTENSIONS:
            skipped.append("{} (non-code extension)".format(filename))
            continue
        if not diff_text.strip():
            skipped.append("{} (empty diff)".format(filename))
            continue
        truncated = False
        if len(diff_text) > MAX_FILE_DIFF_BYTES:
            diff_text = diff_text[:MAX_FILE_DIFF_BYTES]
            truncated = True
        if total + len(diff_text) > MAX_TOTAL_DIFF_BYTES:
            skipped.append("{} (total diff size cap reached)".format(filename))
            continue
        total += len(diff_text)
        diffs.append({"file": filename, "diff": diff_text, "truncated": truncated})
    return diffs, skipped


def from_dir(folder):
    """Build context from a local lookup folder (<USER>.<PRID>.<ts>)."""
    if not os.path.isdir(folder):
        raise ContextError("Not a directory: {}".format(folder))

    report = glob.glob(os.path.join(folder, "*.txt"))
    header = {"description": "", "parallel_id": "", "files": []}
    if report:
        with open(report[0], "r", encoding="utf-8", errors="replace") as fh:
            header = parse_header(fh.read())

    pairs = []
    for path in sorted(glob.glob(os.path.join(folder, "diff", "*.diff"))):
        name = os.path.basename(path)[:-len(".diff")]
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            pairs.append((name, fh.read()))
    diffs, skipped = _collect_diffs(pairs)
    return _assemble(header, diffs, skipped)


def fetch(prid, remote=None):
    """Fetch context on the build server via ssh, then remove the temp folder."""
    cfg = dict(REMOTE)
    if remote:
        cfg.update(remote)
    if not re.fullmatch(r"\d{14,}", prid):
        raise ContextError("PRID must be >= 14 digits: {!r}".format(prid))

    remote_cmd = (
        'F=$({script} {csv} {prid} copy {user} {dest} {paths} >/dev/null 2>&1; '
        'ls -dt {dest}{user}.{prid}.* 2>/dev/null | head -1); '
        '[ -n "$F" ] || {{ echo "__NOFOLDER__"; exit 0; }}; '
        'echo "__HEADER__"; cat "$F"/{prid}.txt 2>/dev/null; '
        'echo "__DIFFS__"; '
        'for d in "$F"/diff/*.diff; do [ -e "$d" ] || continue; '
        'echo "__FILE__ $(basename "$d" .diff)"; cat "$d"; done; '
        'rm -rf "$F"'
    ).format(
        script=cfg["script"], csv=cfg["csv"], prid=prid,
        user=cfg["username"], dest=cfg["dest_base"], paths=cfg["paths_json"],
    )
    try:
        proc = subprocess.run(
            ["ssh", cfg["ssh_alias"], remote_cmd],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise ContextError(
            "ssh lookup timed out after 300s (host {!r})".format(cfg["ssh_alias"])
        )
    except OSError as e:
        raise ContextError("ssh could not be started: {}".format(e))
    if proc.returncode != 0:
        raise ContextError("ssh lookup failed: {}".format(proc.stderr.strip()))
    out = proc.stdout
    if "__NOFOLDER__" in out:
        raise ContextError("No parallel folder found on server for PRID {}".format(prid))

    header_text, _, diffs_text = out.partition("__DIFFS__")
    header_text = header_text.split("__HEADER__", 1)[-1]
    header = parse_header(header_text)

    pairs = []
    for chunk in diffs_text.split("__FILE__ ")[1:]:
        name, _, body = chunk.partition("\n")
        pairs.append((name.strip(), body))
    diffs, skipped = _collect_diffs(pairs)
    return _assemble(header, diffs, skipped)


def _assemble(header, diffs, skipped):
    return {
        "parallel_id": header["parallel_id"],
        "description": header["description"],
        "files": header["files"],
        "diffs": diffs,
        "skipped": skipped,
    }


def to_prompt(context):
    """Render the context as the user message text sent to the model."""
    lines = [
        "Parallel ID: {}".format(context["parallel_id"] or "(unknown)"),
        "Description: {}".format(context["description"] or "(none)"),
        "Files: {}".format(", ".join(context["files"]) or "(none)"),
        "",
        "Diffs (prod vs test):",
    ]
    for d in context["diffs"]:
        lines.append("\n### {}{}".format(d["file"], " [TRUNCATED]" if d["truncated"] else ""))
        lines.append(d["diff"].rstrip())
    if context["skipped"]:
        lines.append("\nSkipped (not sent): {}".format("; ".join(context["skipped"])))
    return "\n".join(lines)
