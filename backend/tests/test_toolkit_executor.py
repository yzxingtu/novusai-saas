"""Test toolkit_executor.py"""

import asyncio
import pytest
from app.ai.tools.types import ToolDefinition, ToolParameter
from app.ai.tools.executors.toolkit_executor import ToolkitExecutor, clear_toolkit_cache


SIMPLE_TOOLKIT = '''
"""
title: Test Toolkit
description: For testing
version: 1.0.0
"""

from pydantic import BaseModel, Field

class Valves(BaseModel):
    greeting: str = Field("Hello", description="Greeting prefix")

class Tools:
    def __init__(self):
        self.valves = Valves()

    async def greet(self, name: str) -> str:
        """Greet someone
        :param name: Name
        """
        return f"{self.valves.greeting}, {name}!"

    def sync_upper(self, text: str) -> str:
        """Uppercase text
        :param text: Input
        """
        return text.upper()

    async def add_numbers(self, a: int, b: int = 0) -> str:
        """Add two numbers
        :param a: First number
        :param b: Second number
        """
        return str(a + b)

    async def return_dict(self) -> dict:
        """Return a dict"""
        return {"key": "value", "num": 42}

    async def return_none(self) -> None:
        """Return None"""
        return None

    async def raise_error(self) -> str:
        """Always raises"""
        raise ValueError("Something went wrong")
'''


def _make_definition(
    name: str,
    method: str,
    toolkit_content: str = SIMPLE_TOOLKIT,
    is_async: bool = True,
    valves_config: dict | None = None,
    params: list[ToolParameter] | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="test",
        tool_type="toolkit",
        parameters=params or [],
        config={
            "_toolkit_content": toolkit_content,
            "_toolkit_method": method,
            "_toolkit_is_async": is_async,
            "_valves_config": valves_config or {},
        },
        timeout=10,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_toolkit_cache()
    yield
    clear_toolkit_cache()


@pytest.mark.asyncio
async def test_async_method():
    executor = ToolkitExecutor()
    defn = _make_definition("greet", "greet")
    result = await executor.execute(defn, "call1", {"name": "World"})
    assert result.success is True
    assert result.output == "Hello, World!"
    assert result.duration_ms >= 0
    print("PASS: async method")


@pytest.mark.asyncio
async def test_sync_method():
    executor = ToolkitExecutor()
    defn = _make_definition("sync_upper", "sync_upper", is_async=False)
    result = await executor.execute(defn, "call2", {"text": "hello"})
    assert result.success is True
    assert result.output == "HELLO"
    print("PASS: sync method")


@pytest.mark.asyncio
async def test_valves_injection():
    executor = ToolkitExecutor()
    defn = _make_definition(
        "greet", "greet",
        valves_config={"greeting": "Hi there"},
    )
    result = await executor.execute(defn, "call3", {"name": "Alice"})
    assert result.success is True
    assert result.output == "Hi there, Alice!"
    print("PASS: valves injection")


@pytest.mark.asyncio
async def test_default_params():
    executor = ToolkitExecutor()
    defn = _make_definition("add_numbers", "add_numbers")
    result = await executor.execute(defn, "call4", {"a": 5})
    assert result.success is True
    assert result.output == "5"
    print("PASS: default params")


@pytest.mark.asyncio
async def test_dict_return():
    executor = ToolkitExecutor()
    defn = _make_definition("return_dict", "return_dict")
    result = await executor.execute(defn, "call5", {})
    assert result.success is True
    assert '"key": "value"' in result.output
    print("PASS: dict return")


@pytest.mark.asyncio
async def test_none_return():
    executor = ToolkitExecutor()
    defn = _make_definition("return_none", "return_none")
    result = await executor.execute(defn, "call6", {})
    assert result.success is True
    assert result.output == ""
    print("PASS: none return")


@pytest.mark.asyncio
async def test_method_error():
    executor = ToolkitExecutor()
    defn = _make_definition("raise_error", "raise_error")
    result = await executor.execute(defn, "call7", {})
    assert result.success is False
    assert "Something went wrong" in result.error
    print("PASS: method error")


@pytest.mark.asyncio
async def test_missing_method():
    executor = ToolkitExecutor()
    defn = _make_definition("nonexistent", "nonexistent")
    result = await executor.execute(defn, "call8", {})
    assert result.success is False
    assert "not found" in result.error.lower()
    print("PASS: missing method")


@pytest.mark.asyncio
async def test_empty_source():
    executor = ToolkitExecutor()
    defn = _make_definition("test", "test", toolkit_content="")
    result = await executor.execute(defn, "call9", {})
    assert result.success is False
    assert "empty" in result.error.lower()
    print("PASS: empty source")


@pytest.mark.asyncio
async def test_syntax_error():
    executor = ToolkitExecutor()
    defn = _make_definition("test", "test", toolkit_content="def broken(:")
    result = await executor.execute(defn, "call10", {})
    assert result.success is False
    assert "syntax" in result.error.lower()
    print("PASS: syntax error")


@pytest.mark.asyncio
async def test_argument_mismatch():
    executor = ToolkitExecutor()
    defn = _make_definition("greet", "greet")
    result = await executor.execute(defn, "call11", {"wrong_param": "x"})
    assert result.success is False
    assert "argument" in result.error.lower() or "error" in result.error.lower()
    print("PASS: argument mismatch")


@pytest.mark.asyncio
async def test_output_truncation():
    long_toolkit = '''
"""
title: Long Output
version: 1.0.0
"""

class Tools:
    async def long_output(self) -> str:
        """Return very long output"""
        return "x" * 50000
'''
    executor = ToolkitExecutor(max_output_size=100)
    defn = _make_definition("long_output", "long_output", toolkit_content=long_toolkit)
    result = await executor.execute(defn, "call12", {})
    assert result.success is True
    assert len(result.output) < 200
    assert "truncated" in result.output
    print("PASS: output truncation")


@pytest.mark.asyncio
async def test_validate():
    executor = ToolkitExecutor()
    defn = _make_definition(
        "greet", "greet",
        params=[ToolParameter(name="name", type="string", required=True)],
    )
    assert await executor.validate(defn, {"name": "test"}) is True
    assert await executor.validate(defn, {}) is False
    print("PASS: validate")


@pytest.mark.asyncio
async def test_module_cache():
    executor = ToolkitExecutor()
    defn = _make_definition("greet", "greet")

    r1 = await executor.execute(defn, "c1", {"name": "A"})
    r2 = await executor.execute(defn, "c2", {"name": "B"})
    assert r1.success and r2.success
    assert r1.output == "Hello, A!"
    assert r2.output == "Hello, B!"
    print("PASS: module cache reuse")


if __name__ == "__main__":
    asyncio.run(_run_all())


async def _run_all():
    clear_toolkit_cache()
    await test_async_method()
    clear_toolkit_cache()
    await test_sync_method()
    clear_toolkit_cache()
    await test_valves_injection()
    clear_toolkit_cache()
    await test_default_params()
    clear_toolkit_cache()
    await test_dict_return()
    clear_toolkit_cache()
    await test_none_return()
    clear_toolkit_cache()
    await test_method_error()
    clear_toolkit_cache()
    await test_missing_method()
    clear_toolkit_cache()
    await test_empty_source()
    clear_toolkit_cache()
    await test_syntax_error()
    clear_toolkit_cache()
    await test_argument_mismatch()
    clear_toolkit_cache()
    await test_output_truncation()
    clear_toolkit_cache()
    await test_validate()
    clear_toolkit_cache()
    await test_module_cache()
    clear_toolkit_cache()
    print("\nAll tests passed!")
