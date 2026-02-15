"""Central repair checklist consumed by LLM benchmark."""

BROKEN_AREAS = [
    'Fix mutable default arguments and race conditions.',
    'Replace insecure eval/SQL interpolation with safe alternatives.',
    'Eliminate broad except blocks that swallow diagnostics.',
    'Repair off-by-one calculations and invalid fallbacks.',
    'Make async flows non-blocking and deterministic.',
    'Add robust tests for edge cases and parser behavior.',
]
