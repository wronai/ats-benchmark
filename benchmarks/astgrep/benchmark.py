"""Benchmark: ast-grep - Structural code search for LLM context compression."""

from __future__ import annotations

import json
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
    save_llm_artifacts,
    save_result,
)


def _run_ast_grep(pattern: str, app_path: Path, lang: str = "python") -> list:
    """Run ast-grep with given pattern and return matches."""
    commands = [
        # Current ast-grep CLI
        ["ast-grep", "run", "--pattern", pattern, "--json=stream", "-l", lang, str(app_path)],
        # Backward compatibility with older CLI
        ["ast-grep", "scan", "--pattern", pattern, "--json", "-l", lang, str(app_path)],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

        if result.returncode not in (0, 1):
            continue

        output = result.stdout.strip()
        if not output:
            return []

        # JSON lines output (preferred)
        matches = []
        all_json_lines = True
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                matches.append(json.loads(line))
            except json.JSONDecodeError:
                all_json_lines = False
                matches = []
                break
        if all_json_lines and matches:
            return matches

        # Fallback: JSON array/object output
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            if isinstance(parsed.get("results"), list):
                return parsed["results"]
            if "file" in parsed or "range" in parsed:
                return [parsed]

    return []


def _extract_match_file_and_line(match: dict) -> tuple[str, int]:
    """Extract file path + start line from old/new ast-grep JSON formats."""
    meta = match.get("meta", {}) if isinstance(match, dict) else {}
    file_path = meta.get("file") or match.get("file", "")

    rng = meta.get("range") or match.get("range", {})
    line_num = rng.get("start", {}).get("line", 0)
    return str(file_path), int(line_num or 0)


def _extract_match_variables(match: dict) -> dict:
    """Extract metavariables from old/new ast-grep JSON formats."""
    if not isinstance(match, dict):
        return {}

    # Older output format
    legacy = match.get("match")
    if isinstance(legacy, dict) and legacy:
        return legacy

    # Newer output format (metaVariables)
    vars_out = {}
    meta_vars = match.get("metaVariables", {})

    single = meta_vars.get("single", {}) if isinstance(meta_vars, dict) else {}
    for key, val in single.items():
        if isinstance(val, dict):
            vars_out[key] = val.get("text", "")

    multi = meta_vars.get("multi", {}) if isinstance(meta_vars, dict) else {}
    for key, vals in multi.items():
        if isinstance(vals, list):
            if vals and isinstance(vals[0], dict):
                vars_out[key] = vals[0].get("text", "")
            else:
                vars_out[key] = ""

    return vars_out


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
                    file_path, line_num = _extract_match_file_and_line(match)

                    # Extract matched variables
                    variables = _extract_match_variables(match)
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
                m = _extract_match_variables(match)
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

    save_llm_artifacts(
        Path(__file__).parent,
        stage="benchmark",
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        prompt=prompt,
        context=context,
        llm_result=llm_result,
        extra={
            "tool": "ast-grep",
            "method": "fallback-ast" if "Fallback" in context else "ast-grep",
            "patterns_used": 9,
        },
    )

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
            "method": "fallback-ast" if "Fallback" in context else "ast-grep",
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
