# AINL × OpenFang Integration

This directory contains documentation for using AINL (AI Native Language) with OpenFang Agent Operating System.

## Quick Start

```bash
# 1. Install AINL and integrate with OpenFang
ainl install openfang

# 2. Create or emit an AINL hand
ainl emit --target openfang -o my_hand/ my_workflow.ainl

# 3. Run the hand with OpenFang
openfang hand run my_hand --input '{"data": "test"}'

# 4. Monitor status
ainl status --host openfang
```

## What is OpenFang?

OpenFang is an open-source Agent Operating System built in Rust. It features:
- WASM sandboxing for secure hand execution
- 16 security systems including Merkle trails and taint tracking
- Native MCP (Model Context Protocol) support
- Tauri sidecar support for desktop integrations
- HAND.toml manifests for declarative agent definitions

## How AINL Integrates

AINL provides:
- High-level DSL for defining AI workflows
- Compilation to optimized IR
- MCP server for OpenFang to call AINL tools
- Sidecar bridge for bidirectional data flow
- Token tracking and cost metering
- Validation dashboard and marketplace

## Next Steps

- See [INSTALL.md](INSTALL.md) for detailed setup
- See [CONFIG.md](CONFIG.md) for configuration reference
- Visit [OpenFang docs](https://github.com/RightNow-AI/openfang) for OpenFang specifics
