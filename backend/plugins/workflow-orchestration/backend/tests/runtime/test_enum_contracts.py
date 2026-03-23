from __future__ import annotations

from pathlib import Path

def test_checkpoint_type_enum_and_model_default_match_runtime_contract(
    load_plugin_backend_module,
) -> None:
    model_enums = load_plugin_backend_module("models.enums")
    runtime_constants = load_plugin_backend_module("runtime.constants")

    enum_values = {item.value for item in model_enums.CheckpointTypeEnum}
    assert enum_values == set(runtime_constants.CHECKPOINT_TYPES)

    backend_root = Path(__file__).resolve().parents[5]
    runtime_model_source = (
        backend_root
        / "plugins"
        / "workflow-orchestration"
        / "backend"
        / "models"
        / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "default=CheckpointTypeEnum.RUN_START_CHECKPOINT.value" in runtime_model_source
