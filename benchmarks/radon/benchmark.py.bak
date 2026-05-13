"""Benchmark: radon - Code complexity metrics for LLM context."""

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


def _run_radon_cc(app_path: Path) -> dict:
    """Run radon cc (cyclomatic complexity) analysis."""
    try:
        result = subprocess.run(
            ["radon", "cc", str(app_path), "-s", "-j"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _run_radon_mi(app_path: Path) -> dict:
    """Run radon mi (maintainability index) analysis."""
    try:
        result = subprocess.run(
            ["radon", "mi", str(app_path), "-s", "-j"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _run_radon_raw(app_path: Path) -> dict:
    """Run radon raw metrics analysis."""
    try:
        result = subprocess.run(
            ["radon", "raw", str(app_path), "-j"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _run_radon_hal(app_path: Path) -> dict:
    """Run radon halstead metrics analysis."""
    try:
        result = subprocess.run(
            ["radon", "hal", str(app_path), "-j"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _analyze_complexity(app_path: Path) -> str:
    """Analyze code complexity using radon."""
    lines = ["# Radon Complexity Analysis"]

    # Cyclomatic Complexity
    cc_data = _run_radon_cc(app_path)
    if cc_data:
        lines.append("\n## Cyclomatic Complexity (CC)")

        high_complexity = []
        moderate_complexity = []

        for file_path, blocks in cc_data.items():
            for block in blocks:
                rank = block.get("rank", "A")
                name = block.get("name", "unknown")
                complexity = block.get("complexity", 0)
                lineno = block.get("lineno", 0)

                if rank in ("C", "D", "E", "F"):
                    high_complexity.append({
                        "file": file_path,
                        "function": name,
                        "complexity": complexity,
                        "rank": rank,
                        "line": lineno,
                    })
                elif rank == "B":
                    moderate_complexity.append({
                        "file": file_path,
                        "function": name,
                        "complexity": complexity,
                        "rank": rank,
                        "line": lineno,
                    })

        if high_complexity:
            lines.append(f"\n### High Complexity Functions ({len(high_complexity)})")
            for item in sorted(high_complexity, key=lambda x: x["complexity"], reverse=True)[:15]:
                lines.append(
                    f"  - {item['file']}:{item['line']} {item['function']}() "
                    f"CC={item['complexity']} (rank={item['rank']})"
                )

        if moderate_complexity:
            lines.append(f"\n### Moderate Complexity Functions ({len(moderate_complexity)})")
            for item in sorted(moderate_complexity, key=lambda x: x["complexity"], reverse=True)[:10]:
                lines.append(
                    f"  - {item['file']}:{item['line']} {item['function']}() "
                    f"CC={item['complexity']}"
                )

    # Maintainability Index
    mi_data = _run_radon_mi(app_path)
    if mi_data:
        lines.append("\n## Maintainability Index (MI)")

        poor_mi = []
        moderate_mi = []

        for file_path, mi_info in mi_data.items():
            if isinstance(mi_info, dict):
                mi_value = mi_info.get("mi", 0)
                rank = mi_info.get("rank", "A")
            else:
                mi_value = mi_info
                rank = "A" if mi_value >= 85 else "B" if mi_value >= 70 else "C"

            if rank in ("C", "D"):
                poor_mi.append({"file": file_path, "mi": mi_value, "rank": rank})
            elif rank == "B":
                moderate_mi.append({"file": file_path, "mi": mi_value, "rank": rank})

        if poor_mi:
            lines.append(f"\n### Low Maintainability ({len(poor_mi)} files)")
            for item in sorted(poor_mi, key=lambda x: x["mi"])[:10]:
                lines.append(f"  - {item['file']}: MI={item['mi']:.1f} (rank={item['rank']})")

    # Raw Metrics
    raw_data = _run_radon_raw(app_path)
    if raw_data:
        lines.append("\n## Raw Metrics Summary")

        total_loc = 0
        total_sloc = 0
        total_comments = 0

        for file_path, metrics in raw_data.items():
            total_loc += metrics.get("loc", 0)
            total_sloc += metrics.get("sloc", 0)
            total_comments += metrics.get("comments", 0)

        lines.append(f"  Total LOC: {total_loc}")
        lines.append(f"  Source LOC: {total_sloc}")
        lines.append(f"  Comments: {total_comments}")
        lines.append(f"  Comment ratio: {total_comments/max(total_loc,1)*100:.1f}%")

        # Largest files
        largest = sorted(raw_data.items(), key=lambda x: x[1].get("sloc", 0), reverse=True)[:5]
        lines.append("\n### Largest Files (by SLOC)")
        for file_path, metrics in largest:
            lines.append(f"  - {file_path}: {metrics.get('sloc', 0)} SLOC")

    # Halstead Metrics
    hal_data = _run_radon_hal(app_path)
    if hal_data:
        lines.append("\n## Halstead Metrics (Sample)")
        # Halstead metrics can be very detailed, just show summary
        total_difficulty = 0
        count = 0

        for file_path, functions in hal_data.items():
            if isinstance(functions, dict):
                for func_name, metrics in functions.items():
                    if isinstance(metrics, dict):
                        total_difficulty += metrics.get("difficulty", 0)
                        count += 1

        if count > 0:
            avg_difficulty = total_difficulty / count
            lines.append(f"  Average difficulty: {avg_difficulty:.1f}")
            lines.append(f"  Functions analyzed: {count}")

    return "\n".join(lines)


def _fallback_analysis(app_path: Path) -> str:
    """Fallback when radon is not available."""
    lines = ["# Radon Complexity Analysis (Fallback)"]
    lines.append("[radon not available, using basic analysis]")

    import ast

    _SKIP_DIRS = {"__pycache__", "venv", ".venv", "dist", "build", ".git"}

    # Basic complexity estimation via AST
    complexities = []

    for py_file in sorted(app_path.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Simple complexity: count branches
                    branches = 1
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                            branches += 1
                        elif isinstance(child, ast.BoolOp):
                            branches += len(child.values) - 1

                    complexities.append({
                        "file": str(py_file.relative_to(app_path)),
                        "function": node.name,
                        "complexity": branches,
                    })
        except SyntaxError:
            continue

    # Report high complexity
    high_complexity = [c for c in complexities if c["complexity"] > 10]
    if high_complexity:
        lines.append(f"\n## High Complexity Functions ({len(high_complexity)})")
        for item in sorted(high_complexity, key=lambda x: x["complexity"], reverse=True)[:15]:
            lines.append(f"  - {item['file']}:{item['function']}() CC≈{item['complexity']}")

    return "\n".join(lines)


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_target_project()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Complexity analysis
    analysis_start = time.time()

    try:
        subprocess.run(["radon", "--version"], capture_output=True, timeout=5)
        context = _analyze_complexity(app_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        context = _fallback_analysis(app_path)

    analysis_duration = time.time() - analysis_start

    # Phase 2: Send to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="radon (complexity metrics)",
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
            "tool": "radon",
            "method": "fallback" if "Fallback" in context else "radon",
        },
    )

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="radon",
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
            "metrics": ["cyclomatic_complexity", "maintainability_index", "raw_metrics", "halstead"],
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
