"""Parse script files to find calls to other known scripts."""
from pathlib import Path


def find_script_calls(content: str, known_basenames: set[str]) -> list[str]:
    """Return basenames of known scripts mentioned in content.

    Uses simple basename presence check — if a script's filename appears
    in another script's content, it is considered called.
    """
    return [name for name in known_basenames if name in content]


def build_call_graph(
    script_paths: dict[str, Path],
    depth_limit: int = 3,
) -> dict[str, list[str]]:
    """Build call graph from a mapping of {basename: absolute_path}.

    Returns {caller_basename: [called_basename, ...]} for all pairs
    where the caller's content mentions the called script's basename.
    Stops recursion at depth_limit to avoid infinite loops.
    """
    known_basenames = set(script_paths.keys())
    graph: dict[str, list[str]] = {}

    def _recurse(basename: str, depth: int, visited: set[str]) -> None:
        if depth > depth_limit or basename in visited:
            return
        visited.add(basename)
        path = script_paths.get(basename)
        if not path or not path.exists():
            return
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        calls = find_script_calls(content, known_basenames - {basename})
        if calls:
            graph[basename] = calls
        for called in calls:
            _recurse(called, depth + 1, visited)

    for basename in list(known_basenames):
        _recurse(basename, 0, set())

    return graph
