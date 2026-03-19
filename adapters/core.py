# Core builtin adapter for AINL
# Provides fundamental operations: now, math, string, collection utilities

import time

def core_now(frame, *args):
    """Return current timestamp (seconds)."""
    return time.time()

def add(frame, a, b):
    return a + b

def sub(frame, a, b):
    return a - b

def mul(frame, a, b):
    return a * b

def div(frame, a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b

def int_div(frame, a, b):
    return a // b

def mod(frame, a, b):
    return a % b

def pow_(frame, a, b):
    return a ** b

def len_(frame, value):
    if isinstance(value, (list, tuple, str, dict)):
        return len(value)
    raise TypeError("len() expects a collection")

def concat(frame, a, b):
    return str(a) + str(b)

def join(frame, sep, items):
    return sep.join(str(x) for x in items)

def stringify(frame, value):
    return str(value)

def lt(frame, a, b):
    return a < b

def gt(frame, a, b):
    return a > b

def lte(frame, a, b):
    return a <= b

def gte(frame, a, b):
    return a >= b

def eq(frame, a, b):
    return a == b

def ne(frame, a, b):
    return a != b

# --- String operations ---
def split(frame, s, sep):
    """Split string by separator (string). Returns list."""
    if not isinstance(s, str):
        s = str(s)
    if not isinstance(sep, str):
        sep = str(sep)
    return s.split(sep)

def contains(frame, s, substr):
    """Return True if substr in s."""
    return substr in s

def starts_with(frame, s, prefix):
    return s.startswith(prefix)

def ends_with(frame, s, suffix):
    return s.endswith(suffix)

def substr(frame, s, start, length=None):
    """Return substring. If length omitted, to end."""
    if not isinstance(s, str):
        s = str(s)
    if length is None:
        return s[start:]
    return s[start:start+length]

def replace(frame, s, old, new):
    return s.replace(old, new)

def to_lower(frame, s):
    return s.lower()

def to_upper(frame, s):
    return s.upper()

def trim(frame, s):
    return s.strip()

# Map of verbs to functions
VERBS = {
    'now': core_now,
    'add': add,
    'sub': sub,
    'mul': mul,
    'div': div,
    'idiv': int_div,
    'mod': mod,
    'pow': pow_,
    'len': len_,
    'concat': concat,
    'join': join,
    'stringify': stringify,
    'lt': lt,
    'gt': gt,
    'lte': lte,
    'gte': gte,
    'eq': eq,
    'ne': ne,
    # string
    'split': split,
    'contains': contains,
    'starts_with': starts_with,
    'ends_with': ends_with,
    'substr': substr,
    'replace': replace,
    'to_lower': to_lower,
    'to_upper': to_upper,
    'trim': trim,
}

def core_registry():
    return {
        "desc": "Core builtins",
        "module": "adapters.core",
        "verbs": {verb: {} for verb in VERBS.keys()}
    }

def get(verb):
    if verb in VERBS:
        return VERBS[verb]
    raise KeyError(f"Unknown core verb: {verb}")
