"""Configuration helpers for benchmarks."""

from __future__ import annotations

import os
from pathlib import Path


def get_model() -> str:
    """Get LLM model ID in format provider/model."""
    return os.getenv("MODEL_ID", "openrouter/meta-llama/llama-3.2-3b-instruct:free")


def get_max_tokens() -> int:
    return int(os.getenv("MAX_TOKENS", "4096"))


def get_temperature() -> float:
    return float(os.getenv("TEMPERATURE", "0.1"))


def get_target_project() -> Path:
    """Return TARGET_PROJECT path from env, preferring Docker /project mount when present."""
    target = os.getenv("TARGET_PROJECT", "").strip()
    docker_project = Path("/project")

    if target:
        p = Path(target)

        if p.is_absolute() and p.exists():
            return p

        if docker_project.exists():
            return docker_project

        if p.exists():
            return p

        raise FileNotFoundError(f"TARGET_PROJECT not found: {target}")

    if docker_project.exists():
        return docker_project

    return get_sample_app_path()


def get_problem_description() -> str:
    """Return PROBLEM_DESCRIPTION from env or empty string for auto-detect."""
    return os.getenv("PROBLEM_DESCRIPTION", "").strip()


def get_sample_app_path() -> Path:
    """Return path to sample-app, works both in Docker and locally."""
    candidates = [
        Path("/workspace/sample-app"),
        Path(__file__).parent.parent / "sample-app",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("sample-app not found")
