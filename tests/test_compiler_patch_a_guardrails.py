import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_inline_if_with_missing_then_target_does_not_crash():
    c = AICodeCompiler(strict_mode=True)
    code = "L1: If cond\nL2: J ok\n"
    ir = c.compile(code)
    assert isinstance(ir, dict)
    assert "labels" in ir


@pytest.mark.parametrize(
    "code,expected_substring",
    [
        ("htp.Get /x ->out\n", "unknown module"),
        ("If cond ->L1 ->L2\n", "label-only op"),
        ("S core web /api\nE /x G\n", "requires at least"),
        ("L1: J a\nD User id:I\n", "auto-closed label"),
    ],
)
def test_diagnostic_classifier_substrings_remain_present(code: str, expected_substring: str):
    c = AICodeCompiler(strict_mode=True)
    ir = c.compile(code)
    joined = "\n".join(ir.get("errors", []))
    assert expected_substring in joined


@pytest.mark.parametrize(
    "name,code,expected",
    [
        (
            "arith_endpoint",
            "S core web /api\nE /sum G ->L1 ->out\nL1: X out add 2 3 J out\n",
            {
                "labels_sha256": "ef566311fa33b4f2641b832464d8e31d527796d4fd9111ba23650bbe03e10191",
                "graph_semantic_checksum": "sha256:6c2054b0040775d99d41bd8070e338bf2d4cf7d6b40f4ce13f4497b6b41053a3",
                "emit_ir_json_sha256": "4b59f5f73673114cb9ed3ab3ba1cc009810a2f647b2bc6684d9d515dcbbe122f",
                "emit_openapi_sha256": "25afd06f70d158286c9a39aa23415b8ed87619f4705c97c56c67e88653f0a805",
                "emit_server_sha256": "f6bb40b5dccdcd4bed39a7708e402f94532e2345cc1b732be3914a7c590cda62",
                "emit_react_sha256": "25e1fe1ba3bf5e91937e07974fb3a604afdad6d306aab3229f5d769c755b83f7",
            },
        ),
        (
            "inline_if_flow",
            "S core web /api\nE /flow G ->L1 ->out\nL1: Set cond true If cond ->L2 ->L3\nL2: Set out pass J out\nL3: Set out fail J out\n",
            {
                "labels_sha256": "63aaf5c65678a1ca7966a3b2f51b872f3e071155691d76546b15546d72e24a11",
                "graph_semantic_checksum": "sha256:03597e2e690a15964074adb1fcdf52b0f323fd47267fc493b69bb610277f111e",
                "emit_ir_json_sha256": "1375e09898518a71fb75ce8c720df4aaf4586f1172f58efd63c0a50cd5d211a4",
                "emit_openapi_sha256": "264d34063bacf9343560e06e4d505242f3dcd8971a00ed52c670dc2fc6b82d9c",
                "emit_server_sha256": "78bf2178ac822946213ba08acf1d41e9557fe1c352bbfa84386bc40924af3e0a",
                "emit_react_sha256": "25e1fe1ba3bf5e91937e07974fb3a604afdad6d306aab3229f5d769c755b83f7",
            },
        ),
    ],
)
def test_patch_a_valid_artifacts_fingerprint_lock(name: str, code: str, expected: dict):
    c = AICodeCompiler(strict_mode=False)
    ir = c.compile(code)
    assert not ir.get("errors"), f"{name} compile errors: {ir.get('errors')}"

    labels_json = json.dumps(ir.get("labels", {}), sort_keys=True, separators=(",", ":"))
    actual = {
        "labels_sha256": _sha256(labels_json),
        "graph_semantic_checksum": ir.get("graph_semantic_checksum"),
        "emit_ir_json_sha256": _sha256(c.emit_ir_json(ir)),
        "emit_openapi_sha256": _sha256(c.emit_openapi(ir)),
        "emit_server_sha256": _sha256(c.emit_server(ir)),
        "emit_react_sha256": _sha256(c.emit_react(ir)),
    }
    assert actual == expected


@pytest.mark.parametrize(
    "if_tail",
    [
        "c ->L2",
        "c ->L2 ->L3",
        "c L2 L3",
        "c ->L2 L3:",
        "c L2 ->L3",
        "c L2 3",
    ],
)
def test_if_step_shape_parity_inline_vs_standalone(if_tail: str):
    c_inline = AICodeCompiler()
    ir_inline = c_inline.compile(f"L1: If {if_tail}\nL2: J ok\nL3: J err\n")
    step_inline = ir_inline["labels"]["1"]["legacy"]["steps"][0]

    c_standalone = AICodeCompiler()
    ir_standalone = c_standalone.compile(f"L1:\nIf {if_tail}\nL2: J ok\nL3: J err\n")
    step_standalone = ir_standalone["labels"]["1"]["legacy"]["steps"][0]

    assert step_inline["op"] == "If"
    assert step_standalone["op"] == "If"
    assert step_inline["then"] == step_standalone["then"]
    assert step_inline["else"] == step_standalone["else"]
