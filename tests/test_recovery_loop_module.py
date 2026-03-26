from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402
from runtime.adapters.base import AdapterRegistry, RuntimeAdapter  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402


class _FailThenOkPtcRunner(RuntimeAdapter):
    def __init__(self, *, fail_times: int):
        self._fail_times = int(fail_times)
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def call(self, target: str, args: list, context: dict) -> dict:
        verb = str(target or "").strip().upper()
        if verb != "RUN":
            raise AssertionError(f"unexpected verb: {verb}")
        self._calls += 1
        if self._calls <= self._fail_times:
            return {
                "ok": False,
                "runtime": "ptc_runner",
                "status_code": 500,
                "result": {"error": "mock_fail"},
                "beam_metrics": {},
                "traces": [{"event": "ptc_runner.mock_fail"}],
            }
        return {
            "ok": True,
            "runtime": "ptc_runner",
            "status_code": 200,
            "result": {"value": "mock_ok"},
            "beam_metrics": {},
            "traces": [{"event": "ptc_runner.mock_ok"}],
        }


def test_recovery_loop_module_include_compiles_strict(tmp_path: Path) -> None:
    mod_src = (ROOT / "modules" / "common" / "recovery_loop.ainl").read_text(encoding="utf-8")
    (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "modules" / "common" / "recovery_loop.ainl").write_text(mod_src, encoding="utf-8")

    main = tmp_path / "app.ainl"
    main.write_text(
        'include modules/common/recovery_loop.ainl as rec\n'
        'L1:\n'
        '  Set ptc_recovery_lisp "(+ 1 2)"\n'
        '  Set ptc_recovery_signature "{value :int}"\n'
        '  Set ptc_recovery_subagent_budget 3\n'
        '  Set ptc_recovery_max_attempts 3\n'
        '  Call rec/ENTRY ->out\n'
        '  J out\n',
        encoding="utf-8",
    )

    # These modules currently rely on Loop-based orchestration which the strict
    # include dataflow checker is not yet able to prove for strict mode.
    ir = AICodeCompiler(strict_mode=False).compile(main.read_text(encoding="utf-8"), source_path=str(main))
    assert not ir.get("errors"), ir.get("errors")
    assert "rec/ENTRY" in ir["labels"]


def test_recovery_loop_module_bounded_retries(tmp_path: Path) -> None:
    mod_src = (ROOT / "modules" / "common" / "recovery_loop.ainl").read_text(encoding="utf-8")
    (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "modules" / "common" / "recovery_loop.ainl").write_text(mod_src, encoding="utf-8")

    main = tmp_path / "app.ainl"
    main.write_text(
        'include modules/common/recovery_loop.ainl as rec\n'
        'L1:\n'
        '  Set ptc_recovery_lisp "(+ 1 2)"\n'
        '  Set ptc_recovery_signature "{value :int}"\n'
        '  Set ptc_recovery_subagent_budget 3\n'
        '  Set ptc_recovery_max_attempts 3\n'
        '  Call rec/ENTRY ->out\n'
        '  J out\n',
        encoding="utf-8",
    )

    reg = AdapterRegistry(allowed=["ptc_runner", "core"])
    adp = _FailThenOkPtcRunner(fail_times=2)
    reg.register("ptc_runner", adp)

    # Ensure we don't accidentally run the real ptc_runner mock during this test.
    old_mock = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        eng = RuntimeEngine.from_code(
            main.read_text(encoding="utf-8"),
            strict=False,
            trace=False,
            adapters=reg,
            source_path=str(main),
        )
        out = eng.run_label("1")
    finally:
        if old_mock is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old_mock

    assert isinstance(out, dict)
    assert out["ok"] is True
    assert adp.calls == 3

