"""Compile .lang tests and write all emits to tests/emits/."""
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler_v2 import AICodeCompiler

TESTS_DIR = os.path.join(os.path.dirname(__file__), "tests")
EMITS_DIR = os.path.join(TESTS_DIR, "emits")
SERVER_STATIC_README = """# Static files (pages & apps)

Drop any pages or apps here. They are served at /.

- index.html, app.jsx = default dashboard (from .lang)
- Add subdirs or files: other-app/, admin.html, etc.
  They are served at /other-app/, /admin.html, ...
"""

def main():
    os.makedirs(EMITS_DIR, exist_ok=True)
    compiler = AICodeCompiler()
    for fname in sorted(os.listdir(TESTS_DIR)):
        if not fname.endswith(".lang"):
            continue
        path = os.path.join(TESTS_DIR, fname)
        base = fname[:-5]
        with open(path, "r") as f:
            code = f.read()
        ir = compiler.compile(code)
        # Write emits
        for ext, emit_fn in [
            ("react.tsx", compiler.emit_react),
            ("prisma.prisma", compiler.emit_prisma_schema),
            ("api.py", compiler.emit_python_api),
            ("mt5.mq5", compiler.emit_mt5),
            ("scraper.py", compiler.emit_python_scraper),
            ("cron.py", compiler.emit_cron_stub),
        ]:
            out_path = os.path.join(EMITS_DIR, f"{base}.{ext}")
            with open(out_path, "w") as f:
                f.write(emit_fn(ir))
        if ir.get("rag") and any(ir.get("rag", {}).get(k) for k in ("sources", "chunking", "embeddings", "stores", "indexes", "retrievers", "augment", "generate", "pipelines")):
            out_path = os.path.join(EMITS_DIR, f"{base}.rag.py")
            with open(out_path, "w") as f:
                f.write(compiler.emit_rag_pipeline(ir))
        # If .lang defines both API (core) and frontend (fe), emit unified server + static.
        # Emit server for the main ecom dashboard app so one server serves API + static.
        has_core = "core" in ir.get("services", {})
        has_fe = "fe" in ir.get("services", {})
        if has_core and has_fe and base == "ecom_dashboard":
            server_dir = os.path.join(EMITS_DIR, "server")
            static_dir = os.path.join(server_dir, "static")
            os.makedirs(static_dir, exist_ok=True)
            with open(os.path.join(server_dir, "server.py"), "w") as f:
                f.write(compiler.emit_server(ir))
            with open(os.path.join(server_dir, "ir.json"), "w") as f:
                f.write(compiler.emit_ir_json(ir))
            with open(os.path.join(server_dir, "requirements.txt"), "w") as f:
                f.write("fastapi\nuvicorn[standard]\n")
            # Use custom ecommerce storefront (product grid, cart, checkout, styled nav)
            _proj_root = os.path.dirname(os.path.abspath(__file__))
            _storefront = os.path.join(_proj_root, "storefront")
            _storefront_jsx = os.path.join(_storefront, "app.jsx")
            _storefront_html = os.path.join(_storefront, "index.html")
            if os.path.isfile(_storefront_jsx) and os.path.isfile(_storefront_html):
                import shutil as _shutil
                _shutil.copy2(_storefront_jsx, os.path.join(static_dir, "app.jsx"))
                _shutil.copy2(_storefront_html, os.path.join(static_dir, "index.html"))
                print("  -> static: storefront (product grid, cart, checkout) from storefront/")
            else:
                with open(os.path.join(static_dir, "app.jsx"), "w") as f:
                    f.write(compiler.emit_react_browser(ir))
                with open(os.path.join(static_dir, "index.html"), "w") as f:
                    f.write(_index_html())
                print("  -> static: compiler output (storefront/ not found at %s)" % _storefront)
            with open(os.path.join(static_dir, "README.md"), "w") as f:
                f.write(SERVER_STATIC_README)
            with open(os.path.join(server_dir, "openapi.json"), "w") as f:
                f.write(compiler.emit_openapi(ir))
            with open(os.path.join(server_dir, "runbooks.md"), "w") as f:
                f.write(compiler.emit_runbooks(ir))
            with open(os.path.join(server_dir, "Dockerfile"), "w") as f:
                f.write(compiler.emit_dockerfile(ir))
            with open(os.path.join(server_dir, "docker-compose.yml"), "w") as f:
                f.write(compiler.emit_docker_compose(ir))
            with open(os.path.join(server_dir, "k8s.yaml"), "w") as f:
                f.write(compiler.emit_k8s(ir, name="ainl-api", replicas=1, with_ingress=False))
            with open(os.path.join(server_dir, ".env.example"), "w") as f:
                f.write(compiler.emit_env_example(ir))
            migrations_dir = os.path.join(server_dir, "migrations")
            os.makedirs(migrations_dir, exist_ok=True)
            with open(os.path.join(migrations_dir, "001_initial.sql"), "w") as f:
                f.write(compiler.emit_sql_migrations(ir, dialect="postgres"))
            next_routes = compiler.emit_next_api_routes(ir)
            next_dir = os.path.join(server_dir, "next")
            for key, content in next_routes.items():
                if key.startswith("_"):
                    continue
                out_path = os.path.join(next_dir, key)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w") as f:
                    f.write(content)
            with open(os.path.join(static_dir, "App.vue"), "w") as f:
                f.write(compiler.emit_vue_browser(ir))
            with open(os.path.join(static_dir, "App.svelte"), "w") as f:
                f.write(compiler.emit_svelte_browser(ir))
            # Copy runtime + adapters so server dir is self-contained for Docker
            import shutil
            _root = os.path.dirname(os.path.abspath(__file__))
            for _f in ["runtime.py"]:
                _src = os.path.join(_root, _f)
                if os.path.isfile(_src):
                    shutil.copy2(_src, os.path.join(server_dir, _f))
            _ad = os.path.join(_root, "adapters")
            _ad_dest = os.path.join(server_dir, "adapters")
            if os.path.isdir(_ad):
                if os.path.isdir(_ad_dest):
                    shutil.rmtree(_ad_dest)
                shutil.copytree(_ad, _ad_dest)
            print(f"Compiled {fname} -> emits/{base}.* + server/ (API + static + OpenAPI + Docker)")
        if base == "ecom_dashboard":
            dashboard_dir = os.path.join(EMITS_DIR, "dashboard")
            os.makedirs(dashboard_dir, exist_ok=True)
            with open(os.path.join(dashboard_dir, "app.jsx"), "w") as f:
                f.write(compiler.emit_react_browser(ir))
            if not (has_core and has_fe):
                print(f"Compiled {fname} -> emits/{base}.* + dashboard/app.jsx")
        if not (has_core and has_fe) and base != "test_ecom_dashboard":
            print(f"Compiled {fname} -> emits/{base}.*")
    print("Done.")


def _index_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dashboard</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #f5f5f5; }
    .dashboard { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    h1 { margin-top: 0; color: #333; }
    pre { background: #f8f8f8; padding: 1rem; border-radius: 4px; overflow: auto; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script crossorigin src="https://unpkg.com/react@17/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@17/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script type="text/babel" src="/app.jsx?v=2"></script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
