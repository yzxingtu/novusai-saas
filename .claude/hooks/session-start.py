#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session start hook with budgeted Trellis summary injection.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

if sys.platform == "win32":
    import io as _io

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    elif hasattr(sys.stdout, "detach"):
        sys.stdout = _io.TextIOWrapper(  # type: ignore[union-attr]
            sys.stdout.detach(),
            encoding="utf-8",
            errors="replace",
        )


def should_skip_injection() -> bool:
    return (
        os.environ.get("CLAUDE_NON_INTERACTIVE") == "1"
        or os.environ.get("OPENCODE_NON_INTERACTIVE") == "1"
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def run_command(args: list[str], cwd: Path, timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (result.stdout or "").strip()


def read_developer_name(trellis_dir: Path) -> str | None:
    developer = read_text(trellis_dir / ".developer").strip()
    return developer or None


def read_current_task(project_dir: Path, trellis_dir: Path) -> tuple[str | None, Path | None]:
    task_ref = read_text(trellis_dir / ".current-task").strip()
    if not task_ref:
        return None, None
    task_path = Path(task_ref)
    if task_path.is_absolute():
        resolved = task_path
    else:
        resolved = (project_dir / task_ref).resolve()
    if not resolved.exists():
        return task_ref, None
    return task_ref, resolved


def load_task_payload(task_dir: Path | None) -> dict:
    if task_dir is None:
        return {}
    try:
        return json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def task_artifact_status(task_dir: Path | None, task_data: dict) -> str:
    if task_dir is None:
        return "No active task."

    execution_path = str(task_data.get("execution_path") or "normal").strip() or "normal"
    required = [str(item).strip() for item in task_data.get("required_artifacts", []) if str(item).strip()]
    missing = [name for name in required if not (task_dir / name).exists()]
    lines = [
        f"Task: {task_data.get('title') or task_dir.name}",
        f"Path: {execution_path}",
        f"Status: {task_data.get('status') or 'unknown'}",
    ]
    if missing:
        lines.append(f"Missing artifacts: {', '.join(missing)}")
    else:
        lines.append("Required artifacts: ready")
    return "\n".join(lines)


def git_state_summary(project_dir: Path) -> str:
    branch = run_command(["git", "branch", "--show-current"], project_dir) or "unknown"
    dirty_lines = run_command(["git", "status", "--short"], project_dir).splitlines()
    dirty_count = len([line for line in dirty_lines if line.strip()])
    preview = ", ".join(line.strip() for line in dirty_lines[:8] if line.strip())
    if len(dirty_lines) > 8:
        preview = f"{preview}, ..."
    lines = [
        f"Branch: {branch}",
        f"Dirty files: {dirty_count}",
    ]
    if preview:
        lines.append(f"Dirty preview: {preview}")
    return "\n".join(lines)


def build_additional_context(project_dir: Path) -> str:
    trellis_dir = project_dir / ".trellis"
    current_task_ref, current_task_dir = read_current_task(project_dir, trellis_dir)
    task_data = load_task_payload(current_task_dir)

    output = StringIO()
    output.write("<session-context>\n")
    output.write("Trellis uses a path-based workflow. Start with the lightest path that safely fits the task.\n")
    output.write("</session-context>\n\n")

    output.write("<current-state>\n")
    developer = read_developer_name(trellis_dir)
    if developer:
        output.write(f"Developer: {developer}\n")
    output.write(git_state_summary(project_dir))
    if current_task_ref:
        output.write(f"\nCurrent task ref: {current_task_ref}")
    output.write("\n</current-state>\n\n")

    output.write("<path-rules>\n")
    output.write("fast: no task by default; direct answer or direct edit; no heavy context\n")
    output.write("normal: task recommended; require prd.md; keep context minimal\n")
    output.write("deep: task required; require prd.md + info.md; curated context only\n")
    output.write("Retired: heavy-by-default workflow escalation, release-step lifecycle coupling, marker loops\n")
    output.write("</path-rules>\n\n")

    output.write("<canonical-spec>\n")
    output.write(".trellis/workflow.md\n")
    output.write(".trellis/spec/guides/trellis-paths.md\n")
    output.write(".trellis/spec/backend/index.md\n")
    output.write(".trellis/spec/frontend/index.md\n")
    output.write(".trellis/spec/ai-runtime/index.md\n")
    output.write("</canonical-spec>\n\n")

    output.write("<task-status>\n")
    output.write(task_artifact_status(current_task_dir, task_data))
    output.write("\n</task-status>\n\n")

    output.write("<ready>\n")
    output.write("Do not re-read the full workflow or all spec indexes by default.\n")
    output.write("Read only the canonical files needed for the current task and selected path.\n")
    output.write("</ready>")
    return output.getvalue()


def main() -> None:
    if should_skip_injection():
        sys.exit(0)

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": build_additional_context(project_dir),
        }
    }
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
