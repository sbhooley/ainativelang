"""
Execution engine: runs label steps (R, J, P, If, Err, Retry, Call, Set, Filt, Sort) using pluggable adapters.
Request hits E /path -> handler runs engine.run(label_id) and returns result.
"""
from typing import Any, Dict, List

from adapters import AdapterRegistry


def _normalize_label_id(tgt: str) -> str:
    """->L1 or L1 -> 1; ->L1:core -> 1."""
    s = tgt.split("->")[-1].strip()
    if s.startswith("L"):
        s = s[1:]
    if ":" in s:
        s = s.split(":")[-1]
    return s


def _eval_cond(cond: str, ctx: Dict[str, Any]) -> bool:
    """Simple condition: var (truthy), var=value, or var? (exists)."""
    if not cond:
        return False
    if cond.endswith("?"):
        return ctx.get(cond[:-1]) is not None
    if "=" in cond:
        var, val = cond.split("=", 1)
        return str(ctx.get(var.strip())) == val.strip()
    return bool(ctx.get(cond))


class ExecutionEngine:
    """Runs a label's steps (R, J, P, If, Err, Retry, Call, Set, Filt, Sort) and returns the JSON return value."""

    def __init__(self, ir: Dict[str, Any], adapters: AdapterRegistry):
        self.ir = ir
        self.adapters = adapters
        self._labels = ir.get("labels", {})

    def _run_steps(self, steps: List[Dict[str, Any]], ctx: Dict[str, Any], label_id: str) -> Any:
        """Execute steps; returns value when J is hit, or None. Handles If/Call by recursion."""
        i = 0
        while i < len(steps):
            step = steps[i]
            op = step.get("op")

            if op == "R":
                out_var = step.get("out", "res")
                src = step.get("src", "db")
                req_op = (step.get("req_op") or "F").upper()
                entity = step.get("entity", "")
                target = step.get("target", entity)  # canonical: path or entity
                fields = step.get("fields", "*")
                try:
                    if src == "db":
                        adp = self.adapters.get_db()
                        if req_op == "F":
                            ctx[out_var] = adp.find(entity or target, fields)
                        elif req_op == "G":
                            ctx[out_var] = adp.get(entity or target, fields)
                        else:
                            ctx[out_var] = adp.find(entity or target, fields)
                    elif src == "api":
                        adp = self.adapters.get_api()
                        ctx[out_var] = adp.get(target or entity or "/")
                    else:
                        ctx[out_var] = []
                except Exception as e:
                    # Check for Err handler in next step (simplified: next step Err -> run handler)
                    if i + 1 < len(steps) and steps[i + 1].get("op") == "Err":
                        handler = steps[i + 1].get("handler")
                        if handler:
                            ctx["_error"] = str(e)
                            return self.run(handler)
                    raise

            elif op == "J":
                var = step.get("var", "data")
                return ctx.get(var)

            elif op == "P":
                # Spec: P is declaration only; never execute. (Legacy IR may still contain P steps; skip.)
                pass

            elif op == "If":
                cond = step.get("cond", "")
                then_l = step.get("then")
                else_l = step.get("else")
                if _eval_cond(cond, ctx):
                    if then_l:
                        result = self._run_steps(self._get_steps(self._labels.get(_normalize_label_id(then_l), {})), ctx, then_l)
                        if result is not None:
                            return result
                elif else_l:
                    result = self._run_steps(self._get_steps(self._labels.get(_normalize_label_id(else_l), {})), ctx, else_l)
                    if result is not None:
                        return result

            elif op == "Err":
                pass  # Handled in R's except above

            elif op == "Retry":
                count = int(step.get("count", 3))
                backoff_ms = int(step.get("backoff_ms", 0))
                if i > 0:
                    prev = steps[i - 1]
                    last_result = None
                    for _ in range(count):
                        try:
                            if prev.get("op") == "R":
                                out_var = prev.get("out", "res")
                                src = prev.get("src", "db")
                                req_op = (prev.get("req_op") or "F").upper()
                                entity = prev.get("entity", "")
                                target = prev.get("target", entity)
                                fields = prev.get("fields", "*")
                                if src == "db":
                                    adp = self.adapters.get_db()
                                    ctx[out_var] = adp.find(entity or target, fields) if req_op == "F" else adp.get(entity or target, fields)
                                elif src == "api":
                                    ctx[out_var] = self.adapters.get_api().get(target or entity or "/")
                                else:
                                    ctx[out_var] = []
                                break
                        except Exception:
                            if backoff_ms:
                                import time
                                time.sleep(backoff_ms / 1000.0)
                    else:
                        raise RuntimeError("Retry exhausted")
                i += 1
                continue

            elif op == "Call":
                target = step.get("label")
                if target:
                    result = self._run_steps(self._get_steps(self._labels.get(_normalize_label_id(target), {})), dict(ctx), target)
                    if result is not None:
                        ctx["_call_result"] = result
                i += 1
                continue

            elif op == "Set":
                name = step.get("name")
                ref = step.get("ref")
                if name and ref is not None:
                    ctx[name] = ctx.get(ref)
                i += 1
                continue

            elif op == "Filt":
                name = step.get("name")
                ref = step.get("ref")
                field = step.get("field")
                cmp_val = step.get("cmp")
                value = step.get("value")
                arr = ctx.get(ref)
                if isinstance(arr, list) and field is not None:
                    try:
                        val_conv = int(value) if value.isdigit() else value
                    except ValueError:
                        val_conv = value
                    out = []
                    for item in (arr or []):
                        if not isinstance(item, dict):
                            continue
                        v = item.get(field)
                        if cmp_val == "=" and v == val_conv:
                            out.append(item)
                        elif cmp_val == "!=" and v != val_conv:
                            out.append(item)
                        elif cmp_val in (">", ">=") and v is not None and v >= val_conv if cmp_val == ">=" else v > val_conv:
                            out.append(item)
                        elif cmp_val in ("<", "<=") and v is not None and v <= val_conv if cmp_val == "<=" else v < val_conv:
                            out.append(item)
                    ctx[name] = out
                else:
                    ctx[name] = []
                i += 1
                continue

            elif op == "Sort":
                name = step.get("name")
                ref = step.get("ref")
                field = step.get("field")
                order = (step.get("order") or "asc").lower()
                arr = ctx.get(ref)
                if isinstance(arr, list) and field:
                    ctx[name] = sorted(arr, key=lambda x: (x.get(field) is not None, x.get(field)), reverse=(order == "desc"))
                else:
                    ctx[name] = list(arr) if arr else []
                i += 1
                continue

            i += 1
        return ctx.get("data", [])

    def _get_steps(self, label: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Steps live under legacy.steps (spec); support legacy bare 'steps' for backward compat."""
        leg = label.get("legacy", {})
        if leg and "steps" in leg:
            return leg["steps"]
        return label.get("steps", [])

    def run(self, label_id: str) -> Any:
        """Execute the label's steps; returns the value to send as response body."""
        label_id = _normalize_label_id(label_id)
        label = self._labels.get(label_id, {})
        steps: List[Dict[str, Any]] = self._get_steps(label)
        ctx: Dict[str, Any] = {}
        return self._run_steps(steps, ctx, label_id)
