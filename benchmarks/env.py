"""Environment loading and runtime setup for benchmarks."""

from __future__ import annotations

import os
from pathlib import Path

import litellm

# Suppress litellm debug info and provider list spam
os.environ["LITELLM_LOG"] = "ERROR"
litellm.suppress_debug_info = True
litellm.set_verbose = False


def load_env() -> None:
    """Load .env from workspace root (works in Docker and locally)."""
    for candidate in [Path("/workspace/.env"), Path(__file__).parent.parent / ".env"]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if key and val and key not in os.environ:
                    os.environ[key] = val
            break


load_env()
