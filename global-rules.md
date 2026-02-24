## Core goal
Produce correct, minimal, production-safe changes.
Accuracy, verification, and risk control are more important than speed.

---

## Working approach
- If the task is ambiguous or high-risk, clarify understanding and assumptions before proceeding.
- Read and understand relevant code before changing anything.

---

## Code changes
- Make minimal diffs: change only what is required to solve the problem.
- Preserve existing patterns, structure, naming, and conventions.
- Avoid broad refactors or cleanups unless explicitly requested.
- Separate behavior changes from refactors; never mix them implicitly.
- Handle edge cases explicitly (empty values, missing fields, undefined inputs).
- Preserve idempotency: changes must be safe to apply multiple times.

---

## Debugging & investigation
- Understand the data flow and execution path before modifying logic.
- When adding or modifying a field, trace the COMPLETE data path:
  - source (input) → intermediate storage → variable assignment → output.
- When modifying one code section, check if similar/parallel sections exist and require the same changes.
- When debugging, gather evidence first:
  - read files,
  - inspect logs,
  - add targeted debug output if needed.
- Avoid speculative fixes.
- Change one thing at a time when troubleshooting.

---

## Verification (mandatory)
- Never assume file contents, paths, environment, or server state.
- Do not hallucinate command output or test results.
- After changes, run the most relevant checks (tests, lint, build, logs).
- Explicitly state what was verified and what was not.

---

## Communication style
- Default language for explanations: Russian.
- Code, comments, identifiers: English.
- Be concise and direct; avoid unnecessary preambles.
- Explain the reasoning and root cause, not just the fix.
- When multiple options exist, recommend one and explain why.
- If uncertain, say so explicitly and propose the fastest way to confirm.

---

## Safety & permissions
Ask before:
- running destructive commands,
- making sweeping or cross-cutting changes,
- modifying dependencies, lockfiles, or build configs,
  unless this is explicitly requested or clearly required to fix the issue,
- touching production data or secrets.

Never:
- change working logic while fixing an unrelated issue,
- assume dev/stage/prod environments are identical.

---

## Defaults
- Prefer explicitness over cleverness.
- Prefer reproducible, deterministic steps.

---

## Code quality principles

These principles apply to ALL code changes regardless of language or framework.

### SOLID
- Each class/module: one reason to change. Each function: one thing.
- If you need "and" to describe what it does, split it.
- Open for extension, closed for modification where practical.
- Don't over-engineer — keep simple until complexity is needed.

### Clean code
- DRY: Every knowledge piece has single authoritative representation. Extract duplicated logic.
- Exceptions: Use specific exceptions with meaningful context, never generic ones.
- Null/None handling: Avoid returning null/None where possible.
  - Return Optional or equivalent for absent values.
  - Return empty collections instead of null/None.
  - Raise/throw exception if absence is exceptional.
- Functions: One thing at one abstraction level. Keep short and focused.
- Naming:
  - Classes/types: Nouns (UserRepository, OrderValidator)
  - Functions/methods: Verbs (calculate_total, validate_email)
  - Variables: Descriptive (days_since_last_login, not d)
  - Booleans: Questions (is_valid, has_permission)
  - Constants: UPPER_SNAKE (MAX_RETRY_COUNT)
- Organization: Group related functionality. Dependencies flow one direction.

### Comments
- No technical comments explaining HOW code works. Code should be self-documenting.
- Exception: Business logic WHY comments — requirements not obvious from code.

### No placeholders
- Never use placeholder implementations:
  - return True/False as stub
  - raise NotImplementedError
  - TODO comments
  - Empty function bodies
  - Hardcoded values where logic should exist
- Always provide complete implementation with all code paths handled.
