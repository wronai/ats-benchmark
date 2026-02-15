"""Benchmark: ast-grep - Structural code search for LLM context compression."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.common import (
    ANALYSIS_SYSTEM_PROMPT,
    ANALYSIS_USER_PROMPT_TEMPLATE,
    BenchmarkResult,
    call_llm,
    count_raw_code_chars,
    evaluate_response_quality,
    get_target_project,
    save_result,
)


def _run_ast_grep(pattern: str, app_path: Path, lang: str = "python") -> list:
    """Run ast-grep with given pattern and return matches."""
    try:
        result = subprocess.run(
            ["ast-grep", "scan", "--pattern", pattern, "--json", "-l", lang, str(app_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode in (0, 1):  # 1 = matches found
            import json
            lines = result.stdout.strip().split("\n")
            matches = []
            for line in lines:
                if line.strip():
                    try:
                        matches.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return matches
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def _analyze_with_astgrep(app_path: Path) -> str:
    """Use ast-grep patterns to extract structural information."""
    lines = ["# ast-grep Structural Analysis"]

    # Define patterns for common code structures
    patterns = [
        ("function_definitions", "def $NAME($$$PARAMS): $$$BODY", "Functions"),
        ("class_definitions", "class $NAME($$$BASES): $$$BODY", "Classes"),
        ("async_functions", "async def $NAME($$$PARAMS): $$$BODY", "Async Functions"),
        ("exception_handlers", "try: $$$BODY except $$$EXCEPT: $$$HANDLER", "Exception Handling"),
        ("list_comprehensions", "[$ITEM for $VAR in $ITER]", "List Comprehensions"),
        ("dict_patterns", "{$KEY: $VALUE for $VAR in $ITER}", "Dict Comprehensions"),
        ("decorators", "@$DECORATOR\ndef $NAME($$$PARAMS):", "Decorators"),
        ("property_decorators", "@property\ndef $NAME(self):", "Properties"),
        ("dataclasses", "@dataclass\nclass $NAME:", "Dataclasses"),
    ]

    all_matches = {}

    for key, pattern, label in patterns:
        matches = _run_ast_grep(pattern, app_path)
        all_matches[key] = matches

        if matches:
            lines.append(f"\n## {label} ({len(matches)} found)")
            for match in matches[:20]:  # Limit output
                try:
                    meta = match.get("meta", {})
                    file_path = meta.get("file", "")
                    line_num = meta.get("range", {}).get("start", {}).get("line", 0)

                    # Extract matched variables
                    variables = match.get("match", {})
                    if variables:
                        var_str = ", ".join([f"{k}={v}" for k, v in list(variables.items())[:3]])
                        lines.append(f"  - {file_path}:{line_num} ({var_str})")
                    else:
                        lines.append(f"  - {file_path}:{line_num}")
                except Exception:
                    lines.append(f"  - {str(match)[:80]}")

            if len(matches) > 20:
                lines.append(f"  ... and {len(matches) - 20} more")

    # Extract function signatures with types
    signature_pattern = "def $NAME($$$PARAMS) -> $RET:"
    sig_matches = _run_ast_grep(signature_pattern, app_path)
    if sig_matches:
        lines.append(f"\n## Typed Functions ({len(sig_matches)} found)")
        for match in sig_matches[:15]:
            try:
                m = match.get("match", {})
                name = m.get("NAME", "?")
                ret = m.get("RET", "?")
                lines.append(f"  - {name}() -> {ret}")
            except Exception:
                pass

    # Security patterns
    security_patterns = [
        ("sql_injection", "cursor.execute($$$)", "SQL Execution"),
        ("eval_usage", "eval($$$)", "Eval Usage"),
        ("exec_usage", "exec($$$)", "Exec Usage"),
        ("subprocess_calls", "subprocess.$METHOD($$$)", "Subprocess Calls"),
    ]

    lines.append("\n## Security Patterns")
    for key, pattern, label in security_patterns:
        matches = _run_ast_grep(pattern, app_path)
        if matches:
            lines.append(f"  {label}: {len(matches)} occurrences")

    return "\n".join(lines) if len(lines) > 1 else "[ast-grep: no patterns matched]"


def _fallback_analysis(app_path: Path) -> str:
    """Fallback when ast-grep is not available."""
    lines = ["# ast-grep Structural Analysis (Fallback)"]
    lines.append("[ast-grep CLI not available, using manual pattern matching]")

    import ast

    _SKIP_DIRS = {"__pycache__", "venv", ".venv", "dist", "build", ".git"}

    stats = {
        "functions": 0,
        "classes": 0,
        "async_functions": 0,
        "decorators": 0,
        "list_comps": 0,
        "dict_comps": 0,
        "try_blocks": 0,
    }

    for py_file in sorted(app_path.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    stats["functions"] += 1
                    if node.decorator_list:
                        stats["decorators"] += len(node.decorator_list)
                elif isinstance(node, ast.AsyncFunctionDef):
                    stats["async_functions"] += 1
                elif isinstance(node, ast.ClassDef):
                    stats["classes"] += 1
                elif isinstance(node, ast.ListComp):
                    stats["list_comps"] += 1
                elif isinstance(node, ast.DictComp):
                    stats["dict_comps"] += 1
                elif isinstance(node, ast.Try):
                    stats["try_blocks"] += 1
        except SyntaxError:
            continue

    lines.append("\n## Statistics")
    for key, val in stats.items():
        lines.append(f"  {key}: {val}")

    return "\n".join(lines)


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_target_project()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Structural analysis with ast-grep
    analysis_start = time.time()

    # Check if ast-grep is available
    try:
        subprocess.run(["ast-grep", "--version"], capture_output=True, timeout=5)
        context = _analyze_with_astgrep(app_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        context = _fallback_analysis(app_path)

    analysis_duration = time.time() - analysis_start

    # Phase 2: Send to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="ast-grep (structural search)",
        context=context,
    )

    llm_result = call_llm(prompt, system=ANALYSIS_SYSTEM_PROMPT)

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="ast-grep",
        target_project=str(app_path),
        tokens_in=llm_result["tokens_in"],
        tokens_out=llm_result["tokens_out"],
        duration_analysis_sec=analysis_duration,
        duration_llm_sec=llm_result["duration_sec"],
        duration_total_sec=total_duration,
        context_chars=len(context),
        raw_code_chars=raw_chars,
        compression_ratio=1 - (len(context) / raw_chars) if raw_chars > 0 else 0,
        llm_response=llm_result["response"],
        llm_quality_keywords=evaluate_response_quality(llm_result["response"]),
        error=llm_result["error"],
        metadata={
            "patterns_used": 9,
            "method": "ast-grep" if "ast-grep" in context else "fallback-ast",
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
