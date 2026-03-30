# Testing AINL Graphs

How to write unit tests, integration tests, and CI/CD pipelines for AINL programs.

---

## 🧪 Why Test AINL Graphs?

Even with compile-time validation, runtime can bring surprises:

- Adapter failures (API down, auth errors)
- LLM output format changes (despite prompts)
- Data format mismatches from external systems
- Performance regressions (latency, token cost)

Testing ensures your graphs behave correctly under various conditions.

---

## 🛠️ Test Types

| Type | Scope | Tooling |
|------|-------|---------|
| **Unit** | Single node in isolation | ainl test --unit |
| **Integration** | Whole graph with mocked adapters | ainl test --integration |
| **Property** | Graph invariants (always terminates, no cycles) | ainl validate --strict |
| **Performance** | Latency, token usage budgets | ainl benchmark, ainl run --trace-jsonl |
| **Contract** | Graph output matches schema for all valid inputs | JSON Schema validation |

---

## 📁 Test Project Structure

```
my-ainl-project/
├── graphs/
│   ├── monitor.ainl
│   └── alert.ainl
├── tests/
│   ├── unit/
│   │   └── test_classify_node.py
│   ├── integration/
│   │   ├── test_monitor_graph.py
│   │   └── fixtures/
│   │       └── sample_log.json
│   └── conftest.py  # shared fixtures
├── ainl.yaml  # config for tests (mock adapters)
├── pyproject.toml
└── README.md
```

---

## 🧪 Unit Testing Nodes

Mock adapters to test node logic in isolation.

Example: Test that `classify` node correctly parses LLM response.

```python
# tests/unit/test_classify_node.py
import pytest
from ainl import Node, LLMNode
from ainl.testing import MockAdapter

def test_classify_node_parses_critical():
    """Classification returns CRITICAL for severity keywords."""
    # Arrange
    mock = MockAdapter()
    mock.set_response("classify-error", "CRITICAL")
    
    node = LLMNode(
        id="classify",
        adapter="mock",
        model="mock-model",
        prompt="Classify: {{input.message}}"
    )
    node.adapter = mock
    
    # Act
    result = node.run({
        "input": {
            "message": "Database timeout after 30s",
            "level": "error"
        }
    })
    
    # Assert
    assert result == "CRITICAL"
```

**Run unit tests**:

```bash
ainl test --unit tests/
```

---

## 🔗 Integration Testing Graphs

Test entire graph with sample inputs and mocked adapters.

```python
# tests/integration/test_monitor_graph.py
import json
import pytest
from ainl import Graph
from ainl.testing import MockAdapter

@pytest.fixture
def mock_adapters():
    # Configure mock responses for all LLM nodes
    mocks = {
        "classify": MockAdapter(response="CRITICAL"),
        "alert": MockAdapter(response="🚨 Database timeout detected")
    }
    return mocks

def test_monitor_critical_path(mock_adapters):
    """Critical error should trigger Slack alert."""
    # Load graph
    graph = Graph.from_file("graphs/monitor.ainl")
    
    # Inject mocks
    for node_id, adapter in mock_adapters.items():
        graph.get_node(node_id).adapter = adapter
    
    # Run with sample input
    with open("tests/fixtures/sample_log.json") as f:
        input_data = json.load(f)
    
    output = graph.run(input_data)
    
    # Assert output
    assert output["severity"] == "CRITICAL"
    assert output["action_taken"] == "send_slack"
    
    # Verify Slack node was called (we can add call count to MockAdapter)
    slack_node = graph.get_node("send_slack")
    assert slack_node.called is True
```

**Fixtures** store sample inputs/outputs:

```json
// tests/fixtures/sample_log.json
{
  "timestamp": "2025-03-30T14:22:15Z",
  "level": "error",
  "message": "Database connection timeout",
  "service": "payment-processor"
}
```

---

## 🎯 Property-Based Testing

Test invariants across many random inputs using Hypothesis.

```python
# tests/property/test_graph_invariants.py
from hypothesis import given, strategies as st
from ainl import Graph

graph = Graph.from_file("graphs/monitor.ainl")

@given(
    level=st.sampled_from(["info", "warning", "error", "critical"]),
    service=st.text(min_size=1, max_size=50),
    message=st.text(min_size=1, max_size=200)
)
def test_graph_never_crashes(level, service, message):
    """Graph should not raise exceptions for any valid input."""
    input_data = {
        "timestamp": "2025-03-30T14:22:15Z",
        "level": level,
        "message": message,
        "service": service
    }
    
    # Graph should complete without error
    output = graph.run(input_data, mock_adapters=True)
    
    # Output should always have severity and action_taken
    assert "severity" in output
    assert "action_taken" in output
    assert output["severity"] in ["CRITICAL", "WARNING", "INFO"]
```

