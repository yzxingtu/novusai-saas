"""Test type: behavioral.

Scope: plugin config schema validation rejects unknown runtime config fields.
Real dependencies: PluginService static validator.
Mocked dependencies: none.
"""

from __future__ import annotations

import pytest

from app.exceptions.base import ValidationException
from app.services.system.plugin_service import PluginService


def test_plugin_config_rejects_unknown_fields() -> None:
    schema = {
        "properties": {
            "api_key": {"type": "string"},
        },
        "required": ["api_key"],
    }

    with pytest.raises(ValidationException, match="Unknown plugin config field"):
        PluginService._validate_config_against_schema(
            {"api_key": "secret", "old_field": "kept-before"},
            schema,
        )
