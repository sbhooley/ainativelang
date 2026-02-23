#!/usr/bin/env python3
"""
Minimal web validator: POST .lang body, returns { "ok", "ir" } or { "error": "..." }.
Run: uvicorn scripts.validator_app:app --reload --port 8766
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from compiler_v2 import AICodeCompiler

app = FastAPI(title="AINL Validator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    return obj


@app.post("/validate")
async def validate(request: Request):
    """POST raw .lang content in body. Returns { "ok": true, "ir": {...} } or { "ok": false, "error": "..." }."""
    body = (await request.body()).decode("utf-8", errors="replace")
    try:
        c = AICodeCompiler()
        ir = c.compile(body)
        return {"ok": True, "ir": to_jsonable(ir)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/", response_class=HTMLResponse)
def index():
    """Simple paste-and-validate page."""
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>AINL Validator</title>
<style>
  body { font-family: system-ui,sans-serif; margin: 1rem; background: #1a1a2e; color: #eee; }
  textarea { width: 100%; height: 240px; background: #16213e; color: #eee; border: 1px solid #0f3460; padding: 8px; }
  button { padding: 8px 16px; background: #e94560; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
  pre { background: #16213e; padding: 12px; overflow: auto; white-space: pre-wrap; font-size: 12px; }
  .err { color: #e94560; }
  .ok { color: #0f0; }
</style>
</head>
<body>
  <h1>AINL Validator</h1>
  <p>Paste .lang code and click Validate.</p>
  <textarea id="code" placeholder="S core web /api&#10;D User id:I name:S&#10;E /users G ->L1&#10;L1: R db.F User * ->users J users">S core web /api
D User id:I name:S
E /users G ->L1
L1: R db.F User * ->users J users</textarea>
  <br/><br/>
  <button onclick="run()">Validate</button>
  <div id="out"></div>
  <script>
    async function run() {
      const code = document.getElementById('code').value;
      const out = document.getElementById('out');
      try {
        const r = await fetch('/validate', { method: 'POST', body: code, headers: { 'Content-Type': 'text/plain' } });
        const j = await r.json();
        if (j.ok) {
          out.innerHTML = '<pre class="ok">' + JSON.stringify(j.ir, null, 2) + '</pre>';
        } else {
          out.innerHTML = '<pre class="err">' + (j.error || 'Unknown error') + '</pre>';
        }
      } catch (e) {
        out.innerHTML = '<pre class="err">' + e.message + '</pre>';
      }
    }
  </script>
</body>
</html>
"""


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8766)


if __name__ == "__main__":
    main()
