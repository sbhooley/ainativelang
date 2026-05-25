"""Semantic contract validation for AINL adapter calls.

Validates IR adapter calls against ADAPTER_CONTRACTS to catch:
- Unknown adapter verbs
- Arity mismatches (too few / too many arguments)
- Known pitfalls (e.g. inline dict literals on R lines)

Called from the validate/compile pipeline when --strict-contracts is active.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from tooling.ainl_get_started import ADAPTER_CONTRACTS, check_verb_arity


class ContractDiagnostic:
    """A single diagnostic from contract validation."""

    __slots__ = ("adapter", "verb", "label", "severity", "message", "suggested_fix")

    def __init__(
        self,
        adapter: str,
        verb: str,
        label: str,
        severity: str,
        message: str,
        suggested_fix: Optional[str] = None,
    ) -> None:
        self.adapter = adapter
        self.verb = verb
        self.label = label
        self.severity = severity
        self.message = message
        self.suggested_fix = suggested_fix

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "adapter": self.adapter,
            "verb": self.verb,
            "label": self.label,
            "severity": self.severity,
            "message": self.message,
        }
        if self.suggested_fix:
            d["suggested_fix"] = self.suggested_fix
        return d

    def __repr__(self) -> str:
        return f"ContractDiagnostic({self.severity}: {self.message})"


def _extract_adapter_verb(step: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Extract adapter name and verb from an IR step dict."""
    adapter_raw = step.get("adapter") or ""
    if "." in adapter_raw:
        parts = adapter_raw.split(".", 1)
        return parts[0], parts[1]
    target = step.get("target") or ""
    if adapter_raw and target:
        return adapter_raw, target
    return adapter_raw or None, None


def _count_step_args(step: Dict[str, Any]) -> int:
    """Count the number of arguments in an IR step."""
    args = step.get("args")
    if isinstance(args, list):
        return len(args)
    raw = step.get("raw_args") or step.get("arguments") or ""
    if isinstance(raw, str) and raw.strip():
        return len(raw.strip().split())
    return 0


def validate_ir_contracts(
    ir: Dict[str, Any],
    strict: bool = False,
) -> List[ContractDiagnostic]:
    """Validate all adapter calls in an IR dict against ADAPTER_CONTRACTS.

    Parameters
    ----------
    ir : dict
        Compiled IR (as returned by the compiler).
    strict : bool
        If True, unknown verbs on known adapters become errors (not warnings).

    Returns
    -------
    list[ContractDiagnostic]
        Diagnostics found. Empty list means all checks passed.
    """
    diagnostics: List[ContractDiagnostic] = []
    labels = ir.get("labels") or {}

    for label_name, label_data in labels.items():
        steps = label_data if isinstance(label_data, list) else (label_data.get("steps") or [])
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = (step.get("op") or step.get("opcode") or "").upper()
            if op not in ("R", "REQUEST", "CALL"):
                continue

            adapter, verb = _extract_adapter_verb(step)
            if not adapter:
                continue

            contract = ADAPTER_CONTRACTS.get(adapter)
            if not contract:
                continue

            known_verbs = contract.get("verbs") or {}

            if verb and known_verbs:
                verb_match = known_verbs.get(verb) or known_verbs.get(verb.upper()) or known_verbs.get(verb.lower())
                if not verb_match:
                    sev = "error" if strict else "warning"
                    available = ", ".join(sorted(known_verbs.keys()))
                    diagnostics.append(ContractDiagnostic(
                        adapter=adapter,
                        verb=verb or "",
                        label=label_name,
                        severity=sev,
                        message=f"Unknown verb '{verb}' on adapter '{adapter}'. Known verbs: {available}",
                        suggested_fix=f"Use one of: {available}",
                    ))
                    continue

            if verb:
                arg_count = _count_step_args(step)
                arity_warning = check_verb_arity(adapter, verb, arg_count)
                if arity_warning:
                    diagnostics.append(ContractDiagnostic(
                        adapter=adapter,
                        verb=verb,
                        label=label_name,
                        severity="error" if strict else "warning",
                        message=arity_warning,
                    ))

    return diagnostics


def format_diagnostics(diagnostics: List[ContractDiagnostic]) -> str:
    """Format diagnostics as a human-readable report."""
    if not diagnostics:
        return "contract_validation_status: verified (0 issues)\n"
    lines = [f"contract_validation: {len(diagnostics)} issue(s)\n"]
    for d in diagnostics:
        prefix = "ERROR" if d.severity == "error" else "WARN"
        lines.append(f"  [{prefix}] {d.label}: {d.message}")
        if d.suggested_fix:
            lines.append(f"         fix: {d.suggested_fix}")
    return "\n".join(lines) + "\n"
