

from __future__ import annotations

import asyncio
import json

import pytest

from event_schema import EventType, TrainingEvent
from run_recorder import RunRecorder


def test_record_training_event_writes_tagged_line_with_seq(tmp_path):
    recorder = RunRecorder(tmp_path / "events.jsonl")
    recorder.record_training_event(TrainingEvent(type=EventType.STEP_START, node_id=None, step=0, epoch=0))
    recorder.record_training_event(TrainingEvent(type=EventType.STEP_END, node_id=None, step=0, epoch=0))
    asyncio.run(recorder.stop())

    lines = (tmp_path / "events.jsonl").read_text().strip().splitlines()
    records = [json.loads(l) for l in lines]

    assert [r["seq"] for r in records] == [0, 1]
    assert all(r["stream"] == "training" for r in records)


def test_record_telemetry_frame_tags_stream_and_received_at(tmp_path):
    recorder = RunRecorder(tmp_path / "events.jsonl")
    recorder.record_telemetry_frame({"gpu_util": 87})
    asyncio.run(recorder.stop())

    record = json.loads((tmp_path / "events.jsonl").read_text().strip())
    assert record["stream"] == "telemetry"
    assert record["frame"] == {"gpu_util": 87}
    assert "received_at" in record


def test_seq_is_shared_and_monotonic_across_both_stream_types(tmp_path):
    recorder = RunRecorder(tmp_path / "events.jsonl")
    recorder.record_training_event(TrainingEvent(type=EventType.STEP_START, node_id=None, step=0, epoch=0))
    recorder.record_telemetry_frame({"gpu_util": 50})
    recorder.record_training_event(TrainingEvent(type=EventType.STEP_END, node_id=None, step=0, epoch=0))
    asyncio.run(recorder.stop())

    lines = (tmp_path / "events.jsonl").read_text().strip().splitlines()
    records = [json.loads(l) for l in lines]
    assert [r["seq"] for r in records] == [0, 1, 2]
    assert [r["stream"] for r in records] == ["training", "telemetry", "training"]


def test_stop_closes_file_handle(tmp_path):
    recorder = RunRecorder(tmp_path / "events.jsonl")
    recorder.record_training_event(TrainingEvent(type=EventType.RUN_START, node_id=None, step=0, epoch=0))
    asyncio.run(recorder.stop())
    assert recorder._fh.closed


def test_output_directory_is_created_if_missing(tmp_path):
    nested_path = tmp_path / "nested" / "dir" / "events.jsonl"
    recorder = RunRecorder(nested_path)
    asyncio.run(recorder.stop())
    assert nested_path.exists()


@pytest.mark.asyncio
async def test_attach_telemetry_records_frames_and_skips_malformed_json(tmp_path):
    """using a fake websocket connection instead of a real server, so this
    doesn't depend on network or a running stream-server..."""
    import run_recorder as run_recorder_module

    class FakeWebSocket:
        def __init__(self, incoming):
            self._incoming = list(incoming)
            self.sent = []

        async def send(self, msg):
            self.sent.append(msg)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._incoming:
                raise StopAsyncIteration
            return self._incoming.pop(0)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    fake_ws = FakeWebSocket(
        [
            json.dumps({"gpu_util": 10}),
            "not valid json {{{",
            json.dumps({"gpu_util": 20}),
        ]
    )

    def fake_connect(url):
        return fake_ws

    run_recorder_module.websockets.connect = fake_connect  

    recorder = RunRecorder(tmp_path / "events.jsonl")
    await recorder.attach_telemetry("ws://fake")
    await asyncio.sleep(0.05)  
    await recorder.stop()

    lines = (tmp_path / "events.jsonl").read_text().strip().splitlines()
    records = [json.loads(l) for l in lines]

    assert len(records) == 2, "malformed JSON line should have been skipped, not recorded or crashed on"
    assert [r["frame"]["gpu_util"] for r in records] == [10, 20]