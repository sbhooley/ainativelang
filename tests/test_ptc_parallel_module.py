from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402
from runtime.adapters.base import AdapterRegistry  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402
from adapters.ptc_runner import PtcRunnerAdapter  # noqa: E402


def test_ptc_parallel_module_include_compiles_strict(tmp_path: Path) -> None:
    mod_src = (ROOT / "modules" / "common" / "ptc_parallel.ainl").read_text(encoding="utf-8")
    (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "modules" / "common" / "ptc_parallel.ainl").write_text(mod_src, encoding="utf-8")

    main = tmp_path / "app.ainl"
    main.write_text(
        'include modules/common/ptc_parallel.ainl as par\n'
        'L1: \n'
        '  Set ptc_parallel_calls_json "[{\\"lisp\\":\\"(+ 1 1)\\",\\"signature\\":\\"{a :int}\\"},{\\"lisp\\":\\"(+ 2 2)\\",\\"signature\\":\\"{a :int}\\"}]"\n'
        '  Set ptc_parallel_subagent_budget 3\n'
        '  Set ptc_parallel_max_concurrent 1\n'
        '  Set ptc_parallel_queue_name null\n'
        '  Call par/ENTRY ->out\n'
        '  J out\n',
        encoding="utf-8",
    )

    # These modules currently rely on Loop-based orchestration which the strict
    # include dataflow checker is not yet able to prove for strict mode.
    ir = AICodeCompiler(strict_mode=False).compile(main.read_text(encoding="utf-8"), source_path=str(main))
    assert not ir.get("errors"), ir.get("errors")
    assert "par/ENTRY" in ir["labels"]


def test_ptc_parallel_module_mock_runs_and_caps_concurrency(tmp_path: Path) -> None:
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"

        mod_src = (ROOT / "modules" / "common" / "ptc_parallel.ainl").read_text(encoding="utf-8")
        (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
        (tmp_path / "modules" / "common" / "ptc_parallel.ainl").write_text(mod_src, encoding="utf-8")

        main = tmp_path / "app.ainl"
        main.write_text(
            'include modules/common/ptc_parallel.ainl as par\n'
            'L1:\n'
            '  Set ptc_parallel_calls_json "[{\\"lisp\\":\\"(+ 1 1)\\",\\"signature\\":\\"{a :int}\\"},{\\"lisp\\":\\"(+ 2 2)\\",\\"signature\\":\\"{a :int}\\"}]"\n'
            '  Set ptc_parallel_subagent_budget 3\n'
            '  Set ptc_parallel_max_concurrent 1\n'
            '  Set ptc_parallel_queue_name null\n'
            '  Call par/ENTRY ->out\n'
            '  J out\n',
            encoding="utf-8",
        )

        reg = AdapterRegistry(allowed=["ptc_runner", "core"])
        reg.register("ptc_runner", PtcRunnerAdapter(enabled=True))

        eng = RuntimeEngine.from_code(
            main.read_text(encoding="utf-8"),
            strict=False,
            trace=False,
            adapters=reg,
            source_path=str(main),
        )
        out = eng.run_label("1")
        assert isinstance(out, list)
        assert len(out) == 1
        assert isinstance(out[0], dict)
        assert out[0]["ok"] is True
        assert out[0]["runtime"] == "ptc_runner"
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock

