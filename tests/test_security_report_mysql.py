import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler_v2 import AICodeCompiler
from tooling.security_report import analyze_ir


def test_security_report_includes_mysql_metadata():
    code = 'S app core noop\nL1:\nR mysql.QUERY "SELECT 1" ->out\nJ out\n'
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")
    report = analyze_ir(ir)
    mysql = (report.get("summary") or {}).get("adapters", {}).get("mysql")
    assert mysql is not None
    assert "QUERY" in (mysql.get("verbs") or [])
    assert "network" in (mysql.get("privilege_tiers") or [])
