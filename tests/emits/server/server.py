"""Web server from AI-Native Lang: real runtime (R/P/Sc via adapters) + static + logging + rate limit."""
import json
import sys
import time
import uuid
import os
from pathlib import Path
from collections import defaultdict

# Allow importing runtime + adapters (same dir in Docker, else repo root)
_dir = Path(__file__).resolve().parent
_root = _dir if (_dir / 'runtime.py').exists() else _dir.parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from runtime import ExecutionEngine
from adapters import mock_registry

# Load IR (emitted with server); use real adapters by replacing mock_registry
_ir_path = Path(__file__).resolve().parent / "ir.json"
with open(_ir_path) as f:
    _ir = json.load(f)
_registry = mock_registry(_ir.get("types"))
_engine = ExecutionEngine(_ir, _registry)

_metrics = defaultdict(int)
_trace_enabled = False

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())[:8]
        trace_id = req_id if _trace_enabled else None
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        # Never log Authorization or other secret headers (fix #11).
        log = {"request_id": req_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": round(duration_ms, 2)}
        if trace_id:
            log["trace_id"] = trace_id
        _metrics["requests_total"] += 1
        print(json.dumps(log))
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 0):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.window_start = defaultdict(float)
        self.count = defaultdict(int)

    async def dispatch(self, request: Request, call_next):
        if self.rpm <= 0:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.time()
        if now - self.window_start[client] > 60:
            self.window_start[client] = now
            self.count[client] = 0
        self.count[client] += 1
        if self.count[client] > self.rpm:
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=429, content={"error": "rate limit exceeded"})
        return await call_next(request)

app = FastAPI(title="Lang Server")
_rate_limit = int(os.environ.get("RATE_LIMIT", "0"))
app.add_middleware(RateLimitMiddleware, requests_per_minute=_rate_limit)
app.add_middleware(LoggingMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def _run_label(lid):
    r = _engine.run(lid); return {"data": r if r is not None else []}

api = FastAPI()

def _iter_eps(eps):
    out = []
    for path, val in eps.items():
        if not isinstance(val, dict): continue
        if "label_id" in val or "method" in val:
            out.append((path, val.get("method", "G"), val))
        else:
            for method, ep in val.items():
                if isinstance(ep, dict):
                    out.append((path, method, ep))
    return out

@api.get('/products')
def get_products():
    return _run_label('1')

@api.post('/products')
def post_products():
    return _run_label('7')

@api.get('/product')
def get_product():
    return _run_label('6')

@api.get('/orders')
def get_orders():
    return _run_label('2')

@api.post('/orders')
def post_orders():
    return _run_label('9')

@api.get('/order')
def get_order():
    return _run_label('8')

@api.post('/checkout')
def post_checkout():
    return _run_label('3')

@api.get('/customers')
def get_customers():
    return _run_label('10')

@api.get("/health")
def health():
    return {"status": "ok"}

@api.get("/ready")
def ready():
    return {"ready": True}

app.mount("/api", api)

# Static: do not write user-provided content to static_dir (fix #10).
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
