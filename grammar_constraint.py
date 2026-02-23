"""
Next-valid-token constraint for AINL: given a prefix (possibly mid-line), return allowed next tokens.
Use for constrained decoding so 1B/3B models stay within valid AINL.
"""
import re
from typing import Set, List, Tuple

# Ops that start a line (one or two chars, then optional :)
OPS = {"S", "D", "E", "L", "R", "J", "U", "T", "Q", "Sc", "Cr", "P", "C", "A", "Rt", "Lay", "Fm", "Tbl", "Ev"}
# Two-char ops (so we don't suggest "S" then "c" as separate ops)
TWO_CHAR_OPS = {"Sc", "Cr", "Rt", "Lay", "Fm", "Tbl", "Ev"}
# After newline we can also have L<id>:
LABEL_OP_PREFIX = "L"

METHODS = {"G", "P", "U", "D"}
TYPES_SIMPLE = {"I", "i", "S", "s", "B", "F", "D", "J"}
PATH_START = "/"
OUT_ARROW = "->"


def _last_line_and_tail(prefix: str) -> Tuple[str, str]:
    """Return (last_line, rest_before_last_line)."""
    if not prefix:
        return "", ""
    idx = prefix.rfind("\n")
    if idx == -1:
        return prefix, ""
    return prefix[idx + 1:], prefix[: idx + 1]


def _tokenize_line(line: str) -> List[str]:
    """Simple space-split tokens; keeps -> and path segments as tokens."""
    return re.split(r"\s+", line.strip()) if line.strip() else []


def next_valid_tokens(prefix: str) -> Set[str]:
    """
    Return a set of allowed next tokens (strings). May be single chars or full tokens.
    Used to mask logits: only allow these tokens as next.
    """
    last_line, _ = _last_line_and_tail(prefix)
    tokens = _tokenize_line(last_line)

    # Empty line or start of line
    if not tokens:
        # Can start with any op; for two-char we allow first char
        out = set(OPS)
        # Add "L" for labels (L1:, L2:, etc.)
        out.add("L")
        return out

    first = tokens[0]

    # After S: name, then mode, then optional path
    if first == "S":
        if len(tokens) == 1:
            return {"core", "fe", "api"}
        if len(tokens) == 2:
            return {"web", "api"}
        if len(tokens) == 3:
            return {"/api", "/", "/v1", ""}  # path or empty
        return set()

    # After D: type_name then field:type...
    if first == "D":
        if len(tokens) == 1:
            return {"User", "Product", "Order", "Post", "Task", "Event", "Article", "Comment", "Invoice"}
        # After type name, we have field:type; allow common fields and types
        return {"id:I", "name:S", "title:S", "status:S", "created:D", "amount:F", "uid:I", "total:F", "body:S", "email:S"}

    # After E: path, method, ->label, [->returnVar]
    if first == "E":
        if len(tokens) == 1:
            return {"/users", "/products", "/orders", "/me", "/checkout", "/"}
        if len(tokens) == 2:
            return {"G", "P", "U", "D"}
        if len(tokens) == 3:
            return {"->L1", "->L2", "->L3", "->1", "->2"}
        if len(tokens) == 4 and tokens[3].startswith("->"):
            return {"->users", "->products", "->orders", "->data", "->res"}
        return set()

    # After L<id>: (label line) R, J, or inline slots
    if first.startswith("L") and first.endswith(":"):
        return {"R", "J", "db.F", "api.G", "P"}

    # After R: db.F Entity * ->out or api.G /path ->out
    if first == "R":
        if len(tokens) == 1:
            return {"db.F", "api.G", "db.P", "api.P"}
        if len(tokens) == 2:
            return {"User", "Product", "Order", "Post", "*"}
        if len(tokens) == 3:
            return {"*", "->users", "->products", "->orders", "->res", "->data"}
        return set()

    # After J: var name
    if first == "J":
        if len(tokens) == 1:
            return {"users", "products", "orders", "data", "res", "u"}
        return set()

    # After U: UI name then optional props
    if first == "U":
        if len(tokens) == 1:
            return {"Dashboard", "ProductList", "OrderTable", "UserList", "Form", "Detail"}
        return {"products", "orders", "users", "data"}

    # After T: var:type or var type
    if first == "T":
        if len(tokens) == 1:
            return {"users:A[User]", "products:A[Product]", "orders:A[Order]", "data:any"}
        return set()

    # After A: kind, header
    if first == "A":
        if len(tokens) == 1:
            return {"jwt", "apikey"}
        if len(tokens) == 2:
            return {"Authorization", "X-API-Key"}
        return set()

    # After Rt: path, ui name
    if first == "Rt":
        if len(tokens) == 1:
            return {"/", "/products", "/orders", "/users"}
        if len(tokens) == 2:
            return {"Dashboard", "ProductList", "OrderTable", "UserList"}
        return set()

    # After Cr: label, cron expr
    if first == "Cr":
        if len(tokens) == 1:
            return {"L1", "1", "2"}
        if len(tokens) == 2:
            return {"*/5", "*", "*/15"}
        if len(tokens) <= 6:
            return {"*", "*/5", "*/15"}
        return set()

    # After P: name, amount, currency, [desc]
    if first == "P":
        if len(tokens) == 1:
            return {"checkout", "payment"}
        if len(tokens) == 2:
            return {"1999", "999"}
        if len(tokens) == 3:
            return {"usd", "eur"}
        return set()

    # After C: name, key, ttl
    if first == "C":
        if len(tokens) == 1:
            return {"cart", "sess", "cache"}
        if len(tokens) == 2:
            return {"sessionId", "cartId"}
        if len(tokens) == 3:
            return {"3600", "86400"}
        return set()

    # Default: allow newline and next op starters
    return {"\n", "S", "D", "E", "R", "J", "U", "T", "A", "Q", "Sc", "Cr", "P", "C", "Rt", "Lay", "Fm", "Tbl", "Ev", "L"}


def is_valid_ainl_prefix(prefix: str) -> bool:
    """Heuristic: no obvious invalid token in last line."""
    last_line, _ = _last_line_and_tail(prefix)
    if not last_line.strip():
        return True
    tokens = _tokenize_line(last_line)
    if not tokens:
        return True
    first = tokens[0]
    if first in OPS or (first.startswith("L") and first.endswith(":")):
        return True
    if first.startswith("/") or first in METHODS or first.startswith("->"):
        return True
    return False
