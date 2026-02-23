# Install (Cross-OS)

## Requirements

- Python 3.9+
- pip

## Linux / macOS

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
ainl-validate examples/blog.lang --emit ir
```

## Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
.\.venv\Scripts\Activate.ps1
ainl-validate examples/blog.lang --emit ir
```

## Manual install

```bash
python -m pip install -e ".[dev,web]"
```

## CLI tools installed

- `ainl-validate` - compile/validate/emit from `.lang`
- `ainl-validator-web` - run FastAPI validator UI
- `ainl-generate-dataset` - synthetic dataset generator
- `ainl-compat-report` - IR compatibility report
- `ainl-tool-api` - structured tool API CLI
- `ainl-ollama-eval` - local Ollama eval harness