Run with:

```bash
pytest tests/property/ -v
```

---

## 📊 Performance Regression Testing

Ensure graphs don't get slower or more expensive over time.

```python
# tests/performance/test_monitor_performance.py
import time
from ainl import Graph
from ainl.testing import MockAdapter

def test_monitor_performance_budget():
    """Monitor graph should complete within budget."""
    graph = Graph.from_file("graphs/monitor.ainl")
    
    # Mock all external calls for consistent timing
    for node in graph.nodes:
        if node.type in ["llm", "http"]:
            node.adapter = MockAdapter(latency_ms=100)
    
    input_data = load_test_input()
    
    start = time.time()
    output = graph.run(input_data)
    elapsed = time.time() - start
    
    # Assertions
    assert elapsed < 2.0, f"Graph took {elapsed}s, budget 2s"
    assert output["severity"] is not None
```

Track token usage from trace JSONL and assert within budget.

---

## 🔁 CI/CD Integration

Add to GitHub Actions:

```yaml
name: AINL CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install AINL
        run: pip install ainl ainl-adapter-mock pytest
      - name: Validate graphs
        run: |
          ainl validate --strict graphs/*.ainl
      - name: Unit tests
        run: |
          ainl test --unit tests/unit/
      - name: Integration tests
        run: |
          ainl test --integration tests/integration/
      - name: Performance baseline
        run: |
          ainl benchmark graphs/monitor.ainl --output benchmarks.json
          python scripts/check_regression.py benchmarks.json
```

Benchmark script checks that runtime hasn't increased >10% since last commit.

---

## 🧩 Mock Adapters

AINL includes a `MockAdapter` for testing:

```python
from ainl.testing import MockAdapter

# Return fixed response
mock = MockAdapter(response="CRITICAL")

# Simulate latency
mock = MockAdapter(latency_ms=500, response="OK")

# Simulate failure
mock = MockAdapter(error=RuntimeError("Service unavailable"))

# Expect specific prompt (fails if prompt doesn't match)
mock = MockAdapter(expected_prompt="Classify: {{input}}")
```

Use in tests to isolate graph logic from external dependencies.

---

## 📈 Test Coverage

AINL's `ainl test` reports coverage:

```
tests/
  unit/             100% nodes tested
  integration/      85% edge coverage (2/4 branches untested)
  
Overall: 92%
```

Improve coverage by:
- Testing all `switch` branches
- Testing error paths (adapter failures)
- Testing edge cases (empty inputs, null values)

---

## 🐛 Debugging Failed Tests

### Test hangs

Likely deadlock or infinite retry. Set adapter timeout:

```python
mock = MockAdapter(response="OK", timeout=1.0)  # seconds
```

### Assertion fails: node not called

Remember: `when` conditions skip nodes. Ensure test input triggers branch.

### Mock not used

Node may be using cached result. Clear cache with `graph.clear_cache()`.

---

## 📚 Example: Full Test Suite

```python
# tests/conftest.py
import pytest
from ainl import Graph
from ainl.testing import MockAdapter

@pytest.fixture
def monitor_graph():
    graph = Graph.from_file("graphs/monitor.ainl")
    
    # Configure mocks
    for node in graph.nodes:
        if node.type == "llm":
            node.adapter = MockAdapter(response="CRITICAL")
        elif node.type == "http":
            node.adapter = MockAdapter(success_code=200)
    
    return graph

# tests/integration/test_monitor.py
def test_critical_triggers_slack(monitor_graph):
    input_data = {"log": {"level": "error", "msg": "DB down"}}
    output = monitor_graph.run(input_data)
    assert output["action"] == "slack_alert"
    assert monitor_graph.get_node("send_slack").called

def test_info_skips_alert(monitor_graph):
    input_data = {"log": {"level": "info", "msg": "Started"}}
    output = monitor_graph.run(input_data)
    assert output["action"] == "log_file"
    assert not monitor_graph.get_node("send_slack").called
```

---

## 🎯 Best Practices

1. **Mock all external calls** – never hit real APIs in unit/integration tests
2. **Test all branches** – cover every `switch` case
3. **Test error scenarios** – adapter failures, malformed LLM output
4. **Keep fixtures small** – one JSON per test scenario
5. **Use property testing** for random input resilience
6. **Benchmark in CI** – catch performance regressions early

---

## 🔗 Related

- [Monitoring Guide](monitoring.md) – Production observability
- [Graphs & IR](graphs-and-ir.md) – Understand IR for debugging
- [CLI Reference](../../reference/cli-reference.md) – `ainl test` options

---

**Write tests, ship with confidence!** →