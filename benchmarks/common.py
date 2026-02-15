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

# Suppress litellm debug info and provider list spam
os.environ["LITELLM_LOG"] = "ERROR"
litellm.suppress_debug_info = True
litellm.set_verbose = False


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Load .env from workspace root (works in Docker and locally)."""
    for candidate in [Path("/workspace/.env"), Path(__file__).parent.parent / ".env"]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if key and val and key not in os.environ:
                    os.environ[key] = val
            break

_load_env()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Single benchmark run result."""
    tool: str
    target_project: str = ""
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
        if len(d["llm_response"]) > 2000:
            d["llm_response"] = d["llm_response"][:2000] + "..."
        return d


@dataclass
class RepairResult:
    """Result of an LLM repair attempt."""
    tool: str
    target_project: str
    problem: str
    diagnosis: str = ""
    fixed_files: Dict[str, str] = field(default_factory=dict)
    test_code: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_sec: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for fname, content in d["fixed_files"].items():
            if len(content) > 5000:
                d["fixed_files"][fname] = content[:5000] + "\n# ... truncated"
        return d


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_model() -> str:
    """Get LLM model ID in format provider/model."""
    return os.getenv("MODEL_ID", "openrouter/meta-llama/llama-3.2-3b-instruct:free")


def get_max_tokens() -> int:
    return int(os.getenv("MAX_TOKENS", "4096"))


def get_temperature() -> float:
    return float(os.getenv("TEMPERATURE", "0.1"))


def get_target_project() -> Path:
    """Return TARGET_PROJECT path from env, falling back to sample-app."""
    target = os.getenv("TARGET_PROJECT", "").strip()
    if target:
        p = Path(target)
        if p.exists():
            return p
        # Docker mount path
        if Path("/project").exists():
            return Path("/project")
        raise FileNotFoundError(f"TARGET_PROJECT not found: {target}")
    return get_sample_app_path()


def get_problem_description() -> str:
    """Return PROBLEM_DESCRIPTION from env or empty string for auto-detect."""
    return os.getenv("PROBLEM_DESCRIPTION", "").strip()


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


# ---------------------------------------------------------------------------
# Source reading
# ---------------------------------------------------------------------------

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".php", ".c", ".cpp", ".h"}


def read_all_source_files(app_path: Path, max_chars: int = 0) -> str:
    """Read all source files from a project directory."""
    sources = []
    total = 0
    for src_file in sorted(app_path.rglob("*")):
        if not src_file.is_file():
            continue
        if src_file.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if any(part.startswith(".") or part in (
            "node_modules", "__pycache__", "venv", ".venv", "dist", "build",
            ".git", ".idea", ".tox", ".mypy_cache",
        ) for part in src_file.parts):
            continue
        content = src_file.read_text(encoding="utf-8", errors="ignore")
        rel = src_file.relative_to(app_path)
        sources.append(f"# === {rel} ===\n{content}")
        total += len(content)
        if max_chars and total > max_chars:
            sources.append(f"# ... truncated at {max_chars} chars ({total} total)")
            break
    return "\n\n".join(sources)


def count_raw_code_chars(app_path: Path) -> int:
    """Count total characters in all source files."""
    total = 0
    for src_file in app_path.rglob("*"):
        if src_file.is_file() and src_file.suffix.lower() in SOURCE_EXTENSIONS:
            if not any(part.startswith(".") or part in (
                "node_modules", "__pycache__", "venv", ".venv", "dist", "build",
            ) for part in src_file.parts):
                total += len(src_file.read_text(encoding="utf-8", errors="ignore"))
    return total


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def call_llm(prompt: str, system: str = "", max_tokens: int = 0) -> Dict[str, Any]:
    """Call LLM via litellm with OpenRouter and return response + metrics."""
    model = get_model()
    if not max_tokens:
        max_tokens = get_max_tokens()
    temperature = get_temperature()

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
        print(f"  Calling LLM ({model})...", flush=True)
        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=api_key,
            timeout=300,  # Increased to 300s for large baseline contexts
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


