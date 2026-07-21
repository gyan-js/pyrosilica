from __future__ import annotations

import torch

from event_hooks import register_hooks
from event_schema import EventType
from graph_extractor import build_module_id_map


def _run_forward_backward(model, node_ids, emitted):
    hooks = register_hooks(model, node_ids, emitted.append)
    x = torch.randn(2, 4, requires_grad=False)
    out = model(x)
    loss = out.sum()
    loss.backward()
    return hooks


def test_forward_events_fire_for_every_hookable_module(tiny_mlp):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []
    _run_forward_backward(tiny_mlp, node_ids, emitted)

    forward_starts = {e.node_id for e in emitted if e.type == EventType.LAYER_FORWARD_START}
    forward_ends = {e.node_id for e in emitted if e.type == EventType.LAYER_FORWARD_END}

    assert forward_starts == set(node_ids.values())
    assert forward_ends == set(node_ids.values())


def test_forward_start_precedes_forward_end_per_node(tiny_mlp):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []
    _run_forward_backward(tiny_mlp, node_ids, emitted)

    seen_start = set()
    for e in emitted:
        if e.type == EventType.LAYER_FORWARD_START:
            seen_start.add(e.node_id)
        elif e.type == EventType.LAYER_FORWARD_END:
            assert e.node_id in seen_start, f"forward_end for {e.node_id} fired before its forward_start"


def test_backward_events_only_fire_for_modules_with_trainable_params(tiny_mlp):
   
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []
    _run_forward_backward(tiny_mlp, node_ids, emitted)

    backward_node_ids = {e.node_id for e in emitted if e.type == EventType.LAYER_BACKWARD_END}

    relu_id = node_ids["net.1"]
    linear1_id = node_ids["net.0"]
    linear2_id = node_ids["net.2"]

    assert relu_id not in backward_node_ids
    assert linear1_id in backward_node_ids
    assert linear2_id in backward_node_ids


def test_set_progress_updates_step_and_epoch_on_subsequent_events(tiny_mlp):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []
    hooks = register_hooks(tiny_mlp, node_ids, emitted.append)

    x = torch.randn(2, 4)
    tiny_mlp(x)  
    

    hooks.set_progress(step=5, epoch=2)
    tiny_mlp(x)

    steps_seen = {e.step for e in emitted}
    epochs_seen = {e.epoch for e in emitted}
    assert steps_seen == {0, 5}
    assert epochs_seen == {0, 2}


def test_unregister_removes_all_hooks(tiny_mlp):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []
    hooks = register_hooks(tiny_mlp, node_ids, emitted.append)

    hooks.unregister()

    for module in tiny_mlp.modules():
        assert len(module._forward_hooks) == 0
        assert len(module._forward_pre_hooks) == 0
        assert len(module._backward_hooks) == 0

    emitted.clear()
    x = torch.randn(2, 4)
    tiny_mlp(x)
    assert emitted == [], "no events should fire after unregister()"


def test_meta_shapes_are_captured(tiny_mlp):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []
    _run_forward_backward(tiny_mlp, node_ids, emitted)

    forward_start = next(e for e in emitted if e.type == EventType.LAYER_FORWARD_START)
    assert forward_start.meta["input_shape"] is not None
    assert isinstance(forward_start.meta["input_shape"], list)