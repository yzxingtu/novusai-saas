from __future__ import annotations

from app.plugins.runtime_recovery import build_plugin_recovery_state


def test_recovery_state_prioritizes_dependency_install_for_error_plugins() -> None:
    state = build_plugin_recovery_state(
        dependency_status={"overall": "missing"},
        error_message="runtime import failed",
        manifest={"extensions": {}},
        status="error",
    )

    assert state["reason"] == "missing_dependencies"
    assert state["severity"] == "error"
    assert state["primary_action"] == "install_dependencies"
    assert state["secondary_actions"] == ["repair"]


def test_recovery_state_marks_scheduler_desync_with_refresh_action() -> None:
    state = build_plugin_recovery_state(
        dependency_status={"overall": "installed"},
        error_message="Failed to refresh scheduled tasks for plugin demo",
        manifest={"extensions": {"tasks": [{"name": "digest"}]}},
        status="error",
    )

    assert state["reason"] == "schedule_refresh_failed"
    assert state["primary_action"] == "refresh_schedules"
    assert state["has_scheduled_tasks"] is True


def test_recovery_state_prefers_force_cleanup_when_files_are_missing() -> None:
    state = build_plugin_recovery_state(
        dependency_status={"overall": "missing"},
        error_message="Plugin package missing from disk",
        manifest={"extensions": {"tasks": [{"name": "digest"}]}},
        status="error",
    )

    assert state["reason"] == "missing_from_disk"
    assert state["primary_action"] == "force_cleanup"
    assert state["secondary_actions"] == []


def test_recovery_state_defaults_to_healthy_when_no_attention_needed() -> None:
    state = build_plugin_recovery_state(
        dependency_status={"overall": "installed"},
        error_message=None,
        manifest={"extensions": {"tasks": [{"name": "digest"}]}},
        status="enabled",
    )

    assert state["reason"] == "none"
    assert state["severity"] == "healthy"
    assert state["needs_attention"] is False
    assert state["has_scheduled_tasks"] is True
