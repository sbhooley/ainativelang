# Adapters (pluggable backends)

The emitted server runs label steps (R, J, and control-flow; P is declaration-only—payment in labels uses `R pay.*`) via **adapters**. By default it uses **mock** adapters. Replace them with real backends for production.

## Interface

- **DBAdapter** – `find(entity, fields)`, `get(entity, id)`, `create`, `delete`  
  - Use Prisma, SQLAlchemy, or any ORM.
- **APIAdapter** – `get(path)`, `post(path, body)`  
  - Use `httpx` or `requests` for outbound HTTP.
- **PayAdapter** – `create_intent(name, amount, currency, desc)`  
  - Use Stripe (or similar) SDK.
- **ScrapeAdapter** – `scrape(name, url, selectors)`  
  - Use your scraper implementation.

## Usage in emitted server

The server loads `ir.json` and does:

```python
from adapters import mock_registry  # or your registry
_registry = mock_registry(_ir.get("types"))
_engine = ExecutionEngine(_ir, _registry)
```

To plug in real backends, create your own registry and pass it when building the app (or patch the emitted server to use a registry from env/config):

```python
from adapters.base import AdapterRegistry
from my_adapters import MyPrismaDB, MyStripePay
_registry = AdapterRegistry(db=MyPrismaDB(), pay=MyStripePay())
```
