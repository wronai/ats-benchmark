import json
from pathlib import Path
import subprocess


def _run_radon_cc(app_path: Path) -> dict:
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


def _analyze_complexity(app_path: Path) -> str:
    lines = ["# Radon Complexity Analysis"]
    cc_data = _run_radon_cc(app_path)
    if cc_data:
        lines.append("\n## Cyclomatic Complexity (CC)")
        high_complexity, moderate_complexity = _extract_complexity_data(cc_data)
        _append_high_complexity(lines, high_complexity)
        _append_moderate_complexity(lines, moderate_complexity)
    mi_data = _run_radon_mi(app_path)
    if mi_data:
        lines.append("\n## Maintainability Index (MI)")
        poor_mi, moderate_mi = _extract_mi_data(mi_data)
        _append_poor_mi(lines, poor_mi)
    raw_data = _run_radon_raw(app_path)
    if raw_data:
        lines.append("\n## Raw Metrics Summary")
        total_loc, total_sloc, total_comments = _calculate_raw_metrics(raw_data)
        _append_raw_metrics(lines, total_loc, total_sloc, total_comments)
        _append_largest_files(lines, raw_data)
    hal_data = _run_radon_hal(app_path)
    if hal_data:
        lines.append("\n## Halstead Metrics (Sample)")
        _append_halstead_metrics(lines, hal_data)
    return "\n".join(lines)


def _extract_complexity_data(cc_data: dict) -> tuple:
    high_complexity = []
    moderate_complexity = []
    for file_path, blocks in cc_data.items():
        for block in blocks:
            rank = block.get("rank", "A")
            name = block.get("name", "unknown")
            complexity = block.get("complexity", 0)
            lineno = block.get("lineno", 0)
            if rank in ("C", "D", "E", "F"):
                high_complexity.append(
                    {
                        "file": file_path,
                        "function": name,
                        "complexity": complexity,
                        "rank": rank,
                        "line": lineno,
                    }
                )
            elif rank == "B":
                moderate_complexity.append(
                    {
                        "file": file_path,
                        "function": name,
                        "complexity": complexity,
                        "rank": rank,
                        "line": lineno,
                    }
                )
    return high_complexity, moderate_complexity


def _append_high_complexity(lines: list, high_complexity: list) -> None:
    if high_complexity:
        lines.append(f"\n### High Complexity Functions ({len(high_complexity)})")
        for item in sorted(
            high_complexity, key=lambda x: x["complexity"], reverse=True
        )[:15]:
            lines.append(
                f"  - {item['file']}:{item['line']} {item['function']}() "
                f"CC={item['complexity']} (rank={item['rank']})"
            )


def _append_moderate_complexity(lines: list, moderate_complexity: list) -> None:
    if moderate_complexity:
        lines.append(
            f"\n### Moderate Complexity Functions ({len(moderate_complexity)})"
        )
        for item in sorted(
            moderate_complexity, key=lambda x: x["complexity"], reverse=True
        )[:10]:
            lines.append(
                f"  - {item['file']}:{item['line']} {item['function']}() "
                f"CC={item['complexity']}"
            )


def _extract_mi_data(mi_data: dict) -> tuple:
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
    return poor_mi, moderate_mi


def _append_poor_mi(lines: list, poor_mi: list) -> None:
    if poor_mi:
        lines.append(f"\n### Low Maintainability ({len(poor_mi)} files)")
        for item in sorted(poor_mi, key=lambda x: x["mi"])[:10]:
            lines.append(
                f"  - {item['file']}: MI={item['mi']:.1f} (rank={item['rank']})"
            )


def _calculate_raw_metrics(raw_data: dict) -> tuple:
    total_loc = 0
    total_sloc = 0
    total_comments = 0
    for file_path, metrics in raw_data.items():
        total_loc += metrics.get("loc", 0)
        total_sloc += metrics.get("sloc", 0)
        total_comments += metrics.get("comments", 0)
    return total_loc, total_sloc, total_comments


def _append_raw_metrics(
    lines: list, total_loc: int, total_sloc: int, total_comments: int
) -> None:
    lines.append(f"  Total LOC: {total_loc}")
    lines.append(f"  Source LOC: {total_sloc}")
    lines.append(f"  Comments: {total_comments}")
    lines.append(f"  Comment ratio: {total_comments / max(total_loc, 1) * 100:.1f}%")


def _append_largest_files(lines: list, raw_data: dict) -> None:
    largest = sorted(raw_data.items(), key=lambda x: x[1].get("sloc", 0), reverse=True)[
        :5
    ]
    lines.append("\n### Largest Files (by SLOC)")
    for file_path, metrics in largest:
        lines.append(f"  - {file_path}: {metrics.get('sloc', 0)} SLOC")


def _append_halstead_metrics(lines: list, hal_data: dict) -> None:
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
