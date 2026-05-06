"""Regression tests for observable wizard checkpoints (MCP + compile shape)."""
from __future__ import annotations

from tooling.ainl_get_started import (
    CheckpointStatus,
    WizardState,
    _compile_result_has_ir_labels,
    _pending_mcp_from_compile_result,
    initialize_wizard_state,
    wizard_state_from_tool_result,
)


def test_compile_result_has_ir_labels_mcp_shape():
    ir = {"labels": {"_entry": {"nodes": []}}}
    assert _compile_result_has_ir_labels({"ok": True, "ir": ir}) is True
    assert _compile_result_has_ir_labels({"ok": True, "labels": {"x": 1}}) is True
    assert _compile_result_has_ir_labels({"ok": True, "ir": {}}) is False


def test_ir_compiled_advances_from_mcp_compile_envelope():
    state = initialize_wizard_state(
        goal="test",
        task_type="core_workflow",
        subtypes=[],
        adapters=[],
    )
    ir = {"labels": {"L1": {"nodes": []}}, "execution_requirements": {"required_capabilities": ["core"]}}
    out = {
        "ok": True,
        "ir": ir,
        "required_adapters": [],
        "strict": True,
    }
    state = wizard_state_from_tool_result(state, "ainl_compile", out)
    assert state.checkpoints.get("ir_compiled") and state.checkpoints["ir_compiled"].status == CheckpointStatus.COMPLETE
    assert state.checkpoints.get("adapters_configured") and state.checkpoints["adapters_configured"].status == CheckpointStatus.COMPLETE
    assert state.pending_mcp_adapters == []


def test_pending_mcp_adapters_and_run_proves_adapters_configured():
    state = initialize_wizard_state(
        goal="fetch",
        task_type="adapter_workflow",
        subtypes=["http"],
        adapters=["http"],
    )
    # Simulate MCP compile result for an HTTP graph
    ir = {"labels": {"L1": {"nodes": []}}}
    compile_out = {
        "ok": True,
        "ir": ir,
        "required_adapters": ["http"],
        "runtime_readiness": {},
        "strict": True,
    }
    assert _pending_mcp_from_compile_result(compile_out) == ["http"]
    state = wizard_state_from_tool_result(state, "ainl_compile", compile_out)
    assert state.pending_mcp_adapters == ["http"]
    assert state.checkpoints["adapters_configured"].status == CheckpointStatus.IN_PROGRESS

    run_ok = {
        "ok": True,
        "trace_id": "t1",
        "_wizard_ainl_run_adapters": {"enable": ["http"], "http": {"allow_hosts": ["example.com"]}},
    }
    state = wizard_state_from_tool_result(state, "ainl_run", run_ok)
    assert state.checkpoints["run_succeeded"].status == CheckpointStatus.COMPLETE
    assert state.checkpoints["adapters_configured"].status == CheckpointStatus.COMPLETE


def test_strict_examples_checkpoint_via_helper_tool():
    ws = WizardState(session_id="s", goal="g")
    ws = wizard_state_from_tool_result(
        ws,
        "ainl_wizard_checkpoint",
        {"ok": True, "checkpoint_id": "strict_examples_reviewed"},
    )
    assert ws.checkpoints["strict_examples_reviewed"].status == CheckpointStatus.COMPLETE


def test_augment_mcp_server_smoke():
    from scripts.ainl_mcp_server import _augment_with_wizard_state

    base = {"ok": True, "required_adapters": [], "strict": True}
    ws = initialize_wizard_state("hi", "core_workflow", [], [])
    payload = _augment_with_wizard_state(base, "ainl_validate", ws.to_dict())
    assert "wizard_state_json" in payload
    assert "full_source_validated" in (payload.get("wizard_checkpoints_complete") or [])
