"""Shared benchmark utilities for all tools."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import litellm


@dataclass
class BenchmarkResult:
    """Single benchmark run result."""
    tool: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_analysis_sec: float = 0.0
    duration_llm_sec: float = 0.0
    duration_total_sec: float = 0.0
    context_chars: int = 0
    raw_code_chars: int = 0
    compression_ratio: float = 0.0
    llm_response: str = ""
    llm_quality_keywords: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Truncate llm_response for JSON output
        if len(d["llm_response"]) > 500:
            d["llm_response"] = d["llm_response"][:500] + "..."
        return d


def get_model() -> str:
    return os.getenv("MODEL_ID", "meta-llama/llama-3.2-3b-instruct:free")


def get_max_tokens() -> int:
    return int(os.getenv("MAX_TOKENS", "2048"))


def get_temperature() -> float:
    return float(os.getenv("TEMPERATURE", "0.1"))


def get_sample_app_path() -> Path:
    """Return path to sample-app, works both in Docker and locally."""
    candidates = [
        Path("/workspace/sample-app"),
        Path(__file__).parent.parent / "sample-app",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("sample-app not found")


def read_all_source_files(app_path: Path) -> str:
    """Read all Python source files from sample-app."""
    sources = []
    for py_file in sorted(app_path.rglob("*.py")):
        rel = py_file.relative_to(app_path)
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        sources.append(f"# === {rel} ===\n{content}")
    return "\n\n".join(sources)


def count_raw_code_chars(app_path: Path) -> int:
    """Count total characters in all source files."""
    total = 0
    for py_file in app_path.rglob("*.py"):
        total += len(py_file.read_text(encoding="utf-8", errors="ignore"))
    return total


def call_llm(prompt: str, system: str = "") -> Dict[str, Any]:
    """Call LLM via litellm with OpenRouter and return response + metrics."""
    model = get_model()
    max_tokens = get_max_tokens()
    temperature = get_temperature()

    # Ensure OpenRouter routing
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {
            "response": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "duration_sec": 0,
            "error": "OPENROUTER_API_KEY not set",
        }

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    start = time.time()
    try:
        response = litellm.completion(
            model=f"openrouter/{model}",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=api_key,
        )
        duration = time.time() - start

        content = response.choices[0].message.content or ""
        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0

        return {
            "response": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_sec": duration,
            "error": None,
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "response": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "duration_sec": duration,
            "error": str(e),
        }


def evaluate_response_quality(response: str) -> int:
    """Simple quality score: count relevant analysis keywords in response."""
    keywords = [
        "bug", "error", "issue", "fix", "refactor", "improve",
        "vulnerability", "performance", "complexity", "dependency",
        "coupling", "cohesion", "pattern", "anti-pattern",
        "data flow", "call graph", "entry point", "dead code",
        "type", "validation", "exception", "race condition",
        "security", "injection", "memory", "leak",
        "function", "class", "method", "module",
    ]
    response_lower = response.lower()
    return sum(1 for kw in keywords if kw in response_lower)


def save_result(result: BenchmarkResult, output_dir: Path) -> None:
    """Save benchmark result to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "results.json"
    data = result.to_dict()
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[{result.tool}] Results saved to {output_file}")
    print(f"  tokens_in={result.tokens_in}, tokens_out={result.tokens_out}")
    print(f"  context_chars={result.context_chars}, compression={result.compression_ratio:.1%}")
    print(f"  duration_total={result.duration_total_sec:.2f}s")
    if result.error:
        print(f"  ERROR: {result.error}")


ANALYSIS_SYSTEM_PROMPT = """You are a senior software engineer performing code review.
Analyze the provided code representation and identify:
1. Potential bugs or logic errors
2. Data flow issues (missing validation, unhandled edge cases)
3. Refactoring opportunities (code duplication, high coupling)
4. Security concerns
5. Performance issues

Be specific and reference function/class names. Provide actionable recommendations."""

ANALYSIS_USER_PROMPT_TEMPLATE = """Analyze this {tool_name} representation of a Python e-commerce application.
Find bugs, data flow issues, and refactoring opportunities.

{context}"""
