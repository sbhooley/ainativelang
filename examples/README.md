# AINL Example Apps

Full-stack and API-only examples. Compile with:

```bash
python scripts/validate_ainl.py examples/blog.lang --emit ir
```

**Ecom dashboard (API + webserver + frontend):** The main e-commerce app is `tests/ecom_dashboard.lang`. Build and serve it with:

```bash
python run_tests_and_emit.py
python serve_dashboard.py
```

Then open http://127.0.0.1:8765/ for the dashboard and http://127.0.0.1:8765/api/ for the API (OpenAPI at `/api/openapi.json`).

| File | Description |
|------|-------------|
| **blog.lang** | Posts + comments, CRUD, cache |
| **ticketing.lang** | Events + tickets, auth (A), payment (P) |
| **internal_tool.lang** | Tasks + users, cron (Cr) |
| **api_only.lang** | Backend only: users + sessions |
| **ecom.lang** | E-commerce snippet (routes, P, cache) |
| **tests/ecom_dashboard.lang** | Full ecom dashboard: API + frontend, Products/Orders/Customers, checkout, cache (C) |

Grammar version: **1.0** (see docs/AINL_SPEC.md).
