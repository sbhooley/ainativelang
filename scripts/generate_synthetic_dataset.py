#!/usr/bin/env python3
"""
Generate synthetic AINL dataset: valid .lang programs (CRUD, auth, cron, pay, scrape).
Validates each with compiler; writes only programs that compile.
Usage: python scripts/generate_synthetic_dataset.py [--count 10000] [--out data/synthetic]
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler_v2 import AICodeCompiler

# Building blocks for valid programs
SERVICE_NAMES = ["core", "fe", "api"]
MODES = ["web", "api"]
PATHS = ["/api", "/", "/v1"]
ENTITY_NAMES = [
    "User", "Product", "Order", "Post", "Comment", "Task", "Event", "Ticket",
    "Article", "Category", "Item", "Invoice", "Session", "Profile",
]
FIELD_TYPES = ["I", "S", "F", "B", "D", "J"]
FIELD_NAMES = ["id", "name", "title", "status", "created", "amount", "uid", "total", "body", "email", "sku", "price"]
METHODS = ["G", "P", "U", "D"]
AUTH_KINDS = ["jwt", "apikey"]
AUTH_HEADERS = ["Authorization", "X-API-Key"]


def random_type():
    if random.random() < 0.2:
        return f"E[{random.choice(['A','B','C'])}]"
    if random.random() < 0.15:
        return f"A[{random.choice(ENTITY_NAMES)}]"
    return random.choice(FIELD_TYPES)


def gen_d_type_for_entity(name: str):
    n_fields = random.randint(2, 6)
    fields = ["id:I"]
    used = {"id"}
    pool = [f for f in FIELD_NAMES if f not in used]
    for _ in range(n_fields - 1):
        f = random.choice(pool) if pool else "field"
        if f not in used:
            used.add(f)
            pool = [x for x in FIELD_NAMES if x not in used]
        fields.append(f"{f}:{random_type()}")
    return f"D {name} " + " ".join(fields)


def gen_s_services(has_fe: bool = True):
    lines = ["S core web /api", "S fe web /"] if has_fe else ["S core web /api"]
    return "\n".join(lines)


def gen_e_and_labels(entities: list, count: int):
    """Generate E and L blocks for GET list endpoints."""
    lines = []
    for i, ent in enumerate(entities[:count]):
        path = f"/{ent.lower()}s"
        lid = str(i + 1)
        var = ent.lower() + "s"
        lines.append(f"E {path} G ->L{lid} ->{var}")
        lines.append(f"L{lid}: R db.F {ent} * ->{var} J {var}")
    return "\n".join(lines)


def gen_ui_and_routes(entities: list, count: int):
    ui_names = [f"{e}List" for e in entities[:count]]
    lines = []
    for i, name in enumerate(ui_names):
        path = "/" if i == 0 else f"/{entities[i].lower()}s"
        lines.append(f"Rt {path} {name}")
    for name in ui_names:
        prop = name.replace("List", "").lower() + "s"
        lines.append(f"U {name} {prop}")
        lines.append(f"T {prop}:A[{entities[ui_names.index(name) % len(entities)]}]")
    return "\n".join(lines)


def gen_auth():
    return f"A {random.choice(AUTH_KINDS)} {random.choice(AUTH_HEADERS)}"


def gen_cron(labels: list):
    if not labels or random.random() < 0.6:
        return ""
    lbl = random.choice(labels)
    expr = " ".join(["*/15", "*", "*", "*", "*"])
    return f"Cr {lbl} {expr}"


def gen_cache():
    if random.random() < 0.5:
        return ""
    return 'C cart sessionId 3600'


def gen_full_stack(n_entities: int = 2, with_auth: bool = False, with_cron: bool = False):
    entities = random.sample(ENTITY_NAMES, min(n_entities, len(ENTITY_NAMES)))
    lines = [
        gen_s_services(True),
        *[gen_d_type_for_entity(e) for e in entities],
        gen_e_and_labels(entities, len(entities)),
        gen_ui_and_routes(entities, len(entities)),
    ]
    if with_auth:
        lines.append(gen_auth())
    if with_cron:
        lines.append(gen_cron([str(i + 1) for i in range(len(entities))]))
    c = gen_cache()
    if c:
        lines.append(c)
    return "\n".join(lines)


def gen_api_only(n_entities: int = 2, with_auth: bool = False):
    entities = random.sample(ENTITY_NAMES, min(n_entities, len(ENTITY_NAMES)))
    lines = [
        "S core web /api",
        *[gen_d_type_for_entity(e) for e in entities],
        gen_e_and_labels(entities, len(entities)),
    ]
    if with_auth:
        lines.append(gen_auth())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=10000, help="Target number of valid programs")
    ap.add_argument("--out", default="data/synthetic", help="Output directory")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    os.makedirs(args.out, exist_ok=True)
    compiler = AICodeCompiler()
    valid = 0
    attempts = 0
    max_attempts = args.count * 3

    while valid < args.count and attempts < max_attempts:
        attempts += 1
        template = random.choice(["full_stack", "full_stack", "api_only"])
        n_ent = random.randint(1, 3)
        with_auth = random.random() < 0.3
        with_cron = random.random() < 0.2 if template == "full_stack" else False

        if template == "full_stack":
            code = gen_full_stack(n_entities=n_ent, with_auth=with_auth, with_cron=with_cron)
        else:
            code = gen_api_only(n_entities=n_ent, with_auth=with_auth)

        try:
            c = AICodeCompiler()
            ir = c.compile(code)
            if ir.get("services") or ir.get("types") or ir.get("labels"):
                fname = os.path.join(args.out, f"ainl_{valid:06d}.lang")
                with open(fname, "w") as f:
                    f.write(code)
                valid += 1
                if valid % 1000 == 0:
                    print(f"Generated {valid}/{args.count} valid programs")
        except Exception:
            pass

    print(f"Done. Wrote {valid} valid programs to {args.out}")
    return 0 if valid >= args.count else 1


if __name__ == "__main__":
    sys.exit(main())
