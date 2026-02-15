"""Benchmark: baseline - Raw source code sent directly to LLM (no compression)."""

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
    get_sample_app_path,
    read_all_source_files,
    save_result,
)


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_sample_app_path()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Just read raw source code (no analysis)
    analysis_start = time.time()
    context = read_all_source_files(app_path)
    analysis_duration = time.time() - analysis_start

    # Phase 2: Send raw code to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="raw source code (baseline, no compression)",
        context=context,
    )

    llm_result = call_llm(prompt, system=ANALYSIS_SYSTEM_PROMPT)

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="baseline-raw",
        tokens_in=llm_result["tokens_in"],
        tokens_out=llm_result["tokens_out"],
        duration_analysis_sec=analysis_duration,
        duration_llm_sec=llm_result["duration_sec"],
        duration_total_sec=total_duration,
        context_chars=len(context),
        raw_code_chars=raw_chars,
        compression_ratio=0.0,  # No compression
        llm_response=llm_result["response"],
        llm_quality_keywords=evaluate_response_quality(llm_result["response"]),
        error=llm_result["error"],
        metadata={
            "mode": "raw_source",
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
