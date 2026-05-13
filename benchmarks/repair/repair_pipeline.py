from pathlib import Path


def _context_code2logic(project_path: Path) -> str:
    try:
        from code2logic import analyze_project, CompactGenerator, FunctionLogicGenerator

        project = analyze_project(str(project_path), use_treesitter=True, verbose=False)
        compact = CompactGenerator().generate(project)
        logic = FunctionLogicGenerator().generate(project, detail="full")
        return f"## Project Structure (code2logic compact)\n{compact}\n\n## Function Details\n{logic}"
    except Exception as e:
        return (
            f"[code2logic failed: {e}] — falling back to raw source\n"
            + read_all_source_files(project_path, max_chars=30000)
        )


def _context_baseline(project_path: Path) -> str:
    return read_all_source_files(project_path, max_chars=50000)


def _auto_detect_problem(project_path: Path) -> str:
    todo_issue = check_todo_file(project_path)
    if todo_issue:
        return todo_issue

    issues = check_common_issues(project_path)
    if issues:
        return "Auto-detected issues:\n" + "\n".join(issues[:10])

    return "General code review: find bugs, missing error handling, and refactoring opportunities in this project."


def check_todo_file(project_path: Path) -> str:
    todo = project_path / "TODO.md"
    if todo.exists():
        content = todo.read_text(encoding="utf-8", errors="ignore")
        if content.strip():
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 20:
                    return f"From TODO.md: {line[:200]}"
    return None


def check_common_issues(project_path: Path) -> list[str]:
    issues = []
    for py_file in sorted(project_path.rglob("*.py"))[:50]:
        if any(p in py_file.parts for p in ("__pycache__", "venv", ".venv", ".git")):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            rel = py_file.relative_to(project_path)
            if "# TODO" in content or "# FIXME" in content or "# HACK" in content:
                for i, line in enumerate(content.splitlines(), 1):
                    if any(tag in line for tag in ("# TODO", "# FIXME", "# HACK")):
                        issues.append(f"{rel}:{i}: {line.strip()}")
            if "raise NotImplementedError" in content:
                issues.append(f"{rel}: has NotImplementedError stubs")
            if "pass  #" in content or content.count("pass\n") > 3:
                issues.append(f"{rel}: has empty pass stubs")
        except Exception:
            continue
    return issues
