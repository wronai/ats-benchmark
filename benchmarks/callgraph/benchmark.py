"""Benchmark: callgraph - Static call graph extraction for LLM context compression."""

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


def _generate_callgraph(app_path: Path) -> dict:
    """Generate call graph using callgraph-cli or pyan as fallback."""
    graph_data = {"nodes": [], "edges": [], "entry_points": []}

    # Try callgraph-cli first
    try:
        result = subprocess.run(
            ["callgraph-cli", str(app_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {
                "nodes": data.get("functions", []),
                "edges": data.get("calls", []),
                "entry_points": data.get("entry_points", []),
            }
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: pyan
    try:
        result = subprocess.run(
            ["pyan", str(app_path), "--uses", "--no-defines", "--colored", "--grouped", "--annotated", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {
                "nodes": list(set(node for edge in data for node in edge[:2])),
                "edges": [{"from": edge[0], "to": edge[1]} for edge in data],
                "entry_points": [],
            }
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # Last fallback: manual extraction
    return _manual_callgraph_extraction(app_path)


def _manual_callgraph_extraction(app_path: Path) -> dict:
    """Manual extraction of function calls when tools are unavailable."""
    import ast

    nodes = set()
    edges = []
    entry_points = []

    _SKIP_DIRS = {"__pycache__", "venv", ".venv", "dist", "build", ".git", ".tox", ".mypy_cache"}

    for py_file in sorted(app_path.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in py_file.parts):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            module_prefix = str(py_file.relative_to(app_path).with_suffix("")).replace("/", ".")

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_name = f"{module_prefix}.{node.name}"
                    nodes.add(func_name)

                    # Look for calls within function
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Name):
                                called = child.func.id
                                edges.append({"from": func_name, "to": called, "type": "call"})
                            elif isinstance(child.func, ast.Attribute):
                                called = child.func.attr
                                edges.append({"from": func_name, "to": called, "type": "method_call"})

                elif isinstance(node, ast.ClassDef):
                    class_name = f"{module_prefix}.{node.name}"
                    nodes.add(class_name)

                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_name = f"{class_name}.{item.name}"
                            nodes.add(method_name)

                            # Check for __main__ entry point
                            if item.name == "main" or "run" in item.name.lower():
                                entry_points.append(method_name)

        except SyntaxError:
            continue

    return {
        "nodes": sorted(nodes),
        "edges": edges,
        "entry_points": entry_points,
    }


def _compress_callgraph(graph: dict, max_nodes: int = 200) -> str:
    """Compress call graph into LLM-friendly format."""
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    nodes = []
    for node in raw_nodes:
        if isinstance(node, str):
            nodes.append(node)
        elif isinstance(node, dict):
            name = node.get("name") or node.get("id") or node.get("function") or node.get("qualified_name")
            if name:
                nodes.append(str(name))

    edges = []
    for edge in raw_edges:
        if isinstance(edge, dict):
            src = edge.get("from") or edge.get("caller") or edge.get("src")
            dst = edge.get("to") or edge.get("callee") or edge.get("dst")
            if src and dst:
                edges.append({"from": str(src), "to": str(dst)})
        elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
            edges.append({"from": str(edge[0]), "to": str(edge[1])})

    if not nodes:
        return "# Call Graph Analysis\n## Nodes (0 functions/classes)\n\n## Call Edges (0 relationships)"

    nodes = sorted(set(nodes))

    # If too large, prioritize entry points and their neighbors
    if len(nodes) > max_nodes:
        entry_points = set()
        for ep in graph.get("entry_points", []):
            if isinstance(ep, str):
                entry_points.add(ep)
            elif isinstance(ep, dict):
                name = ep.get("name") or ep.get("id") or ep.get("function")
                if name:
                    entry_points.add(str(name))
            else:
                entry_points.add(str(ep))

        priority_nodes = set(entry_points)

        # Add neighbors of entry points
        for edge in edges:
            if edge.get("from") in entry_points or edge.get("to") in entry_points:
                priority_nodes.add(edge.get("from"))
                priority_nodes.add(edge.get("to"))

        # Fallback when no explicit entry points are available
        if not priority_nodes:
            degree = {}
            for edge in edges:
                src = edge.get("from")
                dst = edge.get("to")
                if src:
                    degree[src] = degree.get(src, 0) + 1
                if dst:
                    degree[dst] = degree.get(dst, 0) + 1

            if degree:
                ranked = sorted(degree.items(), key=lambda item: item[1], reverse=True)
                priority_nodes.update(node for node, _ in ranked[:max_nodes])
            else:
                priority_nodes.update(nodes[:max_nodes])

        # Limit
        nodes = sorted(priority_nodes)[:max_nodes]
        node_set = set(nodes)
        edges = [e for e in edges if e.get("from") in node_set and e.get("to") in node_set]

    # Build compressed representation
    lines = ["# Call Graph Analysis"]
    lines.append(f"## Nodes ({len(nodes)} functions/classes)")

    # Group by module
    by_module = {}
    for node in nodes:
        if "." in node:
            mod, name = node.rsplit(".", 1)
            by_module.setdefault(mod, []).append(name)
        else:
            by_module.setdefault("__root__", []).append(node)

    for mod, names in sorted(by_module.items()):
        lines.append(f"\n### {mod}")
        for name in sorted(names)[:20]:  # Limit per module
            lines.append(f"  - {name}")
        if len(names) > 20:
            lines.append(f"  ... and {len(names) - 20} more")

    lines.append(f"\n## Call Edges ({len(edges)} relationships)")
    for edge in edges[:100]:  # Limit edges
        lines.append(f"  {edge.get('from')} -> {edge.get('to')}")
    if len(edges) > 100:
        lines.append(f"  ... and {len(edges) - 100} more edges")

    return "\n".join(lines)


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_target_project()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Generate call graph
    analysis_start = time.time()
    graph = _generate_callgraph(app_path)
    context = _compress_callgraph(graph)
    analysis_duration = time.time() - analysis_start

    # Phase 2: Send to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="callgraph (static call graph)",
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
            "tool": "callgraph",
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
        },
    )

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="callgraph",
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
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "entry_points": len(graph.get("entry_points", [])),
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
