from __future__ import annotations

import ast
from pathlib import Path


def _extract_literal_assignment(module_path: Path, name: str):
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment {name} not found in {module_path}")


def test_module_settings_bundle_only_reports_actual_deferred_capabilities() -> None:
    backend_root = Path(__file__).resolve().parents[5]
    presets_path = (
        backend_root
        / "plugins"
        / "workflow-orchestration"
        / "backend"
        / "models"
        / "presets.py"
    )
    service_path = (
        backend_root
        / "plugins"
        / "workflow-orchestration"
        / "backend"
        / "services"
        / "module_config_service.py"
    )

    deferred_capabilities = _extract_literal_assignment(
        presets_path,
        "DEFERRED_CAPABILITIES",
    )
    deferred_codes = {item["code"] for item in deferred_capabilities}

    assert deferred_codes == {
        "generic_host_plugin_settings_ui",
        "hosted_trigger_execution_entrypoints",
    }
    assert "runtime_state_machine" not in deferred_codes
    assert "tenant_runtime_routes" not in deferred_codes
    assert "frontend_pages" not in deferred_codes

    service_source = service_path.read_text(encoding="utf-8")
    assert "DEFERRED_CAPABILITIES" in service_source
    assert '"deferred_capabilities": DEFERRED_CAPABILITIES' in service_source
