"""Task registry metadata tests."""

from app.tasks.base import get_task_registry, register_task


def test_register_task_records_base_name_for_runtime_dispatch() -> None:
    @register_task(
        name="tests.tasks.sample_runtime_task",
        queue="default",
        description="sample",
    )
    def sample_runtime_task(self) -> dict:
        return {"ok": True}

    registry = get_task_registry()
    meta = registry["tests.tasks.sample_runtime_task"]

    assert meta["base"] == "BaseTask"
    assert meta["queue"] == "default"
