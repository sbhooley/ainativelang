#!/usr/bin/env python3
"""Print or (opt-in) create scripts/ shims for bridge tools. Default: print only."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent

_SKIP = frozenset(
    {
        "_shim_delegate.py",
        "ainl_bridge_main.py",
        "generate_shims.py",
        "__init__.py",
    }
)

SHIM_TEMPLATE = '''#!/usr/bin/env python3
"""# Shim: delegates to armaraos/bridge/{target} — do NOT edit logic here; edit in bridge/.

``scripts/`` is not a Python package, so relative imports like ``from ..armaraos.bridge`` do not
apply. This shim loads ``armaraos/bridge/_shim_delegate.py`` via importlib and re-executes the
real script with the current ``sys.argv`` (so ``--dry-run`` and passthrough args behave identically).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TARGET = "{target}"
_HELP = f"""{{_TARGET}} shim — delegates to armaraos/bridge/{{_TARGET}} (via armaraos/bridge/_shim_delegate.py).

Implementation and flags are defined in armaraos/bridge/ only.
"""


def main() -> None:
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(_HELP, end="")
        sys.exit(0)
    root = Path(__file__).resolve().parent.parent
    delegate_path = root / "armaraos" / "bridge" / "_shim_delegate.py"
    if not delegate_path.is_file():
        print(
            f"ainl shim: missing {{delegate_path}}\\n"
            "  Clone or restore the repo so armaraos/bridge/ is present.",
            file=sys.stderr,
        )
        sys.exit(127)
    try:
        spec = importlib.util.spec_from_file_location("ainl_armaraos_shim_delegate", delegate_path)
        if spec is None or spec.loader is None:
            raise ImportError("invalid spec for _shim_delegate.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except ImportError as e:
        print(
            f"ainl shim: ImportError loading bridge delegate ({{e}}).\\n"
            "  Check that armaraos/bridge/_shim_delegate.py exists and is readable.",
            file=sys.stderr,
        )
        sys.exit(127)
    try:
        mod.run_bridge_script(_TARGET)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ainl shim: delegation failed: {{e}}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def iter_bridge_py() -> list[Path]:
    out: list[Path] = []
    for p in sorted(_BRIDGE.glob("*.py")):
        if p.name in _SKIP:
            continue
        rel = p.relative_to(_BRIDGE)
        if "tests" in rel.parts:
            continue
        out.append(p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Suggest or create scripts/ shims for armaraos/bridge/*.py. "
            "By default prints templates only (safe). "
            "Use --write only when you intend to add files under scripts/."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "WARNING: --write creates new files on disk after confirmation. "
            "Combining --dry-run with --write never writes (templates only)."
        ),
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print full template suggestions only; never write (also suppresses --write).",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help=(
            "DESTRUCTIVE: after confirmation, create only *missing* scripts/*.py shims. "
            "Ignored when --dry-run is set."
        ),
    )
    args = ap.parse_args()

    scripts_dir = _BRIDGE.parent.parent / "scripts"
    tools = iter_bridge_py()
    if not tools:
        print("No bridge Python tools found (after excludes).", file=sys.stderr)
        sys.exit(0)

    if args.write and not args.dry_run:
        missing = [p for p in tools if not (scripts_dir / p.name).is_file()]
        if not missing:
            print("All shims already exist under scripts/; nothing to create.", file=sys.stderr)
            sys.exit(0)
        n = len(missing)
        try:
            ans = input(f"About to create {n} shim file(s) in scripts/. Continue? [y/N] ")
        except EOFError:
            ans = ""
        if ans.strip() not in ("y", "Y"):
            print("Aborted; no files written.", file=sys.stderr)
            sys.exit(0)
        for p in missing:
            dest = scripts_dir / p.name
            body = SHIM_TEMPLATE.format(target=p.name).rstrip() + "\n"
            dest.write_text(body, encoding="utf-8")
            print(f"Wrote {dest}", file=sys.stderr)
        sys.exit(0)

    if args.write and args.dry_run:
        print(
            "Note: --dry-run prevents --write; printing templates only.\n",
            file=sys.stderr,
        )

    print("=== AINL OpenFang bridge — suggested scripts/ shims ===\n")
    print("Copy snippets below into scripts/<name> as needed, or use --write (without --dry-run) to create missing files.\n")

    for p in tools:
        target = p.name
        dest = scripts_dir / target
        exists = "exists" if dest.is_file() else "MISSING — create if you need scripts/ path"
        print(f"--- scripts/{target} ({exists}) ---\n")
        print(SHIM_TEMPLATE.format(target=target))
        print()

    print("=== Instructions ===")
    print("- chmod +x scripts/<tool>.py if you rely on shebang execution.")
    print("- Keep fingerprints in tooling/cron_registry.json aligned with payload strings you use.")
    print("- Prefer armaraos/bridge/ainl_bridge_main.py for CLI discovery when no scripts/ shim is required.")


if __name__ == "__main__":
    main()
