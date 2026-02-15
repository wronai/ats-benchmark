#!/usr/bin/env python3
"""Analyze and compare benchmark results from all tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


BENCHMARK_DIRS = [
    "benchmarks/code2logic",
    "benchmarks/nfo",
    "benchmarks/baseline",
]

REPAIR_DIRS = [
    "benchmarks/repair/code2logic",
    "benchmarks/repair/nfo",
    "benchmarks/repair/baseline",
]


def load_results() -> List[Dict[str, Any]]:
    """Load results.json from each benchmark directory."""
    results = []
    root = Path(__file__).parent
    for bdir in BENCHMARK_DIRS:
        result_file = root / bdir / "results.json"
        if result_file.exists():
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                results.append(data)
            except Exception as e:
                print(f"Warning: failed to load {result_file}: {e}", file=sys.stderr)
    return results


def load_repair_results() -> List[Dict[str, Any]]:
    """Load repair_result.json from each repair directory."""
    results = []
    root = Path(__file__).parent
    for rdir in REPAIR_DIRS:
        result_file = root / rdir / "repair_result.json"
        if result_file.exists():
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                results.append(data)
            except Exception as e:
                print(f"Warning: failed to load {result_file}: {e}", file=sys.stderr)
    return results


def print_comparison_table(results: List[Dict[str, Any]]) -> None:
    """Print a formatted comparison table."""
    if not results:
        print("No results found. Run benchmarks first: make benchmark-all")
        return

    print("=" * 90)
    print("ATS BENCHMARK — COMPARISON RESULTS")
    print("=" * 90)
    print()

    # Header
    headers = [
        "Tool",
        "Tokens In",
        "Tokens Out",
        "Context (chars)",
        "Compression",
        "LLM Time (s)",
        "Total (s)",
        "Quality",
    ]
    widths = [16, 11, 11, 15, 12, 12, 10, 8]

    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-" * len(header_line))

    # Sort by compression ratio (descending)
    sorted_results = sorted(results, key=lambda r: r.get("compression_ratio", 0), reverse=True)

    for r in sorted_results:
        tool = r.get("tool", "?")
        tokens_in = r.get("tokens_in", 0)
        tokens_out = r.get("tokens_out", 0)
        context_chars = r.get("context_chars", 0)
        compression = r.get("compression_ratio", 0)
        llm_time = r.get("duration_llm_sec", 0)
        total_time = r.get("duration_total_sec", 0)
        quality = r.get("llm_quality_keywords", 0)
        error = r.get("error")

        if error:
            tool += " *"

        row = [
            tool.ljust(widths[0]),
            str(tokens_in).rjust(widths[1]),
            str(tokens_out).rjust(widths[2]),
            str(context_chars).rjust(widths[3]),
            f"{compression:.1%}".rjust(widths[4]),
            f"{llm_time:.2f}".rjust(widths[5]),
            f"{total_time:.2f}".rjust(widths[6]),
            str(quality).rjust(widths[7]),
        ]
        print(" | ".join(row))

    print()

    # Errors
    errors = [(r["tool"], r["error"]) for r in results if r.get("error")]
    if errors:
        print("ERRORS:")
        for tool, err in errors:
            print(f"  [{tool}] {err[:100]}")
        print()

    # Summary
    print("SUMMARY:")
    if len(sorted_results) >= 2:
        baseline = next((r for r in sorted_results if r["tool"] == "baseline-raw"), None)
        if baseline:
            baseline_tokens = baseline.get("tokens_in", 1) or 1
            for r in sorted_results:
                if r["tool"] != "baseline-raw":
                    tokens = r.get("tokens_in", 0)
                    if tokens > 0:
                        savings = (1 - tokens / baseline_tokens) * 100
                        print(
                            f"  {r['tool']}: {savings:.0f}% fewer tokens than baseline "
                            f"({tokens} vs {baseline_tokens})"
                        )

    # Best tool
    valid = [r for r in sorted_results if not r.get("error")]
    if valid:
        best_compression = max(valid, key=lambda r: r.get("compression_ratio", 0))
        best_quality = max(valid, key=lambda r: r.get("llm_quality_keywords", 0))
        best_speed = min(valid, key=lambda r: r.get("duration_total_sec", float("inf")))

        print(f"\n  Best compression: {best_compression['tool']} ({best_compression['compression_ratio']:.1%})")
        print(f"  Best quality:     {best_quality['tool']} ({best_quality['llm_quality_keywords']} keywords)")
        print(f"  Fastest:          {best_speed['tool']} ({best_speed['duration_total_sec']:.2f}s)")

    print()
    print("=" * 90)


def save_summary_json(results: List[Dict[str, Any]]) -> None:
    """Save combined results to a single JSON file."""
    output = Path(__file__).parent / "benchmark_summary.json"
    summary = {
        "results": results,
        "tools_count": len(results),
        "errors_count": sum(1 for r in results if r.get("error")),
    }
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Summary saved to: {output}")


def print_repair_table(repairs: List[Dict[str, Any]]) -> None:
    """Print repair results comparison."""
    if not repairs:
        return

    print()
    print("=" * 90)
    print("ATS BENCHMARK — REPAIR RESULTS")
    print("=" * 90)
    print()

    target = repairs[0].get("target_project", "?")
    problem = repairs[0].get("problem", "?")
    print(f"Target:  {target}")
    print(f"Problem: {problem[:120]}")
    print()

    headers = ["Tool", "Tokens In", "Tokens Out", "Duration (s)", "Files Fixed", "Has Test", "Status"]
    widths = [14, 11, 11, 12, 12, 9, 20]

    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-" * len(header_line))

    for r in repairs:
        tool = r.get("tool", "?")
        tokens_in = r.get("tokens_in", 0)
        tokens_out = r.get("tokens_out", 0)
        duration = r.get("duration_sec", 0)
        fixed_files = r.get("fixed_files", {})
        test_code = r.get("test_code", "")
        error = r.get("error")

        status = "ERROR" if error else ("OK" if fixed_files else "NO FIX")
        has_test = "yes" if test_code.strip() else "no"

        row = [
            tool.ljust(widths[0]),
            str(tokens_in).rjust(widths[1]),
            str(tokens_out).rjust(widths[2]),
            f"{duration:.2f}".rjust(widths[3]),
            str(len(fixed_files)).rjust(widths[4]),
            has_test.center(widths[5]),
            status.ljust(widths[6]),
        ]
        print(" | ".join(row))

    print()

    # Show diagnoses
    for r in repairs:
        diag = r.get("diagnosis", "")
        if diag:
            print(f"[{r['tool']}] Diagnosis: {diag[:200]}")
    print()

    # Show errors
    errors = [(r["tool"], r["error"]) for r in repairs if r.get("error")]
    if errors:
        print("ERRORS:")
        for tool, err in errors:
            print(f"  [{tool}] {err[:100]}")
        print()

    print("=" * 90)


def main():
    results = load_results()
    print_comparison_table(results)

    repairs = load_repair_results()
    print_repair_table(repairs)

    all_data = results + repairs
    if all_data:
        save_summary_json(results)


if __name__ == "__main__":
    main()
