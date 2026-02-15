"""Repair pipeline: use code2logic/nfo to compress project context, then ask LLM to fix a real problem."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.common import (
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_PROMPT_TEMPLATE,
    RepairResult,
    call_llm,
    count_raw_code_chars,
    get_problem_description,
    get_target_project,
    read_all_source_files,
    save_repair_result,
)


# ---------------------------------------------------------------------------
# Context generators (one per tool)
# ---------------------------------------------------------------------------

def _context_code2logic(project_path: Path) -> str:
    """Generate compressed context using code2logic."""
    try:
        from code2logic import analyze_project, CompactGenerator, FunctionLogicGenerator

        project = analyze_project(str(project_path), use_treesitter=True, verbose=False)
        compact = CompactGenerator().generate(project)
        logic = FunctionLogicGenerator().generate(project, detail="full")
        return f"## Project Structure (code2logic compact)\n{compact}\n\n## Function Details\n{logic}"
    except Exception as e:
        return f"[code2logic failed: {e}] — falling back to raw source\n" + read_all_source_files(project_path, max_chars=30000)


def _context_nfo(project_path: Path) -> str:
    """Generate data-flow context using nfo-style analysis."""
    lines = ["## Data Flow Analysis"]
    imports_map = {}

    for py_file in sorted(project_path.rglob("*.py")):
        if any(part in py_file.parts for part in (
            "__pycache__", "venv", ".venv", "dist", "build", ".git", ".tox",
        )):
            continue

        try:
            rel = py_file.relative_to(project_path)
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        file_imports = []
        for line in content.splitlines():
            s = line.strip()
            if s.startswith(("from ", "import ")):
                file_imports.append(s)
        imports_map[str(rel)] = file_imports

        lines.append(f"\n### {rel}")
        in_class = None
        for line in content.splitlines():
            s = line.strip()
            if s.startswith("class "):
                in_class = s.split("(")[0].replace("class ", "").rstrip(":")
                lines.append(f"  class {in_class}")
            elif s.startswith("def "):
                fname = s.split("(")[0].replace("def ", "")
                ret = ""
                if "->" in s:
                    ret = s.split("->")[1].strip().rstrip(":")
                prefix = f"    {in_class}." if in_class else "  "
                lines.append(f"{prefix}{fname}() -> {ret or '?'}")

    lines.append("\n## Import Graph")
    for mod, imps in imports_map.items():
        if imps:
            lines.append(f"  {mod}:")
            for imp in imps[:8]:
                lines.append(f"    <- {imp}")

    return "\n".join(lines)


def _context_baseline(project_path: Path) -> str:
    """Raw source code — no compression."""
    return read_all_source_files(project_path, max_chars=50000)


CONTEXT_GENERATORS = {
    "code2logic": _context_code2logic,
    "nfo": _context_nfo,
    "baseline": _context_baseline,
}


# ---------------------------------------------------------------------------
# Auto-detect problem
# ---------------------------------------------------------------------------

def _auto_detect_problem(project_path: Path) -> str:
    """Try to auto-detect problems from TODO.md, failing tests, or common issues."""
    # Check TODO.md
    todo = project_path / "TODO.md"
    if todo.exists():
        content = todo.read_text(encoding="utf-8", errors="ignore")
        if content.strip():
            # Extract first actionable section
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 20:
                    return f"From TODO.md: {line[:200]}"

    # Check for common issues in source
    issues = []
    for py_file in sorted(project_path.rglob("*.py"))[:50]:
        if any(p in py_file.parts for p in ("__pycache__", "venv", ".venv", ".git")):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            rel = py_file.relative_to(project_path)
            if "# TODO" in content or "# FIXME" in content or "# HACK" in content:
                for i, line in enumerate(content.splitlines(), 1):
                    if any(tag in line for tag in ("# TODO", "# FIXME", "# HACK")):
                        issues.append(f"{rel}:{i}: {line.strip()}")
            if "raise NotImplementedError" in content:
                issues.append(f"{rel}: has NotImplementedError stubs")
            if "pass  #" in content or content.count("pass\n") > 3:
                issues.append(f"{rel}: has empty pass stubs")
        except Exception:
            continue

    if issues:
        return "Auto-detected issues:\n" + "\n".join(issues[:10])

    return "General code review: find bugs, missing error handling, and refactoring opportunities in this project."


# ---------------------------------------------------------------------------
# Parse LLM JSON response
# ---------------------------------------------------------------------------

def _parse_repair_json(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ```
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_start = raw.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    # Return raw as diagnosis
    return {"diagnosis": raw[:2000], "fixed_files": {}, "test_code": "", "summary": "Failed to parse JSON"}


# ---------------------------------------------------------------------------
# Main repair function
# ---------------------------------------------------------------------------

def run_repair(tool: str = "code2logic") -> RepairResult:
    """Run repair pipeline for a single tool."""
    project_path = get_target_project()
    project_name = project_path.name

    # Get or auto-detect problem
    problem = get_problem_description()
    if not problem:
        problem = _auto_detect_problem(project_path)

    print(f"\n{'='*70}")
    print(f"[repair/{tool}] Target: {project_path}")
    print(f"[repair/{tool}] Problem: {problem[:100]}...")
    print(f"{'='*70}")

    # Generate context
    gen = CONTEXT_GENERATORS.get(tool, _context_code2logic)
    context = gen(project_path)
    raw_chars = count_raw_code_chars(project_path)

    print(f"[repair/{tool}] Context: {len(context)} chars (raw: {raw_chars}, compression: {1 - len(context)/max(raw_chars,1):.0%})")

    # Build prompt
    prompt = REPAIR_USER_PROMPT_TEMPLATE.format(
        project_name=project_name,
        problem=problem,
        tool_name=tool,
        context=context,
    )

    # Call LLM
    print(f"[repair/{tool}] Calling LLM ({__import__('os').getenv('MODEL_ID', '?')})...")
    llm_result = call_llm(prompt, system=REPAIR_SYSTEM_PROMPT)

    if llm_result["error"]:
        return RepairResult(
            tool=tool,
            target_project=str(project_path),
            problem=problem,
            diagnosis=f"LLM call failed: {llm_result['error']}",
            tokens_in=llm_result["tokens_in"],
            tokens_out=llm_result["tokens_out"],
            duration_sec=llm_result["duration_sec"],
            error=llm_result["error"],
        )

    # Parse response
    parsed = _parse_repair_json(llm_result["response"])

    result = RepairResult(
        tool=tool,
        target_project=str(project_path),
        problem=problem,
        diagnosis=parsed.get("diagnosis", ""),
        fixed_files=parsed.get("fixed_files", {}),
        test_code=parsed.get("test_code", ""),
        tokens_in=llm_result["tokens_in"],
        tokens_out=llm_result["tokens_out"],
        duration_sec=llm_result["duration_sec"],
    )

    return result


def run_all_repairs() -> None:
    """Run repair with all tools and save results."""
    output_base = Path(__file__).parent

    for tool in ["code2logic", "nfo", "baseline"]:
        try:
            result = run_repair(tool)
            save_repair_result(result, output_base / tool)
        except Exception as e:
            print(f"[repair/{tool}] FAILED: {e}")

    print(f"\n{'='*70}")
    print("All repair runs completed. Results in benchmarks/repair/*/")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM repair pipeline")
    parser.add_argument("--tool", choices=["code2logic", "nfo", "baseline", "all"], default="all",
                        help="Which compression tool to use (default: all)")
    args = parser.parse_args()

    if args.tool == "all":
        run_all_repairs()
    else:
        result = run_repair(args.tool)
        output_dir = Path(__file__).parent / args.tool
        save_repair_result(result, output_dir)
