"""External terminal and tool launcher for LSA Web UI."""

import shutil
import subprocess
from pathlib import Path


def launch_terminal(cmd: str, cwd: str) -> int | None:
    """Launch external terminal window with command.

    Tries common Linux terminal emulators in order.
    Returns PID of launched process, or None if no terminal found.
    """
    terminals = [
        "x-terminal-emulator",
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "xterm",
    ]
    terminal = None
    for t in terminals:
        if shutil.which(t):
            terminal = t
            break

    if terminal is None:
        return None

    if terminal == "gnome-terminal":
        args = [terminal, "--", "bash", "-c", cmd]
    else:
        args = [terminal, "-e", "bash", "-c", cmd]

    proc = subprocess.Popen(args, cwd=cwd, start_new_session=True)
    return proc.pid


def launch_claude(snapshot_path: Path, prompt_file: Path | None = None) -> int | None:
    """Launch Claude Code in a terminal at the snapshot directory."""
    if prompt_file and prompt_file.exists():
        cmd = f"cat '{prompt_file}' | claude; exec bash"
    else:
        cmd = "claude; exec bash"
    return launch_terminal(cmd, cwd=str(snapshot_path))


def launch_cursor(snapshot_path: Path) -> int | None:
    """Launch Cursor IDE at the snapshot directory."""
    cursor_bin = shutil.which("cursor")
    if cursor_bin is None:
        return None
    proc = subprocess.Popen(
        [cursor_bin, str(snapshot_path)],
        start_new_session=True,
    )
    return proc.pid
