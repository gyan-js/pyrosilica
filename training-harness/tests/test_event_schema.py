
from __future__ import annotations

import json

from event_schema import SCHEMA_VERSION, EventType, TrainingEvent


def test_to_dict_serializes_enum_as_string_value():
    event = TrainingEvent(type=EventType.STEP_START, node_id=None, step=0, epoch=0)
    d = event.to_dict()
    assert d["type"] == "step_start"
    assert isinstance(d["type"], str)


def test_to_dict_includes_schema_version_and_stream():
    event = TrainingEvent(type=EventType.RUN_START, node_id=None, step=0, epoch=0)
    d = event.to_dict()
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["stream"] == "training"


def test_default_meta_is_not_shared_between_instances():
    e1 = TrainingEvent(type=EventType.STEP_START, node_id=None, step=0, epoch=0)
    e2 = TrainingEvent(type=EventType.STEP_START, node_id=None, step=1, epoch=0)

    e1.meta["foo"] = "bar"
    assert "foo" not in e2.meta
    assert e1.meta is not e2.meta


def test_to_dict_is_json_serializable_for_every_event_type():
    for event_type in EventType:
        event = TrainingEvent(
            type=event_type,
            node_id="some/node",
            step=1,
            epoch=0,
            meta={"loss": 0.5, "input_shape": [1, 2, 3]},
        )
        serialized = json.dumps(event.to_dict())
        restored = json.loads(serialized)
        assert restored["type"] == event_type.value


def test_node_id_defaults_none_for_run_level_events():
    event = TrainingEvent(type=EventType.RUN_START, node_id=None, step=0, epoch=0)
    assert event.to_dict()["node_id"] is None