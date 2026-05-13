"""Benchmark result data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


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
