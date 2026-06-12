"""Change Docs engine: CAB / PTF / QA generation from a parallel-run diff.

Pipeline:  context (diff + header)  ->  draft CAB via Claude API  ->  render docx
The PTF and QA checklists are rendered deterministically; they make no API call.

Ported from the standalone `change_docs` tool into the LSA package so the web UI
can reuse it via clean intra-package imports (no sys.path manipulation).
"""

from . import context, draft, render

__all__ = ["context", "draft", "render", "ticket_id_for"]


def ticket_id_for(ctx, override=""):
    """Derive a ticket id from the context (Description token / parallel id)."""
    if override:
        return override
    desc = ctx.get("description", "")
    token = desc.split()[0] if desc else ""
    return token or ctx.get("parallel_id", "") or "TICKET"
