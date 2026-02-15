"""Benchmark: bandit - Security analysis for LLM context."""

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


def _run_bandit(app_path: Path) -> dict:
    """Run bandit security analysis."""
    try:
        result = subprocess.run(
            ["bandit", "-r", str(app_path), "-f", "json", "-ll"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # bandit returns 0 even with issues, only non-zero on errors
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _run_bandit_txt(app_path: Path) -> str:
    """Run bandit and get text output for better parsing."""
    try:
        result = subprocess.run(
            ["bandit", "-r", str(app_path), "-f", "txt", "-ll"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _analyze_security(app_path: Path) -> str:
    """Analyze code security using bandit."""
    lines = ["# Bandit Security Analysis"]

    data = _run_bandit(app_path)
    txt_output = _run_bandit_txt(app_path)

    if not data and not txt_output:
        return "[bandit: no security data available]"

    # Parse JSON results
    results = data.get("results", [])
    metrics = data.get("metrics", {})

    if results:
        # Group by severity
        by_severity = {"HIGH": [], "MEDIUM": [], "LOW": []}
        by_category = {}

        for issue in results:
            severity = issue.get("issue_severity", "LOW")
            by_severity.setdefault(severity, []).append(issue)

            category = issue.get("test_name", "unknown")
            by_category.setdefault(category, []).append(issue)

        # Report by severity
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            issues = by_severity.get(severity, [])
            if issues:
                lines.append(f"\n## {severity} Severity Issues ({len(issues)})")
                for issue in issues[:10]:  # Limit per severity
                    filename = issue.get("filename", "unknown")
                    line = issue.get("line_number", 0)
                    test = issue.get("test_name", "unknown")
                    text = issue.get("issue_text", "")
                    lines.append(f"  - {filename}:{line} [{test}] {text[:80]}")
                if len(issues) > 10:
                    lines.append(f"  ... and {len(issues) - 10} more")

        # Report by category
        lines.append(f"\n## Issue Categories")
        for category, issues in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
            lines.append(f"  - {category}: {len(issues)} occurrences")

    # Metrics summary
    if metrics:
        lines.append(f"\n## Security Metrics")

        # Find _totals or aggregate
        totals = metrics.get("_totals", {})
        if totals:
            lines.append(f"  Files scanned: {totals.get('files', 0)}")
            lines.append(f"  Lines scanned: {totals.get('loc', 0)}")
            lines.append(f"  SEVERE (High): {totals.get('SEVERITY.HIGH', 0)}")
            lines.append(f"  CONFIDENCE.HIGH: {totals.get('CONFIDENCE.HIGH', 0)}")

    # Add confidence information
    high_confidence = [r for r in results if r.get("issue_confidence") == "HIGH"]
    if high_confidence:
        lines.append(f"\n## High Confidence Issues ({len(high_confidence)})")
        for issue in high_confidence[:8]:
            filename = issue.get("filename", "unknown")
            line = issue.get("line_number", 0)
            test = issue.get("test_name", "unknown")
            lines.append(f"  - {filename}:{line} [{test}]")

    return "\n".join(lines)


def _fallback_security_analysis(app_path: Path) -> str:
    """Fallback security analysis when bandit is not available."""
    lines = ["# Bandit Security Analysis (Fallback)"]
    lines.append("[bandit not available, using pattern matching]")

    # Known security patterns to look for
    dangerous_patterns = [
        ("eval", r"\beval\s*\(", "eval() usage - arbitrary code execution"),
        ("exec", r"\bexec\s*\(", "exec() usage - arbitrary code execution"),
        ("compile", r"\bcompile\s*\(", "compile() with dynamic input"),
        ("pickle_loads", r"pickle\.loads?\s*\(", "pickle deserialization - remote code execution"),
        ("yaml_load", r"yaml\.load\s*\([^)]*\)(?!.*Loader=yaml\.SafeLoader)", "yaml.load without SafeLoader"),
        ("shell_true", r"shell\s*=\s*True", "subprocess with shell=True"),
        ("sql_string_concat", r"(execute|cursor\.execute).*[\"'].*\+|f[\"'].*SELECT", "SQL injection risk"),
        ("hardcoded_password", r"(password|passwd|pwd)\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password"),
        ("debug_true", r"debug\s*=\s*True", "Debug mode enabled"),
        ("assert_in_production", r"^assert\s+", "assert statements (removed in optimized code)"),
        ("tempfile_mktemp", r"tempfile\.mktemp", "Insecure temporary file creation"),
        ("telnetlib", r"import\s+telnetlib", "Telnetlib usage - cleartext protocol"),
        ("ftplib", r"import\s+ftplib", "FTPlib usage - cleartext protocol"),
        ("hashlib_md5", r"hashlib\.md5", "MD5 hash - cryptographically broken"),
        ("hashlib_sha1", r"hashlib\.sha1\s*\(", "SHA1 hash - cryptographically weak"),
        ("random_crypto", r"(random\.choice|random\.randint).*password|secret|token", "random for crypto"),
    ]

    import re

    _SKIP_DIRS = {"__pycache__", "venv", ".venv", "dist", "build", ".git"}
    findings = []

    for py_file in sorted(app_path.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            lines_content = content.split("\n")

            for pattern_name, pattern, description in dangerous_patterns:
                for i, line in enumerate(lines_content, 1):
                    if re.search(pattern, line):
                        findings.append({
                            "file": str(py_file.relative_to(app_path)),
                            "line": i,
                            "pattern": pattern_name,
                            "description": description,
                            "code": line.strip()[:60],
                        })
        except Exception:
            continue

    if findings:
        # Group by severity/pattern
        high_severity = [f for f in findings if f["pattern"] in ("eval", "exec", "pickle_loads", "shell_true", "sql_string_concat")]
        medium_severity = [f for f in findings if f["pattern"] in ("yaml_load", "hardcoded_password", "debug_true")]
        low_severity = [f for f in findings if f not in high_severity and f not in medium_severity]

        if high_severity:
            lines.append(f"\n## HIGH Severity Findings ({len(high_severity)})")
            for f in high_severity[:10]:
                lines.append(f"  - {f['file']}:{f['line']} [{f['pattern']}] {f['description']}")

        if medium_severity:
            lines.append(f"\n## MEDIUM Severity Findings ({len(medium_severity)})")
            for f in medium_severity[:8]:
                lines.append(f"  - {f['file']}:{f['line']} [{f['pattern']}] {f['description']}")

        lines.append(f"\n## Summary")
        lines.append(f"  Total security patterns found: {len(findings)}")
        lines.append(f"  High severity: {len(high_severity)}")
        lines.append(f"  Medium severity: {len(medium_severity)}")
        lines.append(f"  Low severity: {len(low_severity)}")
    else:
        lines.append("\n## No obvious security patterns found")

    return "\n".join(lines)


def run_benchmark() -> BenchmarkResult:
    total_start = time.time()
    app_path = get_target_project()
    raw_chars = count_raw_code_chars(app_path)

    # Phase 1: Security analysis
    analysis_start = time.time()

    try:
        subprocess.run(["bandit", "--version"], capture_output=True, timeout=5)
        context = _analyze_security(app_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        context = _fallback_security_analysis(app_path)

    analysis_duration = time.time() - analysis_start

    # Phase 2: Send to LLM
    prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
        tool_name="bandit (security analysis)",
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
            "tool": "bandit",
            "method": "fallback" if "Fallback" in context else "bandit",
        },
    )

    total_duration = time.time() - total_start

    result = BenchmarkResult(
        tool="bandit",
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
            "focus": "security_vulnerabilities",
            "categories": ["injection", "xss", "crypto", "deserialization", "secrets"],
        },
    )

    return result


if __name__ == "__main__":
    result = run_benchmark()
    output_dir = Path(__file__).parent
    save_result(result, output_dir)
