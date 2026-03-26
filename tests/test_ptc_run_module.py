from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402
from runtime.adapters.base import AdapterRegistry  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402
from adapters.ptc_runner import PtcRunnerAdapter  # noqa: E402


def test_ptc_run_module_include_compiles_non_strict(tmp_path: Path) -> None:
    mod_src = (ROOT / "modules" / "common" / "ptc_run.ainl").read_text(encoding="utf-8")
    (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "modules" / "common" / "ptc_run.ainl").write_text(mod_src, encoding="utf-8")

    main = tmp_path / "app.ainl"
    main.write_text(
        'include modules/common/ptc_run.ainl as ptcrun\n'
        'L1:\n'
        '  Set ptc_run_lisp "(+ 1 2)"\n'
        '  Set ptc_run_signature "{total :int}"\n'
        '  Set ptc_run_subagent_budget 3\n'
        '  Call ptcrun/ENTRY ->out\n'
        '  J out\n',
        encoding="utf-8",
    )

    ir = AICodeCompiler(strict_mode=False).compile(main.read_text(encoding="utf-8"), source_path=str(main))
    assert not ir.get("errors"), ir.get("errors")
    assert "ptcrun/ENTRY" in ir["labels"]


@pytest.mark.parametrize("have_signature", [True, False])
@pytest.mark.parametrize("have_budget", [True, False])
def test_ptc_run_module_mock_runs_with_optionals(tmp_path: Path, have_signature: bool, have_budget: bool) -> None:
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"

        mod_src = (ROOT / "modules" / "common" / "ptc_run.ainl").read_text(encoding="utf-8")
        (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
        (tmp_path / "modules" / "common" / "ptc_run.ainl").write_text(mod_src, encoding="utf-8")

        main = tmp_path / "app.ainl"
        lines = [
            'include modules/common/ptc_run.ainl as ptcrun',
            "L1:",
            '  Set ptc_run_lisp "(+ 1 2)"',
        ]
        if have_signature:
            lines.append('  Set ptc_run_signature "{total :int}"')
        if have_budget:
            lines.append("  Set ptc_run_subagent_budget 3")
        lines.append("  Call ptcrun/ENTRY ->out")
        lines.append("  J out")
        main.write_text("\n".join(lines) + "\n", encoding="utf-8")

        reg = AdapterRegistry(allowed=["core", "ptc_runner"])
        reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))

        eng = RuntimeEngine.from_code(
            main.read_text(encoding="utf-8"),
            strict=False,
            trace=False,
            adapters=reg,
            source_path=str(main),
        )
        out = eng.run_label("1")
        assert isinstance(out, dict)
        assert out["ok"] is True
        assert out["runtime"] == "ptc_runner"
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock

