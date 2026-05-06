"""GraphPatch dispatch + boot-time reinstall logic.

Extracted from ``runtime/engine.py`` to reduce the size of
``RuntimeEngine`` and isolate the GraphPatch machinery in its own
module. The functions defined here are attached to ``RuntimeEngine``
at the bottom of ``runtime/engine.py`` via ``setattr``, so they
continue to behave as instance methods on existing call sites
(``self._memory_patch_dispatch(...)``, ``self._reinstall_patches()``).

The two cuts here are deliberate:

- ``_memory_patch_dispatch`` -- runtime-time GraphPatch entry from a
  ``MemoryPatch`` node: validates dataflow, normalizes the patch, and
  installs the patched label into the engine's label table.
- ``_reinstall_patches`` -- boot-time replay of all active patches from
  the GraphStore PatchRegistry.

Late binding (rather than a Mixin) avoids a module-import cycle:
``runtime/engine.py`` defines the helpers/exceptions/logger this
module imports; this module is imported only at the bottom of
``runtime/engine.py``, after those names are already in scope.

Audit ref: sbhooley/ainativelang#39 P1-7 (memory/graph dispatch
extraction).
"""
from __future__ import annotations

from typing import Any, Dict, List

from runtime.engine import OverwriteGuardError, _LOG, _norm_lid


def _memory_patch_dispatch(
    self,
    *,
    memory_node_id: str,
    label_name: str,
    frame: Dict[str, Any],
    lid: str,
    idx: int,
    stack: List[str],
) -> Dict[str, Any]:
    """
    GraphPatch runtime dispatch:
    1. Call bridge to get pattern steps from ainl-memory
    2. Validate dataflow (reads vs. current frame)
    3. Normalize to full IR label body
    4. Install into self.labels with __patched__ marker
    """
    resolved_label = _norm_lid(label_name)
    if not resolved_label:
        return {"ok": False, "error": "empty patch label_name"}

    existing_body = self.labels.get(resolved_label)
    if existing_body is not None and not existing_body.get("__patched__"):
        raise OverwriteGuardError(
            f"GraphPatch cannot overwrite compiled label {resolved_label!r}"
        )

    call_ctx = dict(frame)
    call_ctx["_runtime_async"] = self.runtime_async
    call_ctx["_observability"] = self.observability
    call_ctx["_adapter_registry"] = self.adapters

    # Query ainl-memory for the procedural node
    bridge_result = self.adapters.call(
        "ainl_graph_memory",
        "graph_patch",
        [memory_node_id, label_name],
        call_ctx,
    )

    if not bridge_result or not bridge_result.get("ok"):
        error_msg = bridge_result.get("error", "Unknown error") if bridge_result else "No response from bridge"
        return {"ok": False, "error": error_msg}

    steps = bridge_result.get("steps", [])
    if not steps:
        return {"ok": False, "error": "No steps returned from memory node"}

    # Validate dataflow
    validation_error = self._runtime_validate_patch_dataflow(steps, label_name, frame)
    if validation_error:
        return {"ok": False, "error": validation_error}

    # Normalize patch
    normalized = self._runtime_normalize_patch(steps, label_name)

    patch_nid = str(bridge_result.get("node_id") or "")
    patch_ver = int(bridge_result.get("patch_version") or 1)
    declared_reads = list(normalized.get("__declared_reads__") or [])
    merged: Dict[str, Any] = {
        **normalized,
        "__patch_node_id__": patch_nid,
        "__patch_version__": patch_ver,
        "__fitness__": 0.5,
    }

    # Install patch
    self.labels[resolved_label] = merged

    try:
        bridge = self.adapters.get("ainl_graph_memory")
        if bridge is not None and patch_nid:
            bridge._store.finalize_patch(patch_nid, declared_reads, persist=True)
    except Exception:
        pass

    _LOG.info(
        f"GraphPatch: installed label '{resolved_label}' from memory node '{memory_node_id}' "
        f"with {len(steps)} steps, {len(declared_reads)} declared reads"
    )

    return {
        "ok": True,
        "label": resolved_label,
        "steps": len(steps),
        "declared_reads": declared_reads,
    }


def _reinstall_patches(self) -> None:
    """
    Re-install all active PatchRegistry entries from the GraphStore
    into self.labels on engine boot. Skips labels that already exist
    in the compiled IR (overwrite guard: __patched__ only).
    Logs a warning for each skipped collision.
    """
    try:
        bridge = self.adapters.get("ainl_graph_memory")
        if bridge is None:
            return
        agent_id = str(
            (self.ir.get("services") or {})
            .get("core", {})
            .get("agent_id", "")
            or "armaraos"
        )
        records = bridge._store.get_patch_registry(agent_id=agent_id)
        for rec in records:
            if rec.label_name in self.labels:
                existing = self.labels[rec.label_name]
                if not existing.get("__patched__"):
                    _LOG.warning(
                        "GraphPatch boot: skipping label %r — "
                        "already exists as compiled label",
                        rec.label_name,
                    )
                    continue
            # Retrieve steps from the source pattern node
            source_node = bridge._store.get_node(rec.source_pattern_node_id)
            if source_node is None:
                _LOG.warning(
                    "GraphPatch boot: source node %r missing for label %r",
                    rec.source_pattern_node_id, rec.label_name,
                )
                continue
            steps = (source_node.payload or {}).get("steps") or []
            if not steps:
                continue
            normalized = self._runtime_normalize_patch(steps, rec.label_name)
            self.labels[rec.label_name] = {
                "__patched__": True,
                "__declared_reads__": set(rec.declared_reads),
                "__patch_node_id__": rec.node_id,
                "__patch_version__": rec.patch_version,
                "__fitness__": rec.fitness,
                **normalized,
            }
        if records:
            _LOG.info(f"GraphPatch boot: reinstalled {len(records)} patch(es)")
    except Exception as e:
        _LOG.warning("GraphPatch boot reinstall failed: %s", e)
