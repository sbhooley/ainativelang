# ArmaraOS-compatible A2A bridge (Hermes `~/.hermes`)

This is a **small stdlib-only HTTP server** that speaks the same A2A surface ArmaraOS expects:

- `GET /.well-known/agent.json`
- `POST /a2a` with JSON-RPC `tasks/send` and `tasks/get`
- `POST /message:send` with `Content-Type: application/a2a+json` (Linux Foundation HTTP binding)

It does **not** embed Hermes itself. Point **`HERMES_AINL_BRIDGE_CMD`** at a program that reads the user message on **stdin** and prints the reply on **stdout** (for example a wrapper around `hermes`, an MCP tool, or a socket to your gateway).

## Install into `~/.hermes`

From the AINL repo:

```bash
bash skills/hermes/install_armaraos_a2a_bridge.sh
```

This copies this directory to `~/.hermes/skills/ainl/armaraos-a2a-bridge/` and writes `~/.hermes/a2a.json` with `base_url` pointing at the default listen address.

## Run

```bash
export HERMES_AINL_BRIDGE_CMD="python3 /path/to/your_hermes_stdin_stdout_proxy.py"   # optional
python3 ~/.hermes/skills/ainl/armaraos-a2a-bridge/armaraos_a2a_bridge.py
```

Or use the generated launcher:

```bash
~/.hermes/skills/ainl/armaraos-a2a-bridge/run-bridge.sh
```

Environment:

| Variable | Default | Meaning |
|----------|---------|---------|
| `HERMES_AINL_BRIDGE_HOST` | `127.0.0.1` | Bind address |
| `HERMES_AINL_BRIDGE_PORT` | `18765` | Listen port (match `a2a.json`) |
| `HERMES_AINL_BRIDGE_CMD` | *(unset)* | Delegate: stdin = user message, stdout = reply |
| `HERMES_BIN` | `hermes` on `PATH` | Used by bundled `hermes_chat_delegate.py` |
| `HERMES_AINL_BRIDGE_TIMEOUT_S` | `300` | Delegate wall-clock timeout |
| `HERMES_AINL_BRIDGE_QUIET` | `0` | Set `1` to silence HTTP access logs |

Bundled delegate (reads stdin → `hermes chat -q … -Q --source tool --yolo` → cleaned stdout):

```bash
export HERMES_AINL_BRIDGE_CMD="python3 $(dirname "$0")/hermes_chat_delegate.py"
export HERMES_BIN="/path/to/hermes"   # optional
```

`--yolo` avoids approval prompts in headless runs; remove it in the delegate script copy if you want strict approvals.

## Verify (smoke test)

From the AINL repo root (so `runtime` imports resolve):

```bash
bash skills/hermes/armaraos-a2a-bridge/smoke_test_a2a_bridge.sh
```

## ArmaraOS side

Use built-in tools **`hermes_a2a_status`**, **`a2a_discover_hermes`**, **`a2a_send_hermes`** (or AINL `a2a.discover_hermes` / `a2a.send_hermes`). `send_binding` **`auto`** in `a2a.json` is correct for this bridge.
