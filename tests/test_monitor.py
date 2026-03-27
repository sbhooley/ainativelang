from intelligence.monitor.collector import MetricsCollector
from intelligence.monitor.cost_tracker import CostTracker
from intelligence.monitor.health import HealthStatus
import os

def test_collector_snapshot():
    col = MetricsCollector()
    col.increment("test", 5)
    snap = col.snapshot()
    assert snap.get("test") == 5

def test_cost_tracker_schema():
    ct = CostTracker(":memory:")  # in-memory for test; adjust implementation if needed
    ct.add_cost("run1", "openrouter", "gpt-4o-mini", 100, 50, 0.001)
    total = ct.get_month_total()
    assert total > 0

def test_health_ready_checks():
    hs = HealthStatus()
    result = hs.ready()
    assert "status" in result
    assert "checks" in result