def check_llm_connection() -> Dict[str, Any]:
    """Test LLM connection with a simple prompt and return diagnostic info."""
    print("=== LLM Connection Test ===", flush=True)
    model = get_model()
    print(f"  Model: {model}")
    
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"success": False, "error": "OPENROUTER_API_KEY is not set in .env"}
    
    print(f"  API Key: {api_key[:10]}...{api_key[-5:] if len(api_key) > 15 else ''}")
    
    test_prompt = "Respond with exactly one word: 'OK'"
    start = time.time()
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": test_prompt}],
            max_tokens=10,
            temperature=0,
            api_key=api_key,
            timeout=30,
        )
        duration = time.time() - start
        content = response.choices[0].message.content or ""
        
        if "OK" in content.upper():
            print(f"  Status: SUCCESS ({duration:.2f}s)")
            return {"success": True, "duration": duration, "model": model}
        else:
            error_msg = f"Unexpected response from LLM: {content}"
            print(f"  Status: FAILED - {error_msg}")
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        duration = time.time() - start
        error_msg = str(e)
        print(f"  Status: ERROR ({duration:.2f}s)")
        print(f"  Error Detail: {error_msg}")
        
        # Detailed diagnostics
        diag = []
        if "Authentication" in error_msg or "401" in error_msg:
            diag.append("Check if your OPENROUTER_API_KEY is valid.")
        if "Connection" in error_msg or "404" in error_msg:
            diag.append("Check your internet connection or if the model ID is correct.")
        if "429" in error_msg or "limit" in error_msg.lower():
            diag.append("Rate limit exceeded or insufficient credits.")
            
        if diag:
            print("\n  Recommended Fixes:")
            for d in diag:
                print(f"  - {d}")
                
        return {"success": False, "error": error_msg, "diagnostics": diag}


# ---------------------------------------------------------------------------
# Quality evaluation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------

def save_result(result: BenchmarkResult, output_dir: Path) -> None:
    """Save benchmark result to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "results.json"
    data = result.to_dict()
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[{result.tool}] Results saved to {output_file}")
    print(f"  target={result.target_project}")
    print(f"  tokens_in={result.tokens_in}, tokens_out={result.tokens_out}")
    print(f"  context_chars={result.context_chars}, compression={result.compression_ratio:.1%}")
    print(f"  duration_total={result.duration_total_sec:.2f}s")
    if result.error:
        print(f"  ERROR: {result.error}")


def save_repair_result(result: RepairResult, output_dir: Path) -> None:
    """Save repair result to JSON and write fixed files to output_dir/fixes/."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "repair_result.json"
    output_file.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    # Write fixed files
    if result.fixed_files:
        fixes_dir = output_dir / "fixes"
        fixes_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in result.fixed_files.items():
            safe_name = fname.replace("/", "__").replace("\\", "__")
            (fixes_dir / safe_name).write_text(content, encoding="utf-8")

    print(f"[{result.tool}] Repair result saved to {output_file}")
    print(f"  target={result.target_project}")
    print(f"  problem={result.problem[:80]}")
    print(f"  diagnosis={result.diagnosis[:120]}")
    print(f"  fixed_files={list(result.fixed_files.keys())}")
    print(f"  tokens_in={result.tokens_in}, tokens_out={result.tokens_out}")
    print(f"  duration={result.duration_sec:.2f}s")
    if result.error:
        print(f"  ERROR: {result.error}")


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """You are a senior software engineer performing code review.
Analyze the provided code representation and identify:
1. Potential bugs or logic errors
2. Data flow issues (missing validation, unhandled edge cases)
3. Refactoring opportunities (code duplication, high coupling)
4. Security concerns
5. Performance issues

Be specific and reference function/class names. Provide actionable recommendations."""

ANALYSIS_USER_PROMPT_TEMPLATE = """Analyze this {tool_name} representation of a project.
Find bugs, data flow issues, and refactoring opportunities.

{context}"""

REPAIR_SYSTEM_PROMPT = """You are a senior software engineer fixing a real bug in a production codebase.
You will receive:
1. A compressed code representation (structure, functions, data flow)
2. A specific problem description

Your task:
- Diagnose the root cause
- Write the COMPLETE fixed source code for each file that needs changes
- Write a test that verifies the fix
- Explain the fix concisely

IMPORTANT: Output valid JSON with this exact schema:
{
  "diagnosis": "Root cause explanation",
  "fixed_files": {"relative/path/to/file.py": "complete file content..."},
  "test_code": "import pytest\\ndef test_fix(): ...",
  "summary": "One-line summary of the fix"
}"""

REPAIR_USER_PROMPT_TEMPLATE = """Fix the following problem in project "{project_name}".

## Problem
{problem}

## Code Context ({tool_name})
{context}

## Instructions
1. Diagnose the root cause based on the code context above
2. Write COMPLETE fixed file(s) — not patches, full files
3. Write a pytest test that verifies the fix
4. Return valid JSON as specified in the system prompt"""
