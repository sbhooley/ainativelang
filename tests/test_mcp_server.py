"""Tests for the AINL MCP server tool and resource functions.

These test the tool functions directly as Python callables so the MCP SDK
is not required at test time.  Transport-level integration (stdio round-trip)
is deferred to manual testing with the MCP Inspector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from scripts.ainl_mcp_server import (
    ainl_adapter_contract,
    ainl_get_started,
    ainl_validate,
    ainl_compile,
    ainl_capabilities,
    ainl_security_report,
    ainl_run,
    ainl_fitness_report,
    ainl_ir_diff,
    ainl_ptc_signature_check,
    ainl_trace_export,
    ainl_ptc_run,
    _load_json,
    _merge_policy,
    _merge_limits,
    _COMPILE_CACHE,
    _COMPILE_CACHE_LOCK,
    _read_integration_doc,
    _strict_valid_examples_json,
    _adapter_contracts_bundle_json,
    _contract_alignment_hints_from_ir,
    _merge_contract_alignment_into_output,
)
from tooling.ainl_get_started import reverse_engineer_corpus, template_status_for_path


VALID_CODE = "S app api /api\nL1:\nR core.ADD 2 3 ->sum\nJ sum"
INVALID_CODE = "S app api /api\nL1:\nR !!!invalid!!!"
NETWORK_CODE = "S app api /api\nL1:\nR http.Get \"https://example.com\" ->resp\nJ resp"
FS_CODE = "S app core noop\nL1:\nR fs.write \"out.csv\" \"name\\n\" ->written\nJ written"
HTTP_FS_CODE = "S app core noop\nL1:\nR http.GET \"https://example.com\" ->resp\nR fs.write \"out.csv\" \"name\\n\" ->written\nJ written"
JSON_DIRECT_RETURN_CODE = "S app core noop\nL1:\nJ {\"ok\": true}"
COMPACT_JSON_DIRECT_RETURN_CODE = "workflow:\n out {\"ok\": true}"
UNKNOWN_ADAPTER_VERB = "S app core noop\ncore.NotARealTopLevelVerb 1\n"


# ---------------------------------------------------------------------------
# ainl-get-started
# ---------------------------------------------------------------------------

class TestGetStarted:
    def test_scraper_goal_blocks_authoring_until_contracts(self):
        result = ainl_get_started(
            goal="I need a scraper that visits a site, fills a form, scrapes results, and saves a CSV."
        )
        assert result["ok"] is True
        assert result["inferred_task_type"] == "adapter_workflow"
        assert "browser_or_http_scraper" in result["subtypes"]
        assert "local_file_output" in result["subtypes"]
        assert result["wizard_state"]["can_author_now"] is False
        missing = set(result["wizard_state"]["missing_checkpoints"])
        assert "ainl_capabilities" in missing
        assert "adapter_contract:http_or_browser" in missing
        assert "adapter_contract:fs" in missing
        assert result["next_tool_call"] == {"tool": "ainl_capabilities", "args": {}}
        guide = result["intent_operation_guide"]
        assert any(row["step"] == "Start the workflow" for row in guide)
        assert any(row.get("blocked_by") == "adapter_contract:http_or_browser" for row in guide)
        assert result["agent_authoring_policy"]["adapter_specific_source_allowed"] is False
        assert "Do not write adapter-specific AINL lines yet." in result["agent_authoring_policy"]["must_not_do"]

    def test_twilio_goal_detects_llm_state_and_messaging(self):
        result = ainl_get_started(
            goal="I need to build a Twilio texting bot that texts a batch of phone numbers and uses AI for replies."
        )
        assert result["ok"] is True
        assert "messaging_or_social" in result["subtypes"]
        assert "llm_generation_or_classification" in result["subtypes"]
        assert "stateful_tracking" in result["subtypes"]
        assert "llm" in result["adapter_contracts_needed"]
        assert "state_or_database" in result["adapter_contracts_needed"]

    def test_core_goal_can_author_with_starter_scaffold(self):
        result = ainl_get_started(goal="Make a hello world AINL workflow.")
        assert result["ok"] is True
        assert result["wizard_state"]["can_author_now"] is True
        assert result["starter_scaffold"]["code"].startswith("workflow:")
        assert result["next_tool_call"]["tool"] == "ainl_validate"
        assert "quick_start" in result
        assert "ordered_checklist" in result
        assert result["strict_valid_example_index"]["resource_uri"] == "ainl://strict-valid-examples"
        assert result["strict_valid_example_index"]["count"] >= 1

    def test_missing_goal_is_tool_call_error(self):
        result = ainl_get_started()
        assert result["ok"] is False
        assert result["tool_call_error"] is True
        assert "goal" in result["next_step"]

    def test_step_local_examples_do_not_advance_wizard(self):
        result = ainl_get_started(current_step="output_write", request_examples_for="fs_write_csv")
        assert result["wizard_stage"] == "incremental_authoring"
        assert result["current_step"] == "output_write"
        assert result["step_status"] == "examples_only"
        assert any("fs.write" in row["code"] for row in result["examples"])

    def test_reverse_engineer_source_returns_human_goals(self):
        code = (ROOT / "examples" / "monitoring" / "solana-balance.ainl").read_text(
            encoding="utf-8"
        )
        result = ainl_get_started(
            reverse_source=code,
            reverse_path="examples/monitoring/solana-balance.ainl",
        )
        assert result["ok"] is True
        rev = result["result"]
        assert "solana" in rev["detected_adapters"]
        assert any("Solana wallet" in goal for goal in rev["reconstructed_user_goals"])
        assert rev["workflow_family"] == "blockchain_monitoring"
        assert rev["recommended_template_status"] == "strict-valid"
        assert "required_contracts" in rev
        assert "adapter_contracts_needed" in rev["expected_classifier"]

    def test_reverse_corpus_scanner_marks_strict_and_demo_signal(self):
        strict_path = ROOT / "examples" / "monitoring" / "solana-balance.ainl"
        demo_path = ROOT / "demo" / "heartbeat.lang"
        result = reverse_engineer_corpus([strict_path, demo_path], repo_root=ROOT)
        assert result["ok"] is True
        assert "patterns" in result
        statuses = {row["source_file"]: row["recommended_template_status"] for row in result["fixtures"]}
        assert statuses["examples/monitoring/solana-balance.ainl"] == "strict-valid"
        assert statuses["demo/heartbeat.lang"] == "experimental_or_negative_signal"
        assert all(row["reconstructed_user_goals"] for row in result["fixtures"])

    def test_template_status_uses_artifact_profiles(self):
        assert template_status_for_path("examples/compact/hello_compact.ainl") == "strict-valid"
        assert template_status_for_path("demo/heartbeat.lang") == "experimental_or_negative_signal"

    def test_capabilities_snapshot_moves_to_contract_resolution(self):
        result = ainl_get_started(
            goal="I need a scraper that visits a site, fills a form, scrapes results, and saves a CSV.",
            capabilities_snapshot={"adapters": {"core": {}, "http": {}, "browser": {}, "fs": {}}},
        )
        assert result["wizard_stage"] == "contract_resolution"
        assert "ainl_capabilities" in result["wizard_state"]["complete_checkpoints"]
        assert result["next_tool_call"]["tool"] == "ainl_adapter_contract"
        assert result["next_tool_call"]["args"]["adapter"] == "http_or_browser"

    def test_contract_snapshots_unlock_incremental_authoring_scaffold(self):
        result = ainl_get_started(
            goal="I need a scraper that visits a site, fills a form, scrapes results, and saves a CSV.",
            capabilities_snapshot={"adapters": {"core": {}, "http": {}, "browser": {}, "fs": {}}},
            adapter_contracts_snapshot={"http_or_browser": {"ok": True}, "fs": {"ok": True}},
        )
        assert result["wizard_stage"] == "incremental_authoring"
        assert result["wizard_state"]["can_author_now"] is True
        scaffold = result["partial_scaffold"]
        names = {row["name"] for row in scaffold["slices"]}
        assert {"adapter_access_http_path", "adapter_access_browser_path", "output_write"}.issubset(names)
        joined = "\n".join("\n".join(row["lines"]) for row in scaffold["slices"])
        assert "page = http.GET target_url" in joined
        assert "session = browser.NAVIGATE target_url" in joined
        assert "written = fs.write output_path csv" in joined
        assert result["agent_authoring_policy"]["adapter_specific_source_allowed"] is True

    def test_adapter_contract_http_is_real_not_placeholder(self):
        result = ainl_adapter_contract("http")
        assert result["ok"] is True
        assert result["status"] == "known"
        assert "GET" in result["verbs"]
        assert result["verbs"]["GET"]["args"] == ["url: string", "headers?: dict", "timeout_s?: number"]
        assert "runtime_registration" in result
        assert result["runtime_registration"]["http"]["allow_hosts"] == ["<host>"]

    def test_adapter_contract_browser_or_http_decision(self):
        result = ainl_adapter_contract("http_or_browser")
        assert result["ok"] is True
        assert result["status"] == "composite"
        assert {row["choose"] for row in result["decision_guide"]} == {"http", "browser"}
        adapters = {row["adapter"] for row in result["contracts"]}
        assert {"http", "browser"}.issubset(adapters)

    def test_adapter_contract_unknown_guides_discovery(self):
        result = ainl_adapter_contract("x")
        assert result["ok"] is False
        assert result["status"] == "unknown"
        assert "ainl_capabilities" in result["next_step"]


# ---------------------------------------------------------------------------
# ainl-validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_missing_code_is_tool_call_error(self):
        result = ainl_validate()
        assert result["ok"] is False
        assert result.get("tool_call_error") is True
        assert "copy_paste_next_call" in result
        assert result["copy_paste_next_call"]["tool"] == "ainl_validate"

    def test_valid_code_returns_ok(self):
        result = ainl_validate(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert result["errors"] == []
        assert "recommended_next_tools" in result
        assert "ainl_compile" in result["recommended_next_tools"]
        assert result["required_adapters"] == []
        assert result["runtime_readiness"]["ready"] is True
        assert "compiler_vs_runtime_note" in result
        assert result.get("strict") is True
        assert "strict_mode_note" not in result

    def test_validate_nonstrict_includes_mode_note(self):
        result = ainl_validate(VALID_CODE, strict=False)
        assert result["ok"] is True
        assert result.get("strict") is False
        assert "strict_mode_note" in result
        assert "strict=false" in result["strict_mode_note"].lower() or "strict=False" in result["strict_mode_note"]

    def test_validate_reports_required_adapters_and_suggested_payload(self):
        result = ainl_validate(HTTP_FS_CODE, strict=True)
        assert result["ok"] is True
        assert result["required_adapters"] == ["fs", "http"]
        readiness = result["runtime_readiness"]
        assert readiness["ready"] is False
        assert readiness["missing_adapters"] == ["fs", "http"]
        suggested = readiness["suggested_adapters"]
        assert suggested["enable"] == ["fs", "http"]
        assert suggested["http"]["allow_hosts"] == ["example.com"]
        assert suggested["fs"]["root"] == "<absolute-workspace-or-output-root>"

    def test_invalid_code_returns_errors(self):
        result = ainl_validate(INVALID_CODE, strict=True)
        assert result["ok"] is False
        assert len(result["errors"]) > 0
        assert "recommended_next_tools" in result
        assert "ainl_validate" in result["recommended_next_tools"]
        assert "repair_recipe" in result
        assert isinstance(result["repair_recipe"], dict)
        if "recommended_resources" in result:
            assert result["recommended_resources"][0] == "ainl://strict-authoring-cheatsheet"
            assert "ainl://adapter-contracts" in result["recommended_resources"]
        else:
            assert result["recommended_next_tools"][0] == "ainl_capabilities"

    def test_validate_returns_llm_native_diagnostics(self):
        result = ainl_validate(INVALID_CODE, strict=True)
        assert "diagnostics" in result
        for d in result["diagnostics"]:
            assert "llm_repair_hint" in d

    def test_validate_failure_includes_primary_and_repair_steps(self):
        result = ainl_validate(INVALID_CODE, strict=True)
        assert result["ok"] is False
        assert "primary_diagnostic" in result
        assert result["primary_diagnostic"] is not None
        assert "agent_repair_steps" in result
        assert len(result["agent_repair_steps"]) >= 1
        # Snippet around the error line (when lineno is known)
        pd = result["primary_diagnostic"]
        assert "llm_repair_hint" in pd
        if "source_context" in pd:
            assert "numbered_lines" in pd["source_context"]
            assert "caret" in pd["source_context"]

    def test_validate_unknown_verb_includes_suggested_fix(self):
        result = ainl_validate(UNKNOWN_ADAPTER_VERB, strict=True)
        assert result["ok"] is False
        pd = result["primary_diagnostic"]
        assert pd is not None
        assert pd.get("suggested_fix") or pd.get("llm_repair_hint")

    def test_validate_unknown_verb_recommended_prioritizes_capabilities(self):
        result = ainl_validate(UNKNOWN_ADAPTER_VERB, strict=True)
        assert result["ok"] is False
        tools = result["recommended_next_tools"]
        assert tools[0] == "ainl_capabilities"
        # Adapter/verb issues: strict cheatsheet + contracts, not HTTP integration cheatsheet.
        assert "recommended_resources" in result
        assert result["recommended_resources"][0] == "ainl://strict-authoring-cheatsheet"
        assert "ainl://adapter-contracts" in result["recommended_resources"]
        assert "ainl://authoring-cheatsheet" not in result["recommended_resources"]

    def test_validate_strict_rejects_direct_json_join(self):
        result = ainl_validate(JSON_DIRECT_RETURN_CODE, strict=True)
        assert result["ok"] is False
        pd = result["primary_diagnostic"]
        assert pd is not None
        assert pd["kind"] == "strict_validation_failure"
        assert "inline JSON/object literals" in pd["message"]
        assert "Do not write `J { ... }`" in pd["suggested_fix"]
        assert "source_context" in pd
        rr = result.get("repair_recipe") or {}
        assert "ainl://strict-authoring-cheatsheet" in rr.get("resources", [])

    def test_validate_strict_rejects_compact_direct_json_out(self):
        result = ainl_validate(COMPACT_JSON_DIRECT_RETURN_CODE, strict=True)
        assert result["ok"] is False
        pd = result["primary_diagnostic"]
        assert pd is not None
        assert "inline JSON/object literals" in pd["message"]
        assert "`out { ... }`" in pd["suggested_fix"]

    def test_validate_ok_recommends_compile_first(self):
        result = ainl_validate(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert result["recommended_next_tools"][0] == "ainl_compile"
        assert "required_adapters" in result
        assert result["runtime_readiness"]["ready"] is True

    def test_validate_and_compile_align_fs_required_adapters(self):
        v = ainl_validate(FS_CODE, strict=True)
        c = ainl_compile(FS_CODE, strict=True)
        assert v["ok"] and c["ok"]
        assert v["required_adapters"] == c["required_adapters"] == ["fs"]
        assert v["runtime_readiness"]["ready"] is False
        assert c["runtime_readiness"]["ready"] is False

    def test_validate_unknown_verb_repair_recipe_discourages_stripping_adapters(self):
        result = ainl_validate(UNKNOWN_ADAPTER_VERB, strict=True)
        assert result["ok"] is False
        steps = (result.get("repair_recipe") or {}).get("steps") or []
        assert any("Do not remove non-core" in s for s in steps)


# ---------------------------------------------------------------------------
# ainl-compile
# ---------------------------------------------------------------------------

class TestCompile:
    def test_compile_valid_returns_ir(self):
        result = ainl_compile(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert "ir" in result
        ir = result["ir"]
        assert "labels" in ir
        assert "recommended_next_tools" in result
        assert "ainl_run" in result["recommended_next_tools"]
        assert result["runtime_readiness"]["ready"] is True

    def test_compile_reports_required_adapters(self):
        result = ainl_compile(FS_CODE, strict=True)
        assert result["ok"] is True
        assert result["required_adapters"] == ["fs"]
        assert result["runtime_readiness"]["suggested_adapters"]["enable"] == ["fs"]

    def test_compile_ok_inserts_ainl_capabilities_after_run_when_adapters_required(self):
        """Phase 2 roadmap: after compile, next steps should surface capability discovery for adapters=…"""
        for code in (FS_CODE, HTTP_FS_CODE):
            result = ainl_compile(code, strict=True)
            assert result["ok"] is True
            assert result["required_adapters"]
            tools = result["recommended_next_tools"]
            assert tools[0] == "ainl_run"
            assert tools[1] == "ainl_capabilities"
            assert "compiler_vs_runtime_note" in result

    def test_compile_invalid_returns_errors(self):
        result = ainl_compile(INVALID_CODE, strict=True)
        assert result["ok"] is False
        assert "errors" in result
        assert "recommended_next_tools" in result
        assert "repair_recipe" in result
        if "recommended_resources" in result:
            assert result["recommended_resources"][0] == "ainl://strict-authoring-cheatsheet"
            assert "ainl://adapter-contracts" in result["recommended_resources"]
        else:
            assert result["recommended_next_tools"][0] == "ainl_capabilities"

    def test_compile_invalid_matches_validate_diagnostics(self):
        result = ainl_compile(INVALID_CODE, strict=True)
        assert result["ok"] is False
        assert "diagnostics" in result
        assert "primary_diagnostic" in result
        assert result["primary_diagnostic"] is not None
        assert "agent_repair_steps" in result

    def test_compile_nonstrict(self):
        result = ainl_compile(VALID_CODE, strict=False)
        assert result["ok"] is True
        assert result.get("strict") is False
        assert "strict_mode_note" in result

    def test_compile_cache_reuses_validate_compile_ir(self):
        with _COMPILE_CACHE_LOCK:
            _COMPILE_CACHE.clear()
        before = ainl_capabilities()["mcp_telemetry"].get("compile_cache_hits", 0)
        assert ainl_validate(VALID_CODE, strict=True)["ok"] is True
        assert ainl_compile(VALID_CODE, strict=True)["ok"] is True
        after = ainl_capabilities()["mcp_telemetry"].get("compile_cache_hits", 0)
        assert after >= before + 1


# ---------------------------------------------------------------------------
# ainl-adapter-contract (http + fs vertical)
# ---------------------------------------------------------------------------

class TestAdapterContractMcp:
    def test_http_contract_has_get_verb_and_pitfalls(self):
        r = ainl_adapter_contract("http", detail_level="standard")
        assert r["ok"] is True
        assert r.get("schema_version")
        assert r.get("adapter") == "http"
        assert "verbs" in r
        assert "GET" in r["verbs"]
        assert "pitfalls" in r
        assert any("params" in p.lower() or "URL" in p for p in r["pitfalls"])
        ptrs = r.get("strict_valid_pointers") or []
        assert len(ptrs) == 1
        assert ptrs[0].get("path") == "examples/http_get_minimal.ainl"
        assert ptrs[0].get("in_ci_strict_valid") is True
        assert ptrs[0].get("resource_uri") == "ainl://strict-valid-examples"

    def test_fs_contract_has_write_verb(self):
        r = ainl_adapter_contract("fs", detail_level="standard")
        assert r["ok"] is True
        assert r.get("adapter") == "fs"
        assert "write" in r.get("verbs", {})
        ptrs = r.get("strict_valid_pointers") or []
        assert len(ptrs) == 1
        assert ptrs[0].get("path") is None
        assert ptrs[0].get("in_ci_strict_valid") is False
        assert "strict-valid" in (ptrs[0].get("note") or "").lower()


class TestContractAlignment:
    def test_synthetic_ir_unknown_http_verb_emits_warning(self):
        ir = {
            "labels": {
                "1": {
                    "nodes": [
                        {
                            "op": "R",
                            "data": {
                                "op": "R",
                                "adapter": "http.OPTIONS",
                                "src": "http",
                                "req_op": "OPTIONS",
                                "lineno": 9,
                            },
                        }
                    ]
                }
            }
        }
        w, items = _contract_alignment_hints_from_ir(ir)
        assert w and items
        assert any(it.get("adapter") == "http" for it in items)
        out: Dict[str, Any] = {"ok": True, "warnings": []}
        _merge_contract_alignment_into_output(out, ir, ok_graph=True)
        assert "contract_alignment" in out
        assert out["contract_alignment"]["mismatched_calls"]
        assert out["contract_validation_status"] == "syntax_valid_contract_mismatch"


# ---------------------------------------------------------------------------
# ainl-capabilities
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_capabilities_shape(self):
        caps = ainl_capabilities()
        assert "schema_version" in caps
        assert "runtime_version" in caps
        assert "policy_support" in caps
        assert caps["policy_support"] is True
        adapters = caps["adapters"]
        assert isinstance(adapters, dict)
        assert "core" in adapters
        assert "mcp_telemetry" in caps
        assert isinstance(caps["mcp_telemetry"], dict)

    def test_capabilities_adapter_has_privilege_tier(self):
        caps = ainl_capabilities()
        for name, info in caps["adapters"].items():
            assert "privilege_tier" in info, f"{name} missing privilege_tier"

    def test_capabilities_includes_mcp_resources_catalog(self):
        caps = ainl_capabilities()
        assert "mcp_resources" in caps
        rows = caps["mcp_resources"]
        assert isinstance(rows, list)
        uris = {r["uri"] for r in rows}
        assert "ainl://integrations-http-machine-payments" in uris
        assert "ainl://examples-http-machine-payment-flow" in uris
        assert "ainl://strict-authoring-cheatsheet" in uris
        for r in rows:
            assert set(r.keys()) == {"uri", "title", "summary"}

    def test_capabilities_strict_summary_shape(self):
        caps = ainl_capabilities()
        assert "strict_summary" in caps
        ss = caps["strict_summary"]
        assert ss.get("schema_version") == "1.0"
        assert "adapters" in ss
        assert "strict_valid_verbs" in ss
        assert caps["adapters"]["core"].get("strict_contract") is True

    def test_read_integration_doc_http_machine_payments_nonempty(self):
        text = _read_integration_doc("HTTP_MACHINE_PAYMENTS.md")
        assert len(text) > 500
        assert "payment_profile" in text or "402" in text


# ---------------------------------------------------------------------------
# ainl-security-report
# ---------------------------------------------------------------------------

class TestSecurityReport:
    def test_security_report_for_core_workflow(self):
        result = ainl_security_report(VALID_CODE)
        assert result["ok"] is True
        report = result["report"]
        assert "summary" in report
        assert "labels" in report
        tiers = report["summary"]["privilege_tiers"]
        assert "pure" in tiers

    def test_security_report_for_network_workflow(self):
        result = ainl_security_report(NETWORK_CODE)
        assert result["ok"] is True
        tiers = set(result["report"]["summary"]["privilege_tiers"])
        assert "network" in tiers

    def test_security_report_lenient_parsing(self):
        """Security report uses non-strict compilation, so only truly
        unparseable input would produce errors."""
        result = ainl_security_report(INVALID_CODE)
        assert result["ok"] is True
        assert "report" in result


# ---------------------------------------------------------------------------
# ainl-run
# ---------------------------------------------------------------------------

class TestRun:
    def test_authoring_workflow_validate_compile_run_smoke(self):
        r_bad = ainl_validate(INVALID_CODE, strict=True)
        assert r_bad["ok"] is False
        r_ok = ainl_validate(VALID_CODE, strict=True)
        assert r_ok["ok"] is True
        r_comp = ainl_compile(VALID_CODE, strict=True)
        assert r_comp["ok"] is True
        r_run = ainl_run(VALID_CODE, strict=True)
        assert r_run["ok"] is True
        assert "trace_id" in r_run

        before = ainl_capabilities()["mcp_telemetry"].get("run_after_validate_without_compile", 0)
        ainl_validate(VALID_CODE, strict=True)
        ainl_run(VALID_CODE, strict=True)
        after = ainl_capabilities()["mcp_telemetry"].get("run_after_validate_without_compile", 0)
        assert after >= before + 1

    def test_run_core_only_succeeds(self):
        result = ainl_run(VALID_CODE, strict=True)
        assert result["ok"] is True
        assert "trace_id" in result
        assert "out" in result
        assert "runtime_version" in result
        assert result.get("strict") is True
        assert "strict_mode_note" not in result

    def test_run_nonstrict_includes_mode_note(self):
        result = ainl_run(VALID_CODE, strict=False)
        assert result["ok"] is True
        assert result.get("strict") is False
        assert "strict_mode_note" in result

    def test_run_network_workflow_not_blocked_by_default_policy(self):
        """Default MCP grant matches runner: http is allowed at policy layer (may fail at runtime if adapter missing)."""
        result = ainl_run(NETWORK_CODE, strict=True)
        assert result.get("error") != "policy_violation"

    def test_run_invalid_code_returns_errors(self):
        result = ainl_run(INVALID_CODE)
        assert result["ok"] is False
        assert "errors" in result

    def test_run_missing_adapter_returns_retry_payload(self):
        result = ainl_run(FS_CODE, strict=True)
        assert result["ok"] is False
        assert "adapter_registration_error" in result
        reg = result["adapter_registration_error"]
        assert reg["adapter"] == "fs"
        assert reg["suggested_adapters"]["enable"] == ["fs"]
        assert reg["suggested_adapters"]["fs"]["root"] == "<absolute-workspace-or-output-root>"
        assert "Retry `ainl_run`" in reg["next_step"] or "Retry ainl_run" in reg["next_step"]
        assert reg["ainl_adapter_contract"]["args"]["adapter"] == "fs"
        assert "ainl://strict-authoring-cheatsheet" in reg["recommended_resources"]
        assert result.get("error_kind") == "adapter_registration"
        assert "repair_recipe" in result
        assert reg["recommended_next_tools"][0] == "ainl_capabilities"

    def test_run_preflight_fails_before_engine_when_http_and_fs_unregistered(self):
        """C1: multi-adapter IR returns a copyable payload without executing the graph."""
        result = ainl_run(HTTP_FS_CODE, strict=True)
        assert result["ok"] is False
        assert result.get("error_kind") == "adapter_registration"
        reg = result["adapter_registration_error"]
        assert set(reg["missing_mcp_configurable"]) == {"http", "fs"}
        assert reg["suggested_adapters"]["enable"] == ["fs", "http"]
        assert reg["suggested_adapters"]["http"]["allow_hosts"] == ["example.com"]

    def test_run_invalid_includes_compile_feedback(self):
        result = ainl_run(INVALID_CODE)
        assert result["ok"] is False
        assert "diagnostics" in result
        assert "primary_diagnostic" in result
        assert "agent_repair_steps" in result
        assert "trace_id" in result
        assert "repair_recipe" in result
        assert "recommended_next_tools" in result

    def test_run_caller_can_add_restrictions(self):
        result = ainl_run(
            VALID_CODE,
            policy={"forbidden_adapters": ["core"]},
        )
        assert result["ok"] is False
        assert result.get("error") == "policy_violation"

    def test_run_caller_cannot_widen_defaults(self, monkeypatch: pytest.MonkeyPatch):
        import scripts.ainl_mcp_server as mcp_mod
        from tooling.capability_grant import merge_grants

        tight = merge_grants(
            mcp_mod._MCP_SERVER_GRANT,
            {"forbidden_privilege_tiers": ["network"]},
        )
        monkeypatch.setattr(mcp_mod, "_MCP_SERVER_GRANT", tight)
        result = mcp_mod.ainl_run(
            NETWORK_CODE,
            policy={"forbidden_privilege_tiers": []},
        )
        assert result["ok"] is False
        assert result.get("error") == "policy_violation"


# ---------------------------------------------------------------------------
# ainl_fitness_report / ainl_ir_diff
# ---------------------------------------------------------------------------

class TestResearchTools:
    def test_fitness_report(self, tmp_path: Path):
        f = tmp_path / "ok.ainl"
        f.write_text(VALID_CODE, encoding="utf-8")
        result = ainl_fitness_report(str(f), runs=2, strict=True)
        assert "metrics" in result
        assert result["metrics"]["latency_ms"]["avg"] >= 0
        assert "adapter_calls" in result["metrics"]
        assert result["metrics"]["memory_deltas"]["tracked"] is True
        assert "operation_histogram" in result["metrics"]
        assert "fitness_score" in result["metrics"]
        assert 0.0 <= result["metrics"]["fitness_score"] <= 1.0
        assert "fitness_components" in result["metrics"]

    def test_ir_diff(self, tmp_path: Path):
        f1 = tmp_path / "a.ainl"
        f2 = tmp_path / "b.ainl"
        f1.write_text(VALID_CODE, encoding="utf-8")
        f2.write_text("S app api /api\nL1:\nR core.ADD 2 4 ->sum\nJ sum", encoding="utf-8")
        result = ainl_ir_diff(str(f1), str(f2), strict=True)
        assert result["ok"] is True
        assert "diff" in result
        assert isinstance(result["diff"]["changed_nodes"], list)

    def test_ptc_signature_check(self):
        code = "L1: R core.ADD 1 2 ->x # signature: {x :int}\n"
        result = ainl_ptc_signature_check(code, strict=True)
        assert result["ok"] is True
        assert result["count"] >= 1

    def test_trace_export(self, tmp_path: Path):
        src = tmp_path / "trace.jsonl"
        dst = tmp_path / "ptc.jsonl"
        src.write_text(
            json.dumps(
                {
                    "step_id": 1,
                    "label": "1",
                    "operation": "R",
                    "inputs": {"_private": "x", "node_id": "n1"},
                    "output": {"ok": True},
                    "outcome": "success",
                    "timestamp": "2026-03-26T00:00:00.000Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        out = ainl_trace_export(str(src), str(dst))
        assert out["ok"] is True
        assert dst.exists()

    def test_ptc_run_mock(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AINL_PTC_RUNNER_MOCK", "1")
        result = ainl_ptc_run("(+ 1 2)", signature="{value :string}", max_attempts=2)
        assert result["ok"] is True
        assert "result" in result

    def test_fitness_score_zero_when_reliability_zero(self, tmp_path: Path):
        # Uses db adapter so safe-profile (core-only) fitness runs reliably fail.
        failing = tmp_path / "failing.ainl"
        failing.write_text(
            "S app api /api\nL1:\nR db.F User * ->rows\nJ rows\n",
            encoding="utf-8",
        )
        result = ainl_fitness_report(str(failing), runs=3, strict=True)
        assert result["metrics"]["reliability_score"] == 0.0
        assert result["metrics"]["fitness_score"] == 0.0


# ---------------------------------------------------------------------------
# MCP resources
# ---------------------------------------------------------------------------

class TestResources:
    def test_adapter_manifest_resource(self):
        data = _load_json("adapter_manifest.json")
        assert "adapters" in data
        assert "core" in data["adapters"]

    def test_security_profiles_resource(self):
        data = _load_json("security_profiles.json")
        assert "profiles" in data
        assert "local_minimal" in data["profiles"]

    def test_strict_valid_examples_json_lists_profile_paths(self):
        payload = json.loads(_strict_valid_examples_json())
        assert payload.get("profile") == "strict-valid"
        assert payload.get("count", 0) >= 1
        assert "examples/compact/hello_compact.ainl" in payload.get("paths", [])

    def test_adapter_contracts_bundle_includes_http(self):
        bundle = json.loads(_adapter_contracts_bundle_json())
        assert bundle["http"]["ok"] is True
        assert "GET" in bundle["http"]["verbs"]
        assert bundle["http"].get("strict_valid_pointers")


# ---------------------------------------------------------------------------
# Policy / limits merge helpers
# ---------------------------------------------------------------------------

class TestMergeHelpers:
    def test_merge_policy_unions_restrictions(self):
        merged = _merge_policy({"forbidden_adapters": ["http"]})
        assert "http" in merged["forbidden_adapters"]
        assert not merged.get("forbidden_privilege_tiers")

    def test_merge_policy_none_preserves_defaults(self):
        merged = _merge_policy(None)
        assert not merged.get("forbidden_privilege_tiers")

    def test_merge_limits_takes_minimum(self):
        merged = _merge_limits({"max_steps": 100})
        assert merged["max_steps"] == 100

    def test_merge_limits_cannot_widen(self):
        # Caller tries to pass a value larger than the server default (500000);
        # _merge_limits takes the minimum, so the server ceiling wins.
        from scripts.ainl_mcp_server import _MCP_DEFAULT_LIMITS
        server_default = _MCP_DEFAULT_LIMITS["max_steps"]
        over_ceiling = server_default + 1_000_000
        merged = _merge_limits({"max_steps": over_ceiling})
        assert merged["max_steps"] == server_default


# ---------------------------------------------------------------------------
# Wizard State Machine
# ---------------------------------------------------------------------------


class TestWizardStateMachine:
    """Tests for the deterministic wizard state machine."""

    def test_wizard_state_returned_from_get_started(self):
        result = ainl_get_started(goal="Build a scraper that saves CSV")
        assert "wizard_state_json" in result
        assert "session_id" in result
        assert result["wizard_stage"] in ("core_starter", "capability_discovery", "contract_resolution", "incremental_authoring")

    def test_wizard_state_resumption_preserves_session(self):
        result1 = ainl_get_started(goal="Build a scraper that saves CSV")
        wizard_state = result1.get("wizard_state_json")
        result2 = ainl_get_started(goal="Build a scraper that saves CSV", wizard_state_json=wizard_state)
        assert result1["session_id"] == result2["session_id"]

    def test_core_workflow_can_author_immediately(self):
        result = ainl_get_started(goal="Run hello.ainl")
        assert result["wizard_state"]["can_author_now"] is True
        assert result["wizard_stage"] == "core_starter"

    def test_adapter_workflow_blocks_until_contracts(self):
        result = ainl_get_started(goal="Build a scraper that saves CSV")
        assert result["wizard_state"]["can_author_now"] is False
        assert result["wizard_stage"] == "capability_discovery"
        assert "capabilities_inspected" in result["wizard_state"]["blocking_checkpoints"]

    def test_next_wizard_action_guides_progression(self):
        result = ainl_get_started(goal="Build a scraper that saves CSV")
        next_action = result.get("next_wizard_action")
        assert next_action is not None
        assert next_action["tool"] == "ainl_capabilities"


class TestLeadGenWorkflow:
    """Tests for lead-gen style workflows with strict validation requirements."""

    def test_strict_validation_required_for_adapter_workflows(self):
        """Adapter workflow must pass strict validation, not just loose."""
        code = '''
scraper:
  in: url output_path
  page = http.GET url
  rows = core.GET page "body"
  written = fs.write output_path rows
  out written
'''
        loose_result = ainl_validate(code=code, strict=False)
        strict_result = ainl_validate(code=code, strict=True)
        assert loose_result["ok"] is True
        assert strict_result["ok"] is True
        assert strict_result.get("strict") is True

    def test_run_proof_requires_ok_true(self):
        """ainl_run ok:false should not satisfy proof gate."""
        code = '''
hello:
  out "test"
'''
        validate_result = ainl_validate(code=code, strict=True)
        assert validate_result["ok"] is True
        compile_result = ainl_compile(code=code, strict=True)
        assert compile_result.get("ok", True) is True

    def test_contract_validation_status_returned(self):
        """Validate should return contract_validation_status for adapter workflows."""
        code = '''
fetcher:
  in: url
  res = http.GET url
  out res
'''
        result = ainl_validate(code=code, strict=True)
        assert "contract_validation_status" in result
        assert result["contract_validation_status"] in (
            "syntax_valid_contract_verified",
            "syntax_valid_contract_unknown",
            "syntax_valid_contract_mismatch",
        )


class TestAdapterRegistrationE2E:
    """Tests for adapter registration and runtime readiness."""

    def test_compile_returns_required_adapters(self):
        """ainl_compile should return required_adapters for configuring ainl_run."""
        code = '''
fetcher:
  in: url output_path
  page = http.GET url
  fs.write output_path page
  out page
'''
        result = ainl_compile(code=code)
        assert "required_adapters" in result
        required = result["required_adapters"]
        assert "http" in required
        assert "fs" in required

    def test_runtime_readiness_hints_for_adapters(self):
        """Compile should include runtime_readiness hints."""
        code = '''
writer:
  in: path content
  fs.write path content
  out "done"
'''
        result = ainl_compile(code=code)
        assert "runtime_readiness" in result
        readiness = result["runtime_readiness"]
        assert "fs" in readiness.get("required_adapters", [])
        assert readiness.get("ready") is False
        assert "suggested_adapters" in readiness

    def test_suggested_adapters_payload_complete(self):
        """Compile should suggest adapters payload structure."""
        code = '''
combined:
  in: url output_path
  page = http.GET url
  fs.write output_path page
  out page
'''
        result = ainl_compile(code=code)
        # Runtime readiness includes adapter configuration hints
        assert result.get("required_adapters")


class TestStrictOutputDiagnostics:
    """Tests for strict mode output/JSON diagnostics."""

    def test_inline_json_literal_detected(self):
        """Inline JSON in out/Set should be flagged in strict mode."""
        code = '''
builder:
  in: name
  out {name: name, status: "ok"}
'''
        result = ainl_validate(code=code, strict=True)
        assert result["ok"] is False
        errors = result.get("errors") or []
        assert any("inline JSON" in str(e).lower() or "object literal" in str(e).lower() for e in errors)

    def test_core_stringify_for_structured_output(self):
        """core.STRINGIFY should be suggested for structured output."""
        code = '''
builder:
  in: data
  json_text = core.STRINGIFY data
  out json_text
'''
        result = ainl_validate(code=code, strict=True)
        assert result["ok"] is True
