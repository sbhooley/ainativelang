import json
import os
import tempfile

from adapters.agent import AgentAdapter
from runtime.adapters.base import AdapterError


def _with_agent_root(tmpdir: str):
  os.environ["AINL_AGENT_ROOT"] = tmpdir


def test_agent_send_task_appends_envelope_and_returns_reference():
  adapter = AgentAdapter()
  envelope = {
      "schema_version": "1.0",
      "task_id": "task-123",
      "requester_id": "planner.agent",
      "target_agent": "openclaw.monitor",
  }

  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    result = adapter.call("send_task", [envelope], context={})

    assert result == "task-123"

    # Tasks file should exist and contain one JSON line matching the envelope.
    abs_path = os.path.join(tmpdir, "tasks", "openclaw_agent_tasks.jsonl")
    assert os.path.isfile(abs_path)
    with open(abs_path, "r", encoding="utf-8") as f:
      lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["task_id"] == "task-123"
    assert stored["requester_id"] == "planner.agent"
    assert stored["target_agent"] == "openclaw.monitor"


def test_agent_send_task_rejects_nonescaping_paths():
  adapter = AgentAdapter()
  envelope = {"schema_version": "1.0", "task_id": "task-escape"}

  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    # Attempt to escape the sandbox root.
    rel_path = "../escape.jsonl"
    try:
      adapter.call("send_task", [envelope, rel_path], context={})
    except AdapterError as e:
      assert "AINL_AGENT_ROOT" in str(e)
    else:
      raise AssertionError("expected AdapterError for sandbox escape")


def test_agent_send_task_requires_object_envelope():
  adapter = AgentAdapter()
  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    try:
      adapter.call("send_task", ["not-a-dict"], context={})
    except AdapterError as e:
      assert "expects first argument to be a JSON object envelope" in str(e)
    else:
      raise AssertionError("expected AdapterError for non-object envelope")


def test_agent_read_result_reads_json_object_file():
  adapter = AgentAdapter()
  result_envelope = {
      "schema_version": "1.0",
      "task_id": "task-123",
      "agent_id": "openclaw.monitor",
      "status": "ok",
      "confidence": 0.9,
  }

  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    abs_path = os.path.join(tmpdir, "results", "task-123.json")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
      json.dump(result_envelope, f)

    loaded = adapter.call("read_result", ["task-123"], context={})

  assert loaded["task_id"] == "task-123"
  assert loaded["agent_id"] == "openclaw.monitor"
  assert loaded["status"] == "ok"
  assert loaded["confidence"] == 0.9


def test_agent_read_result_missing_file():
  adapter = AgentAdapter()
  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    try:
      adapter.call("read_result", ["missing"], context={})
    except AdapterError as e:
      assert "agent.read_result target does not exist" in str(e)
    else:
      raise AssertionError("expected AdapterError for missing result file")


def test_agent_read_result_invalid_json():
  adapter = AgentAdapter()
  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    abs_path = os.path.join(tmpdir, "results", "bad.json")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
      f.write("{not valid json")

    try:
      adapter.call("read_result", ["bad"], context={})
    except AdapterError as e:
      assert "agent.read_result failed to parse JSON" in str(e)
    else:
      raise AssertionError("expected AdapterError for invalid JSON")


def test_agent_read_result_non_object_summary():
  adapter = AgentAdapter()
  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    abs_path = os.path.join(tmpdir, "results", "list.json")
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
      json.dump([{"task_id": "task-1"}], f)

    try:
      adapter.call("read_result", ["list"], context={})
    except AdapterError as e:
      assert "agent.read_result expects JSON object result" in str(e)
    else:
      raise AssertionError("expected AdapterError for non-object result")


def test_agent_read_result_rejects_path_escape():
  adapter = AgentAdapter()
  with tempfile.TemporaryDirectory() as tmpdir:
    _with_agent_root(tmpdir)
    try:
      adapter.call("read_result", ["../escape"], context={})
    except AdapterError as e:
      assert "AINL_AGENT_ROOT" in str(e)
    else:
      raise AssertionError("expected AdapterError for sandbox escape in read_result")


def test_agent_root_must_not_be_filesystem_root():
  adapter = AgentAdapter()
  os.environ["AINL_AGENT_ROOT"] = "/"
  try:
    adapter.call("send_task", [{"task_id": "x"}], context={})
  except AdapterError as e:
    assert "must not be filesystem root" in str(e)
  else:
    raise AssertionError("expected AdapterError when AINL_AGENT_ROOT is filesystem root")

