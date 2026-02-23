"""
Conformance tests: fixed .lang compiles to expected IR shape (AINL 1.0: labels have nodes, edges, legacy.steps) and emits produce expected artifacts.
See docs/CONFORMANCE.md for implementation status vs spec.
Run: pytest tests/test_conformance.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


# --- Fixtures: canonical .lang snippets and expected IR shapes ---

MINIMAL_API = """
S core web /api
D User id:I name:S
E /users G ->L1 ->users
L1: R db.F User * ->users J users
"""


def test_minimal_api_compiles():
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    assert "services" in ir
    assert "core" in ir["services"]
    assert "eps" in ir["services"]["core"]
    assert "/users" in ir["services"]["core"]["eps"]
    assert ir["services"]["core"]["eps"]["/users"]["label_id"] == "1"
    assert "types" in ir
    assert "User" in ir["types"]
    assert "labels" in ir
    assert "1" in ir["labels"]


def test_minimal_api_ir_labels_steps():
    """IR labels use legacy.steps (spec); fallback to steps for backward compat."""
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    lbl = ir["labels"].get("1", {})
    steps = lbl.get("legacy", {}).get("steps", lbl.get("steps", []))
    assert len(steps) >= 2
    ops = [s.get("op") for s in steps]
    assert "R" in ops
    assert "J" in ops


def test_minimal_api_emit_server_contains_route():
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    server = c.emit_server(ir)
    assert "@api.get('/users')" in server or "@api.get(\"/users\")" in server
    assert "_run_label(" in server
    assert "health" in server
    assert "ready" in server


def test_minimal_api_emit_openapi_has_path():
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    openapi_str = c.emit_openapi(ir)
    doc = json.loads(openapi_str)
    assert "/api/users" in doc.get("paths", {})
    assert "get" in doc["paths"]["/api/users"]
    assert "/api/health" in doc["paths"]
    assert "/api/ready" in doc["paths"]


def test_minimal_api_emit_react_non_empty():
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    react = c.emit_react(ir)
    assert len(react) > 0
    assert "React" in react or "useState" in react


def test_minimal_api_emit_prisma_has_model():
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    prisma = c.emit_prisma_schema(ir)
    assert "model" in prisma
    assert "User" in prisma


def test_ecom_dashboard_compiles():
    path = os.path.join(os.path.dirname(__file__), "test_ecom_dashboard.lang")
    with open(path) as f:
        code = f.read()
    c = AICodeCompiler()
    ir = c.compile(code)
    assert "core" in ir["services"]
    assert "fe" in ir["services"]
    assert "Product" in ir["types"]
    assert "Order" in ir["types"]
    assert "/products" in ir["services"]["core"].get("eps", {})
    assert "routes" in ir["services"].get("fe", {})


def test_ecom_dashboard_emit_server_has_health_ready():
    path = os.path.join(os.path.dirname(__file__), "test_ecom_dashboard.lang")
    with open(path) as f:
        code = f.read()
    c = AICodeCompiler()
    ir = c.compile(code)
    server = c.emit_server(ir)
    assert "/health" in server
    assert "/ready" in server
    assert "checkout" in server.lower()


def test_ecom_dashboard_emit_sql_migrations():
    path = os.path.join(os.path.dirname(__file__), "test_ecom_dashboard.lang")
    with open(path) as f:
        code = f.read()
    c = AICodeCompiler()
    ir = c.compile(code)
    sql = c.emit_sql_migrations(ir, dialect="postgres")
    assert "CREATE TABLE" in sql
    assert "Product" in sql
    assert "Order" in sql


def test_auth_op_stored_in_ir():
    code = """
S core web /api
A jwt Authorization
D User id:I
E /me G ->L1
L1: R db.F User * ->u J u
"""
    c = AICodeCompiler()
    ir = c.compile(code)
    assert "auth" in ir["services"]
    assert ir["services"]["auth"].get("kind") == "jwt"
    assert ir["services"]["auth"].get("arg") == "Authorization"


def test_auth_emit_server_has_depends():
    code = """
S core web /api
A apikey X-API-Key
D User id:I
E /users G ->L1
L1: R db.F User * ->users J users
"""
    c = AICodeCompiler()
    ir = c.compile(code)
    server = c.emit_server(ir)
    assert "Depends" in server
    assert "_auth_dep" in server
    assert "401" in server


def test_ir_json_roundtrip():
    c = AICodeCompiler()
    ir = c.compile(MINIMAL_API)
    js = c.emit_ir_json(ir)
    back = json.loads(js)
    assert back["services"]["core"]["eps"]["/users"]["label_id"] == "1"
