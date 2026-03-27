import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler
from tooling.security_report import analyze_ir


def test_security_report_includes_supabase_metadata():
    code = 'S app core noop\nL1:\nR supabase.SELECT "users" ->out\nJ out\n'
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    report = analyze_ir(ir)
    adp = (report.get("summary") or {}).get("adapters", {}).get("supabase")
    assert adp is not None
    assert "SELECT" in (adp.get("verbs") or [])
    assert "network" in (adp.get("privilege_tiers") or [])
