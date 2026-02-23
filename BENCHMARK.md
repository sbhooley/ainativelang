# Token Benchmark: .lang vs Python/TS Equivalents

Approximate token count (word-split heuristic) for each test vs. combined emitted code (React + FastAPI + Prisma + MT5 + Scraper + Cron stubs).

| Test | .lang (approx tokens) | Python/TS equiv (approx tokens) | Ratio |
|------|----------------------|-----------------------------------|-------|
| test_ecom_dashboard | 88 | 278 | 3.2x |
| test_mt5_trader | 47 | 419 | 8.9x |
| test_scraper_cron | 63 | 504 | 8.0x |

**Conclusion**: The .lang source is 3–9× more compact than the combined emitted code, depending on how much of the stack (React, API, Prisma, MT5, Scraper, Cron) is emitted for that test.

Run: `python3 benchmark_tokens.py`
