from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_main(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "main.py"), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=REPO_ROOT,
    )


def test_record_mode_produces_valid_jsonl(tmp_path):
    record_path = tmp_path / "events.jsonl"
    result = _run_main(
        "--model", "mnist_mlp", "--device", "cpu",
        "--epochs", "1", "--max-steps", "3",
        "--output-mode", "record", "--record-path", str(record_path),
    )
    assert result.returncode == 0, result.stderr

    lines = record_path.read_text().strip().splitlines()
    assert lines, "expected at least one recorded event"
    for line in lines:
        json.loads(line)  # raises if malformed


def test_dump_graph_produces_valid_json_matching_schema(tmp_path):
    graph_path = tmp_path / "graph.json"
    result = _run_main(
        "--model", "mnist_mlp", "--device", "cpu",
        "--epochs", "1", "--max-steps", "1",
        "--output-mode", "record", "--record-path", str(tmp_path / "events.jsonl"),
        "--dump-graph", str(graph_path),
    )
    assert result.returncode == 0, result.stderr

    graph = json.loads(graph_path.read_text())
    assert graph["schema_version"] == "1.0.0"
    assert graph["strategy"] in ("torch.fx", "module_hooks")
    assert "root" in graph["nodes"]


def test_bad_model_path_exits_cleanly_without_traceback():
    result = _run_main("--model", "/tmp/definitely_does_not_exist.py", "--device", "cpu")
    assert result.returncode == 1
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    assert "[main] failed to load model" in result.stderr


def test_max_steps_limits_recorded_step_events(tmp_path):
    record_path = tmp_path / "events.jsonl"
    _run_main(
        "--model", "mnist_mlp", "--device", "cpu",
        "--epochs", "5", "--max-steps", "2",
        "--output-mode", "record", "--record-path", str(record_path),
    )
    events = [json.loads(l) for l in record_path.read_text().strip().splitlines()]
    step_starts = [e for e in events if e["type"] == "step_start"]
    assert len(step_starts) == 2


def test_graph_and_event_node_ids_are_aligned_end_to_end(tmp_path):
    
    record_path = tmp_path / "events.jsonl"
    graph_path = tmp_path / "graph.json"
    result = _run_main(
        "--model", "mnist_mlp", "--device", "cpu",
        "--epochs", "1", "--max-steps", "3",
        "--output-mode", "record", "--record-path", str(record_path),
        "--dump-graph", str(graph_path),
    )
    assert result.returncode == 0, result.stderr

    graph = json.loads(graph_path.read_text())
    graph_ids = set(graph["nodes"].keys())
    events = [json.loads(l) for l in record_path.read_text().strip().splitlines()]
    event_ids = {e["node_id"] for e in events if e.get("node_id")}

    missing = event_ids - graph_ids
    assert not missing, f"event node_ids missing from the graph: {missing}"