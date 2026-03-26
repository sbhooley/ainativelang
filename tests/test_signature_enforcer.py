import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.signature_enforcer import (
    collect_signature_annotations,
    signature_diagnostics,
    validate_result_against_signature,
    run_with_signature_retry,
)
from adapters.ptc_runner import PtcRunnerAdapter


def test_collect_signature_annotations():
    src = 'L1: R ptc_runner run "(+ 1 2)" "{total :float}" 5 ->out # signature: {total :float}\n'
    ann = collect_signature_annotations(src)
    assert 1 in ann
    assert "total" in ann[1]


def test_signature_diagnostics_malformed():
    src = 'L1: R core.ADD 1 2 ->x # signature:\n'
    diags = signature_diagnostics(src)
    assert len(diags) == 1
    assert diags[0]["code"] == "AINL_SIGNATURE_METADATA_INVALID"


def test_validate_result_against_signature():
    ok, errs = validate_result_against_signature({"total": 3.14}, "{total :float}")
    assert ok is True
    assert errs == []
    ok2, errs2 = validate_result_against_signature({"total": "x"}, "{total :float}")
    assert ok2 is False
    assert errs2


def test_retry_path_for_ptc_runner_signature():
    old = os.environ.get("AINL_PTC_RUNNER_MOCK")
    try:
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"
        adp = PtcRunnerAdapter(enabled=True)
        out = run_with_signature_retry(
            adapter=adp,
            lisp="(+ 1 2)",
            signature="{value :string}",
            max_attempts=2,
        )
        assert out["signature_ok"] is True
    finally:
        if old is None:
            os.environ.pop("AINL_PTC_RUNNER_MOCK", None)
        else:
            os.environ["AINL_PTC_RUNNER_MOCK"] = old
