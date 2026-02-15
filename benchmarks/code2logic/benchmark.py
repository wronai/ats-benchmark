"""Benchmark: code2logic - AST/logic extraction for LLM context compression."""

from __future__ import annotations

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


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_target_project()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Analyze with code2logic
    analysis_start = time.time()
    try:
        from code2logic import analyze_project, CompactGenerator, FunctionLogicGenerator

        project = analyze_project(str(app_path), use_treesitter=True, verbose=False)

        # Generate compact representation (best token efficiency)
        compact_gen = CompactGenerator()
        compact_output = compact_gen.generate(project)

        # Also generate function logic for richer context
        logic_gen = FunctionLogicGenerator()
        logic_output = logic_gen.generate(project, detail="full")

        context = f"## Compact Structure\n{compact_output}\n\n## Function Logic\n{logic_output}"

    except Exception as e:
        context = f"[code2logic analysis failed: {e}]"
        # Fallback: try with just the analyzer
        try:
            from code2logic import analyze_project
            project = analyze_project(str(app_path), use_treesitter=False, verbose=False)
            # Manual compact output
            lines = []
            for m in project.modules:
                lines.append(f"# {m.path} ({m.language}, {m.lines_total} lines)")
                for f in m.functions:
                    params = ", ".join(f.params) if f.params else ""
                    lines.append(f"  def {f.name}({params}) -> {f.return_type or '?'}")
                for c in m.classes:
                    lines.append(f"  class {c.name}:")
                    for method in c.methods:
                        params = ", ".join(method.params) if method.params else ""
                        lines.append(f"    def {method.name}({params})")
            context = "\n".join(lines)
        except Exception as e2:
            context = f"[code2logic completely failed: {e2}]"

    analysis_duration = time.time() - analysis_start

    # Phase 2: Send to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="code2logic (AST + function logic)",
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
        extra={"tool": "code2logic"},
    )

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="code2logic",
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
            "parser": "tree-sitter",
            "format": "compact+function_logic",
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
