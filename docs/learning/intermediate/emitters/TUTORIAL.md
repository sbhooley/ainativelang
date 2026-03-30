# Emitters Tutorial: Deploy to LangGraph and Temporal

**Time**: 60 minutes  
**Prerequisites**: Complete Basics + Adapters tutorial

---

## What We'll Build

Take an existing AINL graph and **emit** it to two different platforms:
1. **LangGraph**: As a Python module
2. **Temporal**: As a workflow definition

You'll see how one AINL graph becomes deployable to multiple execution engines.

---

## Step 1: Our Starting Graph

Let's use a simple monitoring agent from Basics:

```ainl
# basics/02-first-agent.ainl (modified)
graph MonitoringAgent {
  input: Config = { threshold: number }
  
  node check: HTTP("health") {
    url: "https://api.example.com/health"
  }
  
  node evaluate: Transform("eval") {
    healthy: check.status == 200 and check.response.uptime > input.threshold
  }
  
  output: { timestamp: now(), healthy: evaluate.healthy }
}
```

Save as `monitoring.ainl` in current dir.

---

## Step 2: Emit to LangGraph

LangGraph expects a Python class with state and nodes.

### Generate LangGraph Code

```bash
ainl emit monitoring.ainl   --target langgraph   --output monitoring_langgraph.py
```

**Result** (`monitoring_langgraph.py`):

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class MonitoringState(TypedDict):
    threshold: float
    check_status: int
    check_response: dict
    healthy: bool
    timestamp: str

def check_node(state: MonitoringState):
    # Generated from your HTTP node
    import requests
    resp = requests.get("https://api.example.com/health")
    state["check_status"] = resp.status_code
    state["check_response"] = resp.json()
    return state

def evaluate_node(state: MonitoringState):
    healthy = (state["check_status"] == 200 and 
               state["check_response"]["uptime"] > state["threshold"])
    state["healthy"] = healthy
    state["timestamp"] = datetime.now().isoformat()
    return state

# Build graph
workflow = StateGraph(MonitoringState)
workflow.add_node("check", check_node)
workflow.add_node("evaluate", evaluate_node)
workflow.set_entry_point("check")
workflow.add_edge("check", "evaluate")
workflow.add_edge("evaluate", END)

monitoring_agent = workflow.compile()
```

---

### Run the LangGraph Version

```python
# test_langgraph.py
from monitoring_langgraph import monitoring_agent

result = monitoring_agent.invoke({
    "threshold": 99.5
})
print(result)
```

**Notice**: The generated code is clean, typed, and includes all your logic. You can now:
- Add memory (checkpointing)
- Add human-in-the-loop interrupts
- Deploy to LangGraph Cloud

---

## Step 3: Emit to Temporal

Temporal expects a workflow definition with activities.

### Generate Temporal Code

```bash
ainl emit monitoring.ainl   --target temporal   --output monitoring_temporal.py
```

**Result** (`monitoring_temporal.py`):

```python
from temporalio import workflow, activity
from typing import Dict, Any

@activity.defn
async def http_activity(url: str) -> Dict[str, Any]:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return {
                "status": resp.status,
                "response": await resp.json()
            }

@workflow.defn
class MonitoringWorkflow:
    @workflow.run
    async def run(self, threshold: float) -> Dict[str, Any]:
        # Node: check
        check_result = await workflow.execute_activity(
            http_activity,
            "https://api.example.com/health",
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Node: evaluate
        healthy = (check_result["status"] == 200 and 
                   check_result["response"]["uptime"] > threshold)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "healthy": healthy
        }
```

---

### Run the Temporal Version

```python
# Run a local Temporal worker
temporal worker start --namespace default --task-queue monitoring-queue

# In another terminal, start the workflow
from temporalio import Client
client = await Client.connect("localhost:7233")
result = await client.execute_workflow(
    MonitoringWorkflow.run,
    threshold=99.5,
    id="monitoring-run-1",
    task_queue="monitoring-queue"
)
print(result)
```

---

## Step 4: Compare the Outputs

| Platform | Generated Code | Execution Model | Best For |
|----------|----------------|-----------------|----------|
| **AINL (native)** | `monitoring.ainl` | Interpreted, hot-reload | Development, prototyping |
| **LangGraph** | `monitoring_langgraph.py` | Stateful, checkpointing | Chatbots, agents with memory |
| **Temporal** | `monitoring_temporal.py` | Durable, scheduled | Cron jobs, long-running workflows |

**Same graph, three deployment options**. Choose based on your needs.

---

## Step 5: Understanding Emitter Differences

### LangGraph Emitter

- **Converts**: AINL → Python class using `langgraph.graph.StateGraph`
- **Preserves**: Node ordering, conditional routing (`switch`), state typing
- **Adds**: Memory integration, human interrupts possible via LangGraph Studio
- **Limitation**: `try/catch` converted to `try/except` but may need manual adjustment

### Temporal Emitter

- **Converts**: AINL → Temporal workflow + activities
- **Preserves**: Linear flow only (no `switch` yet – use `if` inside nodes)
- **Adds**: Durable execution, retries, cron schedules
- **Limitation**: Complex graphs with many branches may need manual refactoring

### OpenCrawl Emitter (bonus)

```bash
ainl emit monitoring.ainl --target opencrawl --output crawl_workflow.py
# Creates a Scrapy spider for web scraping workflows
```

---

## Step 6: Customizing Emitted Code

Generated code is **starting point**, not final. Typical post-emit customizations:

### LangGraph: Add Tool Calling

```python
# After emitting, edit:
from langchain.tools import Tool

workflow.add_node("call_tool", tool_node)
# Add your own tool definitions
```

### Temporal: Add Retries

```python
@activity.defn
async def http_activity(url: str) -> Dict[str, Any]:
    # Add retry logic or use Temporal's retry policy
    pass

# In workflow call:
await workflow.execute_activity(
    http_activity,
    retry_policy=RetryPolicy(maximum_attempts=3)
)
```

---

## Step 7: Build Workflow

1. **Develop** in native AINL (fast iteration)
2. **Validate**: `ainl validate monitoring.ainl`
3. **Emit** to target platform when ready
4. **Customize** generated code for platform-specific features
5. **Deploy** to that platform

This separation of concerns: AINL for logic, platform for execution guarantees.

---

## ✅ Checklist

- [x] Start with a working AINL graph
- [x] Emit to LangGraph (`ainl emit --target langgraph`)
- [x] Run the generated LangGraph code
- [x] Emit to Temporal (`ainl emit --target temporal`)
- [x] Run the generated Temporal workflow (with worker)
- [x] Compare the two outputs and understand tradeoffs
- [x] Customize one emitted file (e.g., add a print statement)

---

## Next Steps

- Emit a more complex graph with `switch` statements
- Try the `temporal_cron` emitter for scheduled jobs
- Read [emitters/README.md](../README.md) for all supported targets
- Explore [patterns/cross-graph.md](../patterns/cross-graph orchestration) for multi-graph emits

---

**One AINL graph, infinite deployment targets.** Choose the execution engine that fits your operational needs.
