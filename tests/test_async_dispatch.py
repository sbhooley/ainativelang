import os
import sys
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.engine import RuntimeEngine


class _AsyncProbeAdapter(RuntimeAdapter):
    def __init__(self):
        self.sync_calls = 0
        self.async_calls = 0

    def call(self, target, args, context):
        self.sync_calls += 1
        return {"mode": "sync", "target": target, "args": args}

    async def call_async(self, target, args, context):
        self.async_calls += 1
        return {"mode": "async", "target": target, "args": args}


def _run(runtime_async: bool):
    reg = AdapterRegistry(allowed=["core", "probe"])
    probe = _AsyncProbeAdapter()
    reg.register("probe", probe)
    code = 'L1: R probe.echo "hello" ->out J out\n'
    eng = RuntimeEngine.from_code(code, strict=False, adapters=reg, runtime_async=runtime_async)
    if runtime_async:
        out = asyncio.run(eng.run_label_async("1", frame={}))
    else:
        out = eng.run_label("1", frame={})
    return out, probe


def test_runtime_sync_dispatch_keeps_sync_path():
    out, probe = _run(runtime_async=False)
    assert out["mode"] == "sync"
    assert probe.sync_calls == 1
    assert probe.async_calls == 0


def test_runtime_async_dispatch_prefers_call_async():
    out, probe = _run(runtime_async=True)
    assert out["mode"] == "async"
    assert probe.sync_calls == 0
    assert probe.async_calls == 1


class _SleepProbeAdapter(RuntimeAdapter):
    async def call_async(self, target, args, context):
        delay = float(args[0]) if args else 0.05
        await asyncio.sleep(delay)
        return {"slept": delay}


def test_runtime_native_async_engine_multistep():
    reg = AdapterRegistry(allowed=["core", "probe"])
    reg.register("probe", _AsyncProbeAdapter())
    code = 'L1: Call L2 J _call_result\nL2: R probe.echo "b" ->b J b\n'
    eng = RuntimeEngine.from_code(code, strict=False, adapters=reg, runtime_async=True)
    out = asyncio.run(eng.run_label_async(eng.default_entry_label(), frame={}))
    assert out["mode"] == "async"
    assert out["args"][0] == "b"


def test_runtime_native_async_engine_concurrency_labels():
    reg = AdapterRegistry(allowed=["core", "probe"])
    reg.register("probe", _SleepProbeAdapter())
    code = (
        'L1: If which=a ->La ->Lb\n'
        'La: R probe.sleep 0.15 ->out J out\n'
        'Lb: R probe.sleep 0.15 ->out J out\n'
    )
    eng = RuntimeEngine.from_code(code, strict=False, adapters=reg, runtime_async=True)

    async def _run_two():
        t0 = time.perf_counter()
        await asyncio.gather(
            eng.run_label_async("1", frame={"which": "a"}),
            eng.run_label_async("1", frame={"which": "b"}),
        )
        return time.perf_counter() - t0

    elapsed = asyncio.run(_run_two())
    assert elapsed < 0.28
