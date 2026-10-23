"""Read-mostly developer workflow capabilities.

Git capabilities call the ``git`` executable with fixed argument lists - never a
shell string - so repository names and branch text cannot become commands. All
git capabilities here are read-only; committing, pushing, resetting, and
checkout remain outside the registry in V1 (D-0026).
"""

from __future__ import annotations

import platform
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

_MAX_OUTPUT = 20_000


def _repo(raw: object) -> Path:
    path = Path(str(raw or "")).expanduser()
    if not str(raw or "").strip():
        raise ValueError("root is required")
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("root must be an absolute existing folder")
    if not (path / ".git").exists():
        raise ValueError(f"{path} is not a git repository")
    return path


def _git(root: Path, arguments: Sequence[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
    if shutil.which("git") is None:
        raise RuntimeError("git is not installed or not on PATH")
    return subprocess.run(["git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
                           "-c", "core.hooksPath=", *arguments], cwd=root,
                          env={**os.environ, "GIT_PAGER": "cat", "GIT_EXTERNAL_DIFF": ""}, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def _git_status(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _repo(args.get("root"))
    status = _git(root, ["status", "--porcelain=v1", "--branch"])
    if status.returncode != 0:
        raise RuntimeError(f"git status failed: {' '.join(status.stderr.split())[:200]}")
    lines = status.stdout.splitlines()
    branch_line = lines[0][3:] if lines and lines[0].startswith("##") else ""
    entries = []
    for line in lines[1:]:
        if len(line) > 3:
            entries.append({"state": line[:2], "path": line[3:]})
    staged = sum(1 for e in entries if e["state"] and e["state"][0] not in {"?", " "})
    untracked = sum(1 for e in entries if e["state"] == "??")
    clean = not entries
    return ToolResult("git.status", True,
                      f"{root.name} on {branch_line or 'unknown branch'}: "
                      + ("working tree clean." if clean
                         else f"{len(entries)} changed path(s), {staged} staged, {untracked} untracked."),
                      {"root": str(root), "branch": branch_line, "clean": clean,
                       "changes": entries[:200], "changed_count": len(entries),
                       "staged": staged, "untracked": untracked})


def _git_log(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _repo(args.get("root"))
    limit = max(1, min(int(args.get("limit", 10)), 100))
    result = _git(root, ["log", f"-{limit}", "--date=iso", "--pretty=format:%h%x1f%an%x1f%ad%x1f%s"])
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {' '.join(result.stderr.split())[:200]}")
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            commits.append({"hash": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
    return ToolResult("git.log", True,
                      f"{len(commits)} recent commit(s) in {root.name}."
                      + (f" Latest: {commits[0]['subject']} ({commits[0]['date'][:10]})." if commits else ""),
                      {"root": str(root), "commits": commits})


def _git_diff(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _repo(args.get("root"))
    staged = bool(args.get("staged", False))
    stat_only = bool(args.get("stat_only", True))
    arguments = ["diff", "--no-ext-diff", "--no-textconv"] + (["--cached"] if staged else []) + (["--stat"] if stat_only else ["--unified=3"])
    result = _git(root, arguments, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {' '.join(result.stderr.split())[:200]}")
    text = result.stdout[:_MAX_OUTPUT]
    return ToolResult("git.diff", True,
                      (f"{'Staged' if staged else 'Unstaged'} changes in {root.name}."
                       if text.strip() else f"No {'staged' if staged else 'unstaged'} changes in {root.name}."),
                      {"root": str(root), "staged": staged, "stat_only": stat_only,
                       "diff": text, "empty": not text.strip(), "truncated": len(result.stdout) > _MAX_OUTPUT})


def _git_branches(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = _repo(args.get("root"))
    result = _git(root, ["branch", "--all", "--format=%(refname:short)%09%(HEAD)%09%(committerdate:iso)"])
    if result.returncode != 0:
        raise RuntimeError(f"git branch failed: {' '.join(result.stderr.split())[:200]}")
    branches = []
    current = ""
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            is_head = parts[1].strip() == "*"
            branches.append({"name": parts[0], "current": is_head, "last_commit": parts[2]})
            if is_head:
                current = parts[0]
    return ToolResult("git.branches", True, f"{len(branches)} branch(es); currently on {current or 'unknown'}.",
                      {"root": str(root), "branches": branches[:100], "current": current})


def _python_env(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"],
                            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    packages = []
    if result.returncode == 0:
        import json
        try:
            packages = json.loads(result.stdout)
        except json.JSONDecodeError:
            packages = []
    query = str(args.get("query", "")).strip().casefold()
    if query:
        packages = [pkg for pkg in packages if query in str(pkg.get("name", "")).casefold()]
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    return ToolResult("python.env_info", True,
                      f"Python {platform.python_version()} at {sys.executable} "
                      f"({'virtual environment' if in_venv else 'system interpreter'}), "
                      f"{len(packages)} package(s){' matching ' + query if query else ''}.",
                      {"executable": sys.executable, "version": platform.python_version(),
                       "virtualenv": in_venv, "prefix": sys.prefix,
                       "packages": packages[:200], "package_count": len(packages)})


def _run_module(root: Path, arguments: Sequence[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-m", *arguments], cwd=root, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def _lint(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = Path(str(args.get("root", ""))).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("root must be an absolute existing folder")
    tool = str(args.get("tool", "ruff")).casefold()
    if tool not in {"ruff", "flake8"}:
        raise ValueError("tool must be ruff or flake8")
    timeout = max(10, min(int(args.get("timeout", 120)), 300))
    arguments = ["ruff", "check", "."] if tool == "ruff" else ["flake8", "."]
    try:
        result = _run_module(root, arguments, timeout)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{tool} is not installed in this interpreter") from exc
    if "No module named" in (result.stderr or ""):
        raise RuntimeError(f"{tool} is not installed in this interpreter")
    clean = result.returncode == 0
    return ToolResult("project.lint", clean,
                      f"{tool}: {'no issues found' if clean else 'issues reported'} (exit {result.returncode}).",
                      {"root": str(root), "tool": tool, "exit_code": result.returncode,
                       "clean": clean, "stdout": result.stdout[-_MAX_OUTPUT:], "stderr": result.stderr[-5000:]})


def _format_check(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    root = Path(str(args.get("root", ""))).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("root must be an absolute existing folder")
    apply_changes = bool(args.get("apply", False))
    timeout = max(10, min(int(args.get("timeout", 120)), 300))
    arguments = ["black", "."] + ([] if apply_changes else ["--check", "--diff"])
    try:
        result = _run_module(root, arguments, timeout)
    except FileNotFoundError as exc:
        raise RuntimeError("black is not installed in this interpreter") from exc
    if "No module named" in (result.stderr or ""):
        raise RuntimeError("black is not installed in this interpreter")
    completed = result.returncode == 0
    if apply_changes:
        message = ("Black completed formatting." if completed else
                   f"Black formatting failed (exit {result.returncode}); completion was not verified.")
    else:
        message = ("All files already formatted." if completed else "Formatting differences found."
                   if result.returncode == 1 else f"Black formatting check failed (exit {result.returncode}).")
    return ToolResult("project.format", completed, message,
                      {"root": str(root), "applied": (True if completed else None) if apply_changes else False,
                       "requested_apply": apply_changes, "exit_code": result.returncode,
                       "stdout": result.stdout[-_MAX_OUTPUT:], "stderr": result.stderr[-5000:]})


def _apply_reason(args: Mapping[str, Any]) -> str | None:
    if bool(args.get("apply", False)):
        return "reformatting rewrites source files in place"
    return None


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("git.status", "Read the branch, staged/unstaged changes, and untracked files of a local git repository.",
                       0, 0, {"root": str},
                       {"branch": "string", "clean": "boolean", "changes": "array", "changed_count": "integer"}, _git_status,
                       timeout_seconds=60, side_effect="read",
                       tags=("git", "status", "repo", "changes", "dirty", "clean", "uncommitted", "code"),
                       aliases=("what did i change", "is my repo clean", "uncommitted changes")),
        ToolDefinition("git.log", "Read recent commits from a local git repository.",
                       0, 0, {"root": str, "limit": int}, {"commits": "array"}, _git_log,
                       timeout_seconds=60, side_effect="read",
                       tags=("git", "log", "commits", "history", "recent", "who", "when", "code"),
                       aliases=("what did i commit", "recent commits", "commit history")),
        ToolDefinition("git.diff", "Read the staged or unstaged diff of a local git repository, as a stat summary or full patch.",
                       0, 0, {"root": str, "staged": bool, "stat_only": bool},
                       {"diff": "string", "empty": "boolean"}, _git_diff,
                       timeout_seconds=90, side_effect="read",
                       tags=("git", "diff", "changes", "patch", "review", "code", "modified"),
                       aliases=("show me my changes", "what is different", "review my diff")),
        ToolDefinition("git.branches", "List local and remote branches and identify the checked-out branch.",
                       0, 0, {"root": str}, {"branches": "array", "current": "string"}, _git_branches,
                       timeout_seconds=60, side_effect="read",
                       tags=("git", "branch", "branches", "checkout", "current", "code"),
                       aliases=("what branch am i on", "list branches")),
        ToolDefinition("python.env_info", "Report the active Python interpreter, whether it is a virtual environment, and installed packages.",
                       0, 0, {"query": str},
                       {"executable": "string", "version": "string", "virtualenv": "boolean", "package_count": "integer"}, _python_env,
                       timeout_seconds=90, side_effect="read",
                       tags=("python", "environment", "venv", "packages", "pip", "installed", "version", "dependency"),
                       aliases=("which python am i using", "is that package installed", "my venv")),
        ToolDefinition("project.lint", "Run ruff or flake8 over a project folder and report whether it is clean.",
                       2, 2, {"root": str, "tool": str, "timeout": int},
                       {"clean": "boolean", "exit_code": "integer", "stdout": "string"}, _lint,
                       timeout_seconds=300, side_effect="external_action",
                       tags=("lint", "ruff", "flake8", "style", "quality", "python", "check", "code"),
                       aliases=("lint my project", "any style errors")),
        ToolDefinition("project.format", "Check black formatting for a project, or with apply=true reformat files in place.",
                       2, 2, {"root": str, "apply": bool, "timeout": int},
                       {"applied": "boolean|null", "exit_code": "integer"}, _format_check,
                       timeout_seconds=300, side_effect="reversible_write",
                       requires_confirmation_if=_apply_reason,
                       tags=("format", "black", "style", "reformat", "python", "code", "tidy"),
                       aliases=("format my code", "is my code formatted")),
    )
