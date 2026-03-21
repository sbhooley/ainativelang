# Basic scraper (handwritten baseline)

## Original AINL

Ports [`examples/scraper/basic_scraper.ainl`](../../../examples/scraper/basic_scraper.ainl):

```text
L_scrape:
  R http.GET "https://example.com/products" -> resp
  R db.C Product * -> stored
  J stored
```

The `Sc` line selects `.product-title` and `.product-price`; the Python baseline parses those classes from HTML and appends rows to an in-memory **Product** table (stand-in for `db.C`).

## Implementations

| File | Role |
|------|------|
| `pure_async_python.py` | `run_basic_scrape()`: GET → `parse_products` → `ProductStore.commit_products`. |
| `langgraph_version.py` | Three nodes: `fetch` → `parse` → `store` (same data flow). |

## Equivalence

With the same `mock_html` and `ProductStore`, pure and LangGraph return identical `ScraperResult`. Verify:

```bash
cd benchmarks/handwritten_baselines/basic_scraper
python langgraph_version.py
```

## Key differences vs AINL

- **HTTP + DB**: Real runtime uses `http` and `db` adapters; here **aiohttp** + a list-backed store.
- **Cron**: The example’s hourly `Cr` schedule is omitted; only the **body** of `L_scrape` is modeled.
- **Parsing**: Regex on class names approximates selector behavior; fragile HTML may differ from a full DOM parser.

## Assumptions

- `db.C Product *` means “commit parsed product rows and expose the full stored set as `stored`.”
- Offline benchmarks should pass **`mock_html`** instead of hitting `example.com`.

## Dependencies

- `aiohttp` for network fetches (optional if `mock_html` is set).
- `langgraph` for `langgraph_version.py`.
