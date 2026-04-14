#!/usr/bin/env python3
"""Local dev harness: run `demo/test_openspace_mcp.ainl` with the OpenClaw adapter registry."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from adapters.openclaw_integration import openclaw_monitor_registry  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402

DEMO = ROOT / "demo" / "test_openspace_mcp.ainl"


def main() -> None:
    source = DEMO.read_text(encoding="utf-8")
    print("🔌 Loading OpenClaw adapter registry...")
    reg = openclaw_monitor_registry()
    print(f"   Adapters: {list(reg._adapters.keys())}")

    print("\n🚀 Building engine...")
    engine = RuntimeEngine.from_code(
        code=source,
        adapters=reg,
        source_path=str(DEMO),
        strict=False,
    )
    print(f"✅ Engine built. Default entry: {engine.default_entry_label()}")

    print("\n▶️  Running...")
    try:
        result = engine.run_label(engine.default_entry_label())
        print(f"\n✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        print("\nAdapter registry contents:")
        if engine.adapters:
            print(f"  Type: {type(engine.adapters)}")
            print(f"  Registered adapters: {list(engine.adapters.keys())}")
            print(f"  Adapter 'mcp' in registry: {hasattr(engine.adapters, 'mcp')}")
            print(f"  Adapter lookup for 'mcp': {getattr(engine.adapters, 'mcp', None)}")
            try:
                mcp_adapter = engine.adapters.get("mcp")
                print(f"  mcp_adapter type: {type(mcp_adapter)}")
                if mcp_adapter:
                    print(
                        f"  mcp_adapter methods: {[m for m in dir(mcp_adapter) if not m.startswith('_')]}"
                    )
            except Exception:
                pass
        else:
            print("  No adapter registry available")
        sys.exit(1)


if __name__ == "__main__":
    main()
