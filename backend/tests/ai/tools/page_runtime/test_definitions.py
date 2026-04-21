from app.ai.tools.page_runtime import build_page_runtime_tool_definitions


def test_build_page_runtime_tool_definitions_keeps_single_snapshot_contract() -> None:
    definitions = build_page_runtime_tool_definitions()
    definitions_by_name = {definition.name: definition for definition in definitions}

    assert "ui_get_snapshot" in definitions_by_name
    assert "ui_read_page" not in definitions_by_name
    assert "ui_read_surface" not in definitions_by_name

    snapshot_definition = definitions_by_name["ui_get_snapshot"]
    parameter_names = [parameter.name for parameter in snapshot_definition.parameters]

    assert parameter_names == ["mode", "surface_id", "ui_epoch"]
