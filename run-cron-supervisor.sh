#!/bin/bash
# AINL Cron Supervisor wrapper
# Executes the compiled AINL supervisor graph every 15 minutes

set -e

WORKSPACE="/Users/clawdbot/.openclaw/workspace/AI_Native_Lang"
VENV="${WORKSPACE}/.venv-ainl"
LOGDIR="${WORKSPACE}/logs"

# Ensure log dir exists
mkdir -p "${LOGDIR}"

# Activate venv
source "${VENV}/bin/activate" || {
  echo "ERROR: Could not activate AINL venv at ${VENV}"
  exit 1
}

# Compile and execute the supervisor module
cd "${WORKSPACE}"

python3 <<'EOF'
import sys
import os
from datetime import datetime

sys.path.insert(0, '/Users/clawdbot/.openclaw/workspace/AI_Native_Lang')

try:
    from compiler_v2 import AICodeCompiler
    from runtime.compat import ExecutionEngine
    
    # Load and compile the supervisor AINL module
    with open('modules/openclaw/cron_supervisor.ainl', 'r') as f:
        ainl_code = f.read()
    
    compiler = AICodeCompiler()
    compiled = compiler.compile(ainl_code, emit_graph=True)
    
    # Execute the compiled graph
    engine = ExecutionEngine(compiled.get('graph', {}))
    result = engine.execute()
    
    print(f"[CRON SUPERVISOR] {datetime.now().isoformat()}")
    print(f"Status: OK")
    print(f"Graph executed successfully")
    
except Exception as e:
    print(f"[CRON SUPERVISOR] ERROR: {str(e)}", file=sys.stderr)
    sys.exit(1)
EOF
