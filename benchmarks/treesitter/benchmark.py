"""Benchmark: treesitter - Direct AST extraction using tree-sitter for LLM context."""

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
    save_result,
)


def _get_parser():
    """Get or build tree-sitter parser for Python."""
    try:
        from tree_sitter import Language, Parser

        try:
            import tree_sitter_python as tspython
            py_language = Language(tspython.language())
        except Exception:
            return None

        parser = Parser()
        if hasattr(parser, "set_language"):
            parser.set_language(py_language)
        else:
            parser.language = py_language
        return parser
    except Exception:
        return None


def _serialize_node(node, code_bytes: bytes, indent: int = 0, max_depth: int = 5) -> str:
    """Serialize AST node to string representation."""
    if node is None or indent > max_depth:
        return ""

    node_type = node.type
    result = ["  " * indent + f"({node_type}"]

    # Add text for leaf nodes
    if node.child_count == 0 and node.end_byte - node.start_byte < 50:
        text = code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
        text = text.replace("\\", "\\\\").replace('"', '\\"')
        result[0] += f' "{text}"'

    # Recursively serialize children
    for child in node.children:
        child_str = _serialize_node(child, code_bytes, indent + 1, max_depth)
        if child_str:
            result.append(child_str)

    result.append("  " * indent + ")")
    return "\n".join(result)


def _extract_ast_summary(parser, code: bytes) -> dict:
    """Extract summary statistics from AST."""
    tree = parser.parse(code)
    root = tree.root_node

    stats = {
        "total_nodes": 0,
        "functions": [],
        "classes": [],
        "imports": [],
        "depth": 0,
    }

    def traverse(node, depth=0):
        if node is None:
            return

        stats["total_nodes"] += 1
        stats["depth"] = max(stats["depth"], depth)

        if node.type == "function_definition":
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node:
                stats["functions"].append(code[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore"))

        elif node.type == "class_definition":
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node:
                stats["classes"].append(code[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore"))

        elif node.type in ("import_statement", "import_from_statement"):
            stats["imports"].append(code[node.start_byte:node.end_byte].decode("utf-8", errors="ignore"))

        for child in node.children:
            traverse(child, depth + 1)

    traverse(root)
    return stats


def _build_treesitter_context(app_path: Path, max_files: int = 10) -> str:
    """Build compressed context from tree-sitter AST."""
    parser = _get_parser()
    if parser is None:
        return "[tree-sitter not available, using fallback]"

    lines = ["# Tree-sitter AST Analysis"]
    total_nodes = 0
    all_functions = []
    all_classes = []
    all_imports = []

    _SKIP_DIRS = {"__pycache__", "venv", ".venv", "dist", "build", ".git", ".tox", ".mypy_cache"}

    py_files = list(app_path.rglob("*.py"))
    processed = 0

    for py_file in sorted(py_files):
        if any(part in _SKIP_DIRS for part in py_file.parts):
            continue
        if processed >= max_files:
            break

        try:
            code = py_file.read_bytes()
            rel = py_file.relative_to(app_path)

            stats = _extract_ast_summary(parser, code)
            total_nodes += stats["total_nodes"]
            all_functions.extend(stats["functions"])
            all_classes.extend(stats["classes"])
            all_imports.extend(stats["imports"])

            lines.append(f"\n## {rel}")
            lines.append(f"  AST nodes: {stats['total_nodes']}, depth: {stats['depth']}")

            # Sample AST structure (first function only)
            tree = parser.parse(code)
            for node in tree.root_node.children:
                if node.type == "function_definition":
                    ast_str = _serialize_node(node, code, max_depth=3)
                    lines.append("  Sample AST (function):")
                    for ast_line in ast_str.split("\n")[:15]:
                        lines.append(f"    {ast_line}")
                    break

            processed += 1

        except Exception as e:
            lines.append(f"  [Error: {e}]")

    # Summary
    lines.insert(1, f"\n## Summary")
    lines.insert(2, f"  Files analyzed: {processed}")
    lines.insert(3, f"  Total AST nodes: {total_nodes}")
    lines.insert(4, f"  Functions found: {len(all_functions)}")
    lines.insert(5, f"  Classes found: {len(all_classes)}")
    lines.insert(6, f"  Unique imports: {len(set(all_imports))}")

    return "\n".join(lines)


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_target_project()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Parse with tree-sitter
    analysis_start = time.time()
    context = _build_treesitter_context(app_path)
    analysis_duration = time.time() - analysis_start

    # Phase 2: Send to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="tree-sitter (direct AST)",
        context=context,
    )

    llm_result = call_llm(prompt, system=ANALYSIS_SYSTEM_PROMPT)

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="treesitter",
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
            "language": "python",
            "has_native_parser": _get_parser() is not None,
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
