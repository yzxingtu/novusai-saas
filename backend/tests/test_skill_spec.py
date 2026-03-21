from __future__ import annotations

import pytest

from app.ai.skills.spec import SkillSpecError, parse_skill_markdown


def test_parse_skill_markdown_accepts_valid_agentscope_frontmatter():
    markdown = """---
name: weather_query
description: Use this skill when the user needs current weather or forecast
---

# Weather Query

## Overview
Use the bound capabilities for weather tasks.
"""

    spec = parse_skill_markdown(markdown)

    assert spec.name == "weather_query"
    assert spec.description.startswith("Use this skill")
    assert "# Weather Query" in spec.body


@pytest.mark.parametrize(
    "markdown, expected",
    [
        ("# Missing frontmatter", "must start with YAML frontmatter"),
        (
            """---
name: WeatherQuery
description: Use this skill when needed
---
Body
""",
            "lowercase letters, numbers, and underscores",
        ),
        (
            """---
name: weather_query
---
Body
""",
            "must include 'description'",
        ),
    ],
)
def test_parse_skill_markdown_rejects_invalid_agentscope_docs(markdown: str, expected: str):
    with pytest.raises(SkillSpecError, match=expected):
        parse_skill_markdown(markdown)
