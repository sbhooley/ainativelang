---
> ArmaraOS is an independent open-source project and is not affiliated with any entities using similar names (e.g., Amaros AI or others).
> It is a customized fork and extension of OpenFang by RightNow-AI (https://github.com/RightNow-AI/openfang), licensed under Apache-2.0 OR MIT.
> It includes and integrates AINativeLang (https://github.com/sbhooley/ainativelang) for deterministic AI workflows.
> Modifications Copyright (c) 2026 sbhooley. Original OpenFang and AINativeLang works retain their respective licenses.
---

# AINL × ArmaraOS Integration

This directory contains documentation for using AINL (AI Native Language) with ArmaraOS Agent Operating System.

## Quick Start

```bash
# 1. Install AINL and integrate with ArmaraOS
ainl install armaraos

# 2. Create or emit an AINL hand
ainl emit --target armaraos -o my_hand/ my_workflow.ainl

# 3. Run the hand with ArmaraOS
armaraos hand run my_hand --input '{"data": "test"}'

# 4. Monitor status
ainl status --host armaraos
```

## What is ArmaraOS?

ArmaraOS is an open-source Agent Operating System built in Rust. It features:
- WASM sandboxing for secure hand execution
- 16 security systems including Merkle trails and taint tracking
- Native MCP (Model Context Protocol) support
- Tauri sidecar support for desktop integrations
- HAND.toml manifests for declarative agent definitions

## How AINL Integrates

AINL provides:
- High-level DSL for defining AI workflows
- Compilation to optimized IR
- MCP server for ArmaraOS to call AINL tools
- Sidecar bridge for bidirectional data flow
- Token tracking and cost metering
- Validation dashboard and marketplace

## Next Steps

- See [INSTALL.md](INSTALL.md) for detailed setup
- See [CONFIG.md](CONFIG.md) for configuration reference
- **AINL graph memory inbox (Python write-back):** [graph-memory-sync.md](graph-memory-sync.md) — **`ARMARAOS_AGENT_ID`**, **`ainl_graph_memory_inbox.json`**
- Visit [ArmaraOS docs](https://github.com/RightNow-AI/armaraos) for ArmaraOS specifics
