"""Source file reading utilities for benchmarks."""

from __future__ import annotations

from pathlib import Path

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".h",
}


def _is_ignored_path(src_file: Path) -> bool:
    return any(
        part.startswith(".")
        or part
        in (
            "node_modules",
            "__pycache__",
            "venv",
            ".venv",
            "dist",
            "build",
            ".git",
            ".idea",
            ".tox",
            ".mypy_cache",
        )
        for part in src_file.parts
    )


def read_all_source_files(app_path: Path, max_chars: int = 0) -> str:
    """Read all source files from a project directory."""
    sources = []
    total = 0
    for src_file in sorted(app_path.rglob("*")):
        if not src_file.is_file():
            continue
        if src_file.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if _is_ignored_path(src_file):
            continue
        content = src_file.read_text(encoding="utf-8", errors="ignore")
        rel = src_file.relative_to(app_path)
        sources.append(f"# === {rel} ===\n{content}")
        total += len(content)
        if max_chars and total > max_chars:
            sources.append(f"# ... truncated at {max_chars} chars ({total} total)")
            break
    return "\n\n".join(sources)


def count_raw_code_chars(app_path: Path) -> int:
    """Count total characters in all source files."""
    total = 0
    for src_file in app_path.rglob("*"):
        if src_file.is_file() and src_file.suffix.lower() in SOURCE_EXTENSIONS:
            if not _is_ignored_path(src_file):
                total += len(src_file.read_text(encoding="utf-8", errors="ignore"))
    return total
