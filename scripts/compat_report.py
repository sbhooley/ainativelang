#!/usr/bin/env python3
"""
Compare two AINL IRs and report breaking/additive changes (Compat: break | add).
Usage: python scripts/compat_report.py old_ir.json new_ir.json
"""
import json
import sys


def diff_types(old_t, new_t):
    breaks = []
    adds = []
    for name, data in new_t.items():
        if name not in old_t:
            adds.append(f"Type added: {name}")
            continue
        old_f = set(old_t[name].get("fields", {}))
        new_f = set(data.get("fields", {}))
        removed = old_f - new_f
        added_f = new_f - old_f
        if removed:
            breaks.append(f"Type {name}: removed fields {removed}")
        if added_f:
            adds.append(f"Type {name}: added fields {added_f}")
    for name in old_t:
        if name not in new_t:
            breaks.append(f"Type removed: {name}")
    return breaks, adds


def diff_eps(old_eps, new_eps):
    breaks = []
    adds = []
    for path, ep in new_eps.items():
        if path not in old_eps:
            adds.append(f"Endpoint added: {path} {ep.get('method', 'G')}")
        elif old_eps[path].get("method") != ep.get("method"):
            breaks.append(f"Endpoint {path}: method changed")
    for path in old_eps:
        if path not in new_eps:
            breaks.append(f"Endpoint removed: {path}")
    return breaks, adds


def main():
    if len(sys.argv) < 3:
        print("Usage: compat_report.py old_ir.json new_ir.json")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        old_ir = json.load(f)
    with open(sys.argv[2]) as f:
        new_ir = json.load(f)
    compat = new_ir.get("compat", "add")
    old_t = old_ir.get("types", {})
    new_t = new_ir.get("types", {})
    old_eps = {}
    new_eps = {}
    for srv, data in old_ir.get("services", {}).items():
        old_eps.update(data.get("eps", {}))
    for srv, data in new_ir.get("services", {}).items():
        new_eps.update(data.get("eps", {}))
    breaks, adds = [], []
    b1, a1 = diff_types(old_t, new_t)
    breaks.extend(b1)
    adds.extend(a1)
    b2, a2 = diff_eps(old_eps, new_eps)
    breaks.extend(b2)
    adds.extend(a2)
    print("Breaking changes:", len(breaks))
    for x in breaks:
        print("  -", x)
    print("Additive changes:", len(adds))
    for x in adds:
        print("  +", x)
    if compat == "break" and breaks:
        print("\nCompat=break but breaking changes present.")
    sys.exit(0)

if __name__ == "__main__":
    main()
