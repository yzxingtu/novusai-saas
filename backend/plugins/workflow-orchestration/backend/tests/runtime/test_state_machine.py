from __future__ import annotations


def test_derive_run_status_prefers_running_waiting_and_failed(load_plugin_backend_module) -> None:
    state_machine = load_plugin_backend_module("runtime.state_machine")

    assert state_machine.derive_run_status_from_nodes(["running", "pending"]) == "running"
    assert state_machine.derive_run_status_from_nodes(["waiting_approval", "succeeded"]) == "waiting_approval"
    assert state_machine.derive_run_status_from_nodes(["failed_terminal", "succeeded"]) == "failed"
    assert state_machine.derive_run_status_from_nodes(["failed_retryable"]) == "recovering"


def test_derive_run_status_handles_terminal_sets(load_plugin_backend_module) -> None:
    state_machine = load_plugin_backend_module("runtime.state_machine")

    assert state_machine.derive_run_status_from_nodes(["succeeded", "skipped"]) == "completed"
    assert state_machine.derive_run_status_from_nodes(["cancelled"]) == "cancelled"
    assert state_machine.derive_run_status_from_nodes([]) == "queued"


def test_available_actions_and_buckets_match_constants(load_plugin_backend_module) -> None:
    state_machine = load_plugin_backend_module("runtime.state_machine")

    assert state_machine.run_status_bucket("pending") == "pending"
    assert state_machine.run_status_bucket("waiting_input") == "waiting_human"
    assert state_machine.node_status_bucket("failed_retryable") == "failed"
    assert state_machine.available_run_actions("failed") == ["retry", "recover", "replay"]
    assert state_machine.available_artifact_actions("ready") == ["feedback", "download"]
