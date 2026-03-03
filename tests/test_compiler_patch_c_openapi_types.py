import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler


def test_openapi_type_mapping_for_boolean_and_datetime():
    c = AICodeCompiler()
    code = (
        "S core web /api\n"
        "D User active:B created_at:D\n"
        "E /users G ->L1 A[User]\n"
        "L1: J users\n"
    )
    ir = c.compile(code)
    doc = json.loads(c.emit_openapi(ir))
    props = doc["components"]["schemas"]["User"]["properties"]

    assert props["active"]["type"] == "boolean"
    assert props["created_at"]["type"] == "string"
    assert props["created_at"]["format"] == "date-time"
