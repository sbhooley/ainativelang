"""
Benchmark: approximate token counts for .lang vs Python/TS equivalents.
Uses word-split as a rough token proxy (no tiktoken dependency).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler_v2 import AICodeCompiler

TESTS_DIR = os.path.join(os.path.dirname(__file__), "tests")
EMITS_DIR = os.path.join(TESTS_DIR, "emits")

def approx_tokens(text: str) -> int:
    """Approximate token count: split on whitespace + punctuation."""
    import re
    tokens = re.findall(r"\S+", text)
    return len(tokens)

def main():
    compiler = AICodeCompiler()
    rows = []
    for fname in sorted(os.listdir(TESTS_DIR)):
        if not fname.endswith(".lang"):
            continue
        path = os.path.join(TESTS_DIR, fname)
        base = fname[:-5]
        with open(path, "r") as f:
            lang_code = f.read()
        lang_tok = approx_tokens(lang_code)
        ir = compiler.compile(lang_code)
        react = compiler.emit_react(ir)
        api = compiler.emit_python_api(ir)
        prisma = compiler.emit_prisma_schema(ir)
        mt5 = compiler.emit_mt5(ir)
        scraper = compiler.emit_python_scraper(ir)
        cron = compiler.emit_cron_stub(ir)
        equiv = react + "\n" + api + "\n" + prisma + "\n" + mt5 + "\n" + scraper + "\n" + cron
        equiv_tok = approx_tokens(equiv)
        ratio = equiv_tok / lang_tok if lang_tok else 0
        rows.append((base, lang_tok, equiv_tok, ratio))
    # Table
    print("| Test | .lang (approx tokens) | Python/TS equiv (approx tokens) | Ratio |")
    print("|------|----------------------|-----------------------------------|-------|")
    for base, lt, et, r in rows:
        print(f"| {base} | {lt} | {et} | {r:.1f}x |")
    return rows

if __name__ == "__main__":
    main()
