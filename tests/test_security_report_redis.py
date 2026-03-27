import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler
from tooling.security_report import analyze_ir


def test_security_report_includes_redis_metadata():
    code = 'S app core noop\nL1:\nR redis.GET "k" ->out\nJ out\n'
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    report = analyze_ir(ir)
    redis = (report.get("summary") or {}).get("adapters", {}).get("redis")
    assert redis is not None
    assert "GET" in (redis.get("verbs") or [])
    assert "network" in (redis.get("privilege_tiers") or [])
