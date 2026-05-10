"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_engine_package_keeps_heavy_exports_lazy() -> None:
    script = """
import sys
import app.ai.engine as engine_pkg

print("before", "app.ai.engine.conversation" in sys.modules)
conversation_engine = engine_pkg.ConversationEngine
print("after", "app.ai.engine.conversation" in sys.modules, conversation_engine.__name__)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith(("before ", "after "))
    ]

    assert lines == [
        "before False",
        "after True ConversationEngine",
    ]


def test_engine_package_base_engine_export_stays_lightweight() -> None:
    script = """
import sys
import app.ai.engine as engine_pkg

print("before", "app.ai.engine.conversation" in sys.modules)
base_engine = engine_pkg.BaseEngine
print("after", "app.ai.engine.conversation" in sys.modules, base_engine.__name__)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith(("before ", "after "))
    ]

    assert lines == [
        "before False",
        "after False BaseEngine",
    ]
