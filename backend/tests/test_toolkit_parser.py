"""Test toolkit_parser.py / 测试"""

from app.ai.skills.toolkit_parser import (
    ToolkitMeta,
    parse_toolkit,
    validate_toolkit_source,
)

SAMPLE_TOOLKIT = '''
"""title: Weather API / 接口/处理器
description: Query weather forecast
version: 1.0.0
author: NovusAI
requirements: httpx>=0.25.0, pydantic"""

from pydantic import BaseModel, Field

class Valves(BaseModel):
    api_key: str = Field("", description="API Key")
    base_url: str = Field("https://api.weather.com", description="Base URL")
    timeout: int = Field(30, description="Request timeout seconds")

class Tools:
    def __init__(self):
        self.valves = Valves()

    async def get_weather(self, city: str, units: str = "metric") -> str:
        """Get weather forecast for a city / 获取/返回
        :param city: City name
        :param units: Temperature units (metric/imperial)"""
        return f"Weather for {city}"

    async def search_cities(self, query: str, limit: int = 10) -> str:
        """Search cities by name / 说明
        :param query: Search query
        :param limit: Max results"""
        return "cities"

    def sync_method(self, text: str) -> str:
        """A sync method / 说明
        :param text: Input text"""
        return text

    def _private_helper(self):
        pass
'''


def test_validate():
    errors = validate_toolkit_source(SAMPLE_TOOLKIT)
    assert errors == [], f"Unexpected errors: {errors}"

    errors = validate_toolkit_source("")
    assert len(errors) == 1
    msg = errors[0].lower()
    assert "empty" in msg or "不能为空" in errors[0]

    errors = validate_toolkit_source("class Foo:\n    pass")
    assert len(errors) == 1
    assert "Tools" in errors[0]

    errors = validate_toolkit_source("class Tools:\n    def _private(self): pass")
    assert len(errors) == 1
    msg = errors[0].lower()
    assert "no public" in msg or "公开方法" in errors[0]

    print("PASS: validate_toolkit_source")


def test_parse():
    meta = parse_toolkit(SAMPLE_TOOLKIT)
    assert meta.title == "Weather API"
    assert meta.description == "Query weather forecast"
    assert meta.version == "1.0.0"
    assert meta.author == "NovusAI"
    assert meta.requirements == ["httpx>=0.25.0", "pydantic"]

    # Tools
    assert len(meta.tools) == 3
    t0 = meta.tools[0]
    assert t0.name == "get_weather"
    assert t0.is_async is True
    assert len(t0.parameters) == 2
    assert t0.parameters[0]["name"] == "city"
    assert t0.parameters[0]["type"] == "string"
    assert t0.parameters[0]["required"] is True
    assert t0.parameters[1]["name"] == "units"
    assert t0.parameters[1]["required"] is False
    assert t0.parameters[1]["default"] == "metric"

    t1 = meta.tools[1]
    assert t1.name == "search_cities"
    assert t1.parameters[1]["name"] == "limit"
    assert t1.parameters[1]["type"] == "integer"
    assert t1.parameters[1]["default"] == 10

    t2 = meta.tools[2]
    assert t2.name == "sync_method"
    assert t2.is_async is False

    # Valves
    vs = meta.valves_schema
    assert vs["type"] == "object"
    props = vs["properties"]
    assert "api_key" in props
    assert props["api_key"]["type"] == "string"
    assert props["api_key"]["default"] == ""
    assert props["api_key"]["description"] == "API Key"
    assert props["timeout"]["type"] == "integer"
    assert props["timeout"]["default"] == 30

    print("PASS: parse_toolkit")


def test_roundtrip():
    meta = parse_toolkit(SAMPLE_TOOLKIT)
    d = meta.to_dict()
    meta2 = ToolkitMeta.from_dict(d)
    assert meta2.title == meta.title
    assert len(meta2.tools) == len(meta.tools)
    assert meta2.valves_schema == meta.valves_schema
    print("PASS: roundtrip serialization")


def test_no_valves():
    source = '''
"""title: Simple Tool / 说明
description: No valves
version: 0.1.0"""

class Tools:
    async def hello(self, name: str) -> str:
        """Say hello / 说明
        :param name: Name to greet"""
        return f"Hello {name}"
'''
    meta = parse_toolkit(source)
    assert meta.title == "Simple Tool"
    assert len(meta.tools) == 1
    assert meta.valves_schema == {}
    print("PASS: no valves")


def test_optional_and_union_types():
    source = '''
"""title: Type Test / 测试
version: 1.0.0"""

from typing import Optional

class Tools:
    async def func(
        self,
        a: str,
        b: int,
        c: float,
        d: bool,
        e: list,
        f: dict,
        g: Optional[str] = None,
        h: int | None = None,
    ) -> str:
        """Test types / 测试
        :param a: string
        :param b: integer
        :param c: number
        :param d: boolean
        :param e: array
        :param f: object
        :param g: optional string
        :param h: optional int"""
        return "ok"
'''
    meta = parse_toolkit(source)
    params = meta.tools[0].parameters
    assert params[0]["type"] == "string"
    assert params[1]["type"] == "integer"
    assert params[2]["type"] == "number"
    assert params[3]["type"] == "boolean"
    assert params[4]["type"] == "array"
    assert params[5]["type"] == "object"
    assert params[6]["type"] == "string"  # Optional[str]
    assert params[7]["type"] == "integer"  # int | None
    assert params[6]["required"] is False
    assert params[7]["required"] is False
    print("PASS: type annotations")


if __name__ == "__main__":
    test_validate()
    test_parse()
    test_roundtrip()
    test_no_valves()
    test_optional_and_union_types()
    print("\nAll tests passed!")
