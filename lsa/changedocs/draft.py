"""LLM drafting step: diff context -> CAB content JSON.

Strictly bounded single-shot call (anti-abuse):
  - no tools given to the model (pure text in, JSON out);
  - one call per ticket, at most one repair retry on malformed JSON;
  - output capped by MAX_OUTPUT_TOKENS;
  - system prompt (rules) sent with prompt caching to cut repeat cost;
  - API key read only from ANTHROPIC_API_KEY, never logged;
  - dry_run shows exactly what would be sent + a cost estimate, no call.

PTF is NOT produced here — it is deterministic (see render.py), so the API is
used only for the CAB prose.
"""

import datetime
import json
import os
from pathlib import Path

from .context import to_prompt

MODELS = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL = "sonnet"
MAX_OUTPUT_TOKENS = 4000

# Approximate USD per 1M tokens. ESTIMATE ONLY — verify against current pricing.
# Real spend is taken from the API response usage and written to usage.log.
PRICE_PER_MTOK = {
    "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
    "claude-opus-4-8": {"in": 15.0, "out": 75.0},
}

_HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_PATH = os.path.join(_HERE, "prompts", "system_cab.md")

# Concise style is applied per-request via the user message (not the cached
# system prompt) so prompt caching keeps working across detail levels.
CONCISE_STYLE_DIRECTIVE = (
    "STYLE OVERRIDE — CONCISE: Make every answer as short as possible — one short "
    "sentence, or a stock answer (\"No.\", \"Manual.\", \"N/A — no the protected platform exposure.\") "
    "where it suffices. Still name the changed file(s) and the exact mechanism, but omit "
    "elaboration, secondary detail, and restated context. Brevity over completeness."
)


def _style_suffix(detail):
    """Return the user-message suffix for the requested detail level."""
    if detail == "concise":
        return "\n\n" + CONCISE_STYLE_DIRECTIVE
    return ""


def _extra_block(extra_context):
    """Return a labeled block for operator-provided context, or empty string."""
    extra = (extra_context or "").strip()
    if not extra:
        return ""
    return (
        "\n\nOperator-provided additional context (use it as ground truth alongside the "
        "diff; still do not fabricate beyond the diff and this):\n" + extra
    )

# usage.log must be writable at runtime; the package dir may be a read-only
# install path, so default to a per-user runtime location under ~/.lsa.
USAGE_LOG_PATH = str(Path.home() / ".lsa" / "changedocs" / "usage.log")


class DraftError(Exception):
    """Raised when the CAB draft cannot be produced."""


def _load_system_prompt():
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def estimate_tokens(text):
    """Rough token estimate (~4 chars/token) for dry-run cost preview."""
    return max(1, len(text) // 4)


def _estimate_cost(model_id, in_tokens, out_tokens):
    price = PRICE_PER_MTOK.get(model_id, {"in": 0.0, "out": 0.0})
    return (in_tokens * price["in"] + out_tokens * price["out"]) / 1_000_000


def dry_run(context_prompt, model="sonnet", detail="concise", extra_context=""):
    """Return what would be sent and an estimated cost; make no API call."""
    model_id = MODELS.get(model, MODELS[DEFAULT_MODEL])
    context_prompt = context_prompt + _extra_block(extra_context) + _style_suffix(detail)
    system = _load_system_prompt()
    system_tokens = estimate_tokens(system)
    context_tokens = estimate_tokens(context_prompt)
    in_tok = system_tokens + context_tokens
    est = _estimate_cost(model_id, in_tok, MAX_OUTPUT_TOKENS)
    return {
        "model_id": model_id,
        "system_tokens": system_tokens,
        "context_tokens": context_tokens,
        "estimated_input_tokens": in_tok,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "estimated_cost_usd": est,
        "context_prompt": context_prompt,
    }


def _log_usage(model_id, files, usage, usage_log_path=USAGE_LOG_PATH):
    line = "{ts}\tmodel={model}\tin={inp}\tout={out}\test_usd={cost:.4f}\tfiles={files}\n".format(
        ts=datetime.datetime.now().isoformat(timespec="seconds"),
        model=model_id,
        inp=usage.get("input_tokens", 0),
        out=usage.get("output_tokens", 0),
        cost=_estimate_cost(model_id, usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
        files=",".join(files),
    )
    log_path = Path(usage_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line)


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(text)


def draft_cab(context, model="sonnet", usage_log_path=USAGE_LOG_PATH, api_key=None,
              detail="concise", extra_context=""):
    """Single bounded API call. Returns the CAB content dict for generate_cab.

    The key is taken from the explicit `api_key` argument when provided,
    otherwise from the ANTHROPIC_API_KEY environment variable. It is never
    logged or persisted.
    """
    try:
        import anthropic
    except ImportError:
        raise DraftError("anthropic SDK not installed. Run: pip install anthropic")

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise DraftError(
            "No API key provided. Enter one in the Change Docs panel or set ANTHROPIC_API_KEY."
        )

    model_id = MODELS.get(model, MODELS[DEFAULT_MODEL])
    system = _load_system_prompt()
    user_text = to_prompt(context) + _extra_block(extra_context) + _style_suffix(detail)

    client = anthropic.Anthropic(api_key=api_key)
    system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _call(extra=""):
        return client.messages.create(
            model=model_id,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=system_blocks,
            messages=[{"role": "user", "content": user_text + extra}],
        )

    usage = {"input_tokens": 0, "output_tokens": 0}

    def _track(resp):
        usage["input_tokens"] += getattr(resp.usage, "input_tokens", 0)
        usage["output_tokens"] += getattr(resp.usage, "output_tokens", 0)

    try:
        resp = _call()
        _track(resp)
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        try:
            content = _parse_json(raw)
        except json.JSONDecodeError:
            resp = _call("\n\nReturn ONLY the JSON object, no other text.")
            _track(resp)
            raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            try:
                content = _parse_json(raw)
            except json.JSONDecodeError:
                raise DraftError("Model returned malformed JSON twice; not retrying further.")
    except anthropic.APIError as e:
        raise DraftError("Anthropic API call failed: {}".format(e))
    finally:
        if usage["input_tokens"] or usage["output_tokens"]:
            _log_usage(model_id, [d["file"] for d in context["diffs"]], usage,
                       usage_log_path=usage_log_path)

    if "sections" not in content:
        raise DraftError("Model output missing 'sections'.")
    return content
