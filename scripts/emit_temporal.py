#!/usr/bin/env python3
"""
Emit Temporal ``activities`` + ``workflow`` modules that delegate to AINL via
:func:`runtime.wrappers.temporal_wrapper.execute_ainl_activity`.

Used from ``scripts/validate_ainl.py --emit temporal``.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def resolve_temporal_output_dir_and_base(output: Optional[str], stem: str) -> Tuple[Path, str]:
    """Return (output_dir, base_name) for ``{base}_activities.py`` and ``{base}_workflow.py``."""
    cwd = Path.cwd()
    if not output:
        return cwd, stem
    p = Path(output).expanduser()
    if p.suffix.lower() == ".py":
        parent = p.parent
        return (parent if str(parent) else cwd), p.stem
    if p.exists() and p.is_dir():
        return p, stem
    # Prefix path (e.g. out/monitoring): write under parent with basename as stem for files
    if not p.exists() and p.suffix == "" and p.name:
        return (p.parent if str(p.parent) else cwd), p.name
    return cwd, stem


def _safe_module_base(stem: str) -> str:
    """Use a valid Python module name fragment for imports."""
    s = re.sub(r"[^0-9a-zA-Z_]", "_", stem)
    if s and s[0].isdigit():
        s = "_" + s
    return s or "ainl_temporal"


def emit_temporal_pair(ir: Dict[str, Any], *, output_dir: Path, source_stem: str) -> Tuple[Path, Path]:
    """Write activities + workflow files; return (activities_path, workflow_path)."""
    base = _safe_module_base(source_stem)
    act_path = output_dir / f"{base}_activities.py"
    wf_path = output_dir / f"{base}_workflow.py"
    act_path.write_text(_emit_activities_source(ir, source_stem=source_stem, module_base=base), encoding="utf-8")
    wf_path.write_text(_emit_workflow_source(source_stem=source_stem, module_base=base), encoding="utf-8")
    return act_path, wf_path


def _emit_activities_source(ir: Dict[str, Any], *, source_stem: str, module_base: str) -> str:
    blob = base64.standard_b64encode(json.dumps(ir, ensure_ascii=False).encode("utf-8")).decode("ascii")
    lines = [
        '"""',
        f"AINL Temporal activities (emitted from {source_stem}).",
        "",
        "Requires temporalio on the worker for @activity.defn; without it, call",
        "``run_ainl_core_activity_impl`` directly for local tests.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import base64",
        "import json",
        "import sys",
        "from pathlib import Path",
        "from typing import Any, Dict",
        "",
        'try:',
        "    from temporalio import activity",
        "except ImportError:  # pragma: no cover - optional until worker install",
        "    activity = None  # type: ignore",
        "",
        f"_IR_B64 = {blob!r}",
        f"_SOURCE_STEM = {source_stem!r}",
        "",
        "",
        "def _repo_root() -> Path:",
        "    _here = Path(__file__).resolve().parent",
        "    for start in (_here, Path.cwd().resolve()):",
        "        root = start",
        "        for _ in range(14):",
        '            if (root / "runtime" / "engine.py").is_file() and (root / "adapters").is_dir():',
        "                return root",
        "            if root.parent == root:",
        "                break",
        "            root = root.parent",
        "    return _here",
        "",
        "",
        "_ROOT = _repo_root()",
        "if str(_ROOT) not in sys.path:",
        "    sys.path.insert(0, str(_ROOT))",
        "",
        "from runtime.wrappers.temporal_wrapper import execute_ainl_activity  # noqa: E402",
        "",
        "_IR: Dict[str, Any] | None = None",
        "",
        "",
        "def _ir() -> Dict[str, Any]:",
        "    global _IR",
        "    if _IR is None:",
        "        _IR = json.loads(base64.standard_b64decode(_IR_B64))",
        "    return _IR",
        "",
        "",
        "def run_ainl_core_activity_impl(input_data: Dict[str, Any]) -> Dict[str, Any]:",
        '    """',
        "    Temporal payload: use keys matching AINL frame vars (e.g. metric_value).",
        "    Optional keys: ``_label`` (str) overrides entry label; ``_strict`` (bool) for future use.",
        '    """',
        "    data = dict(input_data or {})",
        "    lid = data.pop(\"_label\", None)",
        "    return execute_ainl_activity(_ir(), data, label=lid, strict=True)",
        "",
        "",
        "if activity is not None:",
        "    run_ainl_core_activity = activity.defn(run_ainl_core_activity_impl)",
        "else:",
        "    run_ainl_core_activity = run_ainl_core_activity_impl",
        "",
    ]
    return "\n".join(lines)


def _emit_workflow_source(*, source_stem: str, module_base: str) -> str:
    act_mod = f"{module_base}_activities"
    lines = [
        '"""',
        f"Temporal workflow for emitted AINL graph ({source_stem}).",
        "",
        "Requires: pip install temporalio",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from datetime import timedelta",
        "",
        'try:',
        "    from temporalio import workflow",
        "    from temporalio.common import RetryPolicy",
        "except ImportError as e:  # pragma: no cover",
        '    raise RuntimeError("Install temporalio: pip install temporalio") from e',
        "",
        "",
        "# Import activities from the sibling module (same directory on worker PYTHONPATH).",
        "with workflow.unsafe.imports_passed_through():",
        f"    import {act_mod} as _ainl_activities",
        "",
        "",
        "@workflow.defn",
        f"class {_workflow_class_name(module_base)}:",
        "    @workflow.run",
        "    async def run(self, input_data: dict) -> dict:",
        '        """',
        "        Customize: add signals/queries, child workflows, or multiple execute_activity",
        "        steps. Adjust start_to_close_timeout and RetryPolicy (maximum_attempts,",
        "        backoff_coefficient, non_retryable_error_types) per your SLOs.",
        '        """',
        "        return await workflow.execute_activity(",
        "            _ainl_activities.run_ainl_core_activity,",
        "            input_data,",
        "            start_to_close_timeout=timedelta(minutes=5),",
        "            retry_policy=RetryPolicy(maximum_attempts=3),",
        "        )",
        "",
    ]
    return "\n".join(lines)


def _workflow_class_name(module_base: str) -> str:
    parts = [p for p in module_base.split("_") if p]
    return "Ainl" + "".join(p.capitalize() for p in parts) + "Workflow"
