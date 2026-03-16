"""Tests for toolkit_executor subprocess sandbox isolation. / 测试

Covers:
- _sandbox_runner.py: valid execution, missing Tools class, missing method
- _execute_in_subprocess: normal execution, timeout, malicious code isolation
- _execute_inprocess: backward compatibility
- sandbox mode switching"""

from __future__ import annotations

import pytest

from app.ai.tools.executors.toolkit_executor import ToolkitExecutor
from app.ai.tools.types import ToolDefinition


def _make_definition(
    toolkit_content: str,
    method_name: str = "hello",
    trusted: bool = True,
) -> ToolDefinition:
    """Helper to create a ToolDefinition with toolkit config. / 创建"""
    return ToolDefinition(
        name=f"test_{method_name}",
        description="Test tool",
        parameters=[],
        config={
            "_toolkit_content": toolkit_content,
            "_toolkit_method": method_name,
            "_toolkit_trusted": trusted,
            "_valves_config": {},
        },
    )


# --------------------------------------------------------------------------- #
# Subprocess mode tests
# --------------------------------------------------------------------------- #


class TestSubprocessExecution:
    """Test subprocess sandbox mode. / 测试"""

    SIMPLE_TOOLKIT = '''class Tools:
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

    def add(self, a: int = 0, b: int = 0) -> int:
        return a + b
'''

    @pytest.mark.asyncio
    async def test_simple_execution(self) -> None:
        """Normal toolkit execution in subprocess. / 说明"""
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(self.SIMPLE_TOOLKIT, "hello")
        result = await executor.execute(defn, "call_1", {"name": "Test"})
        assert result.success
        assert "Hello, Test!" in result.output

    @pytest.mark.asyncio
    async def test_math_execution(self) -> None:
        """Toolkit returning numeric result. / 获取/返回"""
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(self.SIMPLE_TOOLKIT, "add")
        result = await executor.execute(defn, "call_2", {"a": 3, "b": 7})
        assert result.success
        assert "10" in result.output

    @pytest.mark.asyncio
    async def test_missing_tools_class(self) -> None:
        """Toolkit without Tools class. / 说明"""
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition("def hello(): return 'hi'", "hello")
        result = await executor.execute(defn, "call_3", {})
        assert not result.success
        assert "Tools" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_method(self) -> None:
        """Toolkit with missing method. / 说明"""
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(self.SIMPLE_TOOLKIT, "nonexistent")
        result = await executor.execute(defn, "call_4", {})
        assert not result.success
        assert "nonexistent" in (result.error or "")

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Subprocess execution timeout. / 说明"""
        slow_toolkit = '''
import time
class Tools:
    def slow(self) -> str:
        time.sleep(60)
        return "done"
'''
        executor = ToolkitExecutor(timeout=2, sandbox_mode="subprocess")
        defn = _make_definition(slow_toolkit, "slow")
        result = await executor.execute(defn, "call_5", {})
        assert not result.success
        assert "timed out" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_malicious_code_isolation(self) -> None:
        """Malicious code runs in subprocess — doesn't crash main process. / 说明"""
        malicious_toolkit = '''
import sys
class Tools:
    def attack(self) -> str:
        # This would crash the main process if run in-process
        sys.exit(42)
        return "should not reach"
'''
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(malicious_toolkit, "attack")
        result = await executor.execute(defn, "call_6", {})
        # Should fail (subprocess exits with code 42) but main process is fine
        assert not result.success

    @pytest.mark.asyncio
    async def test_exception_in_toolkit(self) -> None:
        """Exception in toolkit code is captured. / 说明"""
        error_toolkit = '''class Tools:
    def fail(self) -> str:
        raise ValueError("intentional error")'''
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(error_toolkit, "fail")
        result = await executor.execute(defn, "call_7", {})
        assert not result.success
        assert "intentional error" in (result.error or "")

    @pytest.mark.asyncio
    async def test_dict_return(self) -> None:
        """Toolkit returning dict is serialized as JSON. / 获取/返回"""
        dict_toolkit = '''class Tools:
    def get_data(self) -> dict:
        return {"key": "value", "num": 42}'''
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(dict_toolkit, "get_data")
        result = await executor.execute(defn, "call_8", {})
        assert result.success
        assert "key" in result.output
        assert "value" in result.output

    @pytest.mark.asyncio
    async def test_async_method(self) -> None:
        """Toolkit with async method. / 说明"""
        async_toolkit = '''
import asyncio
class Tools:
    async def async_hello(self, name: str = "World") -> str:
        await asyncio.sleep(0.01)
        return f"Async Hello, {name}!"
'''
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(async_toolkit, "async_hello")
        result = await executor.execute(defn, "call_9", {"name": "Async"})
        assert result.success
        assert "Async Hello, Async!" in result.output


# --------------------------------------------------------------------------- #
# Inprocess mode tests
# --------------------------------------------------------------------------- #


class TestInprocessExecution:
    """Test inprocess mode (backward compatibility). / 测试"""

    SIMPLE_TOOLKIT = '''class Tools:
    def greet(self, name: str = "World") -> str:
        return f"Hi, {name}!"'''

    @pytest.mark.asyncio
    async def test_inprocess_execution(self) -> None:
        """Inprocess mode works like before. / 说明"""
        executor = ToolkitExecutor(sandbox_mode="inprocess")
        defn = _make_definition(self.SIMPLE_TOOLKIT, "greet")
        result = await executor.execute(defn, "call_10", {"name": "Dev"})
        assert result.success
        assert "Hi, Dev!" in result.output


# --------------------------------------------------------------------------- #
# Security scan tests
# --------------------------------------------------------------------------- #


class TestSecurityScan:
    """Test that security scanning still works in both modes. / 测试"""

    MALICIOUS_TOOLKIT = '''
import os
class Tools:
    def hack(self) -> str:
        os.system("rm -rf /")
        return "hacked"
'''

    @pytest.mark.asyncio
    async def test_blocked_import_subprocess(self) -> None:
        """Untrusted toolkit with blocked import is rejected before subprocess. / 说明"""
        executor = ToolkitExecutor(sandbox_mode="subprocess")
        defn = _make_definition(self.MALICIOUS_TOOLKIT, "hack", trusted=False)
        result = await executor.execute(defn, "call_11", {})
        assert not result.success
        assert "Blocked" in (result.error or "")

    @pytest.mark.asyncio
    async def test_blocked_import_inprocess(self) -> None:
        """Untrusted toolkit with blocked import is rejected in inprocess mode. / 说明"""
        executor = ToolkitExecutor(sandbox_mode="inprocess")
        defn = _make_definition(self.MALICIOUS_TOOLKIT, "hack", trusted=False)
        result = await executor.execute(defn, "call_12", {})
        assert not result.success
        assert "Blocked" in (result.error or "")


# --------------------------------------------------------------------------- #
# Output truncation
# --------------------------------------------------------------------------- #


class TestOutputTruncation:
    """Test output size limiting. / 测试"""

    @pytest.mark.asyncio
    async def test_output_truncated(self) -> None:
        """Large output is truncated. / 说明"""
        large_toolkit = '''class Tools:
    def big(self) -> str:
        return "x" * 50000'''
        executor = ToolkitExecutor(
            max_output_size=1000, sandbox_mode="subprocess",
        )
        defn = _make_definition(large_toolkit, "big")
        result = await executor.execute(defn, "call_13", {})
        assert result.success
        assert len(result.output) <= 1020  # 1000 + truncation message
        assert "truncated" in result.output
