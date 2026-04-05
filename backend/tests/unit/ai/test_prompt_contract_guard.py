from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "check_prompt_contracts.py"
)
_SPEC = importlib.util.spec_from_file_location("check_prompt_contracts", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

scan_paths = _MODULE.scan_paths
scan_python_file = _MODULE.scan_python_file


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_guard_flags_direct_system_prompt_assignment(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    sample = backend_root / "app" / "ai" / "sample.py"
    _write_file(
        sample,
        """
SYSTEM_PROMPT = "You are a helpful assistant. Output ONLY valid JSON."
""".strip(),
    )

    violations = scan_python_file(sample)

    assert len(violations) == 1
    assert violations[0].context == "assignment:SYSTEM_PROMPT"


def test_guard_flags_direct_chatmessage_system_prompt(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    sample = backend_root / "app" / "services" / "ai" / "sample.py"
    _write_file(
        sample,
        """
from app.ai.types import ChatMessage

def build():
    return ChatMessage(
        role="system",
        content="You are a router assistant. Respond ONLY with JSON and do NOT explain.",
    )
""".strip(),
    )

    violations = scan_python_file(sample)

    assert len(violations) == 1
    assert violations[0].context == "chatmessage:system"


def test_guard_flags_direct_tool_description(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    sample = backend_root / "app" / "ai" / "sample.py"
    _write_file(
        sample,
        """
from app.ai.tools.types import ToolDefinition

tool = ToolDefinition(
    name="query_records",
    description="Query the database using natural language. IMPORTANT: You MUST use this tool for any count or statistics question.",
)
""".strip(),
    )

    violations = scan_python_file(sample)

    assert len(violations) == 1
    assert violations[0].context == "tool_definition:description"


def test_guard_allows_render_prompt_contract_usage(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    sample = backend_root / "app" / "ai" / "sample.py"
    _write_file(
        sample,
        """
from app.ai.prompt_contracts import render_prompt_contract

SYSTEM_PROMPT = render_prompt_contract("rag_multi_query_system")
""".strip(),
    )

    violations = scan_python_file(sample)

    assert violations == []


def test_guard_scan_paths_skips_prompt_contract_resources(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    prompt_resource = (
        backend_root
        / "app"
        / "ai"
        / "prompt_contracts"
        / "resources"
        / "fake.py"
    )
    _write_file(
        prompt_resource,
        """
SYSTEM_PROMPT = "You are a helpful assistant."
""".strip(),
    )
    sample = backend_root / "app" / "ai" / "sample.py"
    _write_file(
        sample,
        """
from app.ai.prompt_contracts import render_prompt_contract

SYSTEM_PROMPT = render_prompt_contract(
    "tool_runtime_summary",
    execution_path="fast",
    intent_summary="direct_reply",
    allowed_tools="x",
    prompt_budget=0,
    tool_round_budget=0,
    elapsed_budget_ms=0,
)
""".strip(),
    )

    violations = scan_paths(backend_root)

    assert violations == []
