

from __future__ import annotations

import math

import pytest
import torch.nn as nn
import torch.optim as optim

from event_schema import EventType
from graph_extractor import build_module_id_map
from training_loop import run_training


def _hooks_remaining(model):
    return sum(
        len(m._forward_hooks) + len(m._forward_pre_hooks) + len(m._backward_hooks)
        for m in model.modules()
    )


def test_full_run_emits_events_in_correct_order(tiny_mlp, tiny_mlp_dataloader):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []

    run_training(
        model=tiny_mlp,
        dataloader=tiny_mlp_dataloader,
        optimizer=optim.Adam(tiny_mlp.parameters()),
        loss_fn=nn.CrossEntropyLoss(),
        node_ids=node_ids,
        emit=emitted.append,
        device="cpu",
        epochs=1,
    )

    types = [e.type for e in emitted]
    assert types[0] == EventType.RUN_START
    assert types[1] == EventType.EPOCH_START
    assert types[-1] == EventType.RUN_END
    assert types[-2] == EventType.EPOCH_END

    step_starts = [i for i, t in enumerate(types) if t == EventType.STEP_START]
    step_ends = [i for i, t in enumerate(types) if t == EventType.STEP_END]
    optimizer_steps = [i for i, t in enumerate(types) if t == EventType.OPTIMIZER_STEP]

    assert len(step_starts) == len(step_ends) == len(optimizer_steps) == 4  # 16 samples / batch_size 4
    for start, opt_step, end in zip(step_starts, optimizer_steps, step_ends):
        assert start < opt_step < end


def test_max_steps_truncates_the_run(tiny_mlp, tiny_mlp_dataloader):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []

    run_training(
        model=tiny_mlp,
        dataloader=tiny_mlp_dataloader,
        optimizer=optim.Adam(tiny_mlp.parameters()),
        loss_fn=nn.CrossEntropyLoss(),
        node_ids=node_ids,
        emit=emitted.append,
        device="cpu",
        epochs=1,
        max_steps=2,
    )

    step_starts = [e for e in emitted if e.type == EventType.STEP_START]
    assert len(step_starts) == 2


def test_hooks_are_unregistered_after_a_clean_run(tiny_mlp, tiny_mlp_dataloader):
    node_ids = build_module_id_map(tiny_mlp)

    run_training(
        model=tiny_mlp,
        dataloader=tiny_mlp_dataloader,
        optimizer=optim.Adam(tiny_mlp.parameters()),
        loss_fn=nn.CrossEntropyLoss(),
        node_ids=node_ids,
        emit=lambda e: None,
        device="cpu",
        epochs=1,
    )

    assert _hooks_remaining(tiny_mlp) == 0


def test_hooks_are_unregistered_even_when_loss_fn_raises(tiny_mlp, tiny_mlp_dataloader):
    node_ids = build_module_id_map(tiny_mlp)

    def _bad_loss(pred, target):
        raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        run_training(
            model=tiny_mlp,
            dataloader=tiny_mlp_dataloader,
            optimizer=optim.Adam(tiny_mlp.parameters()),
            loss_fn=_bad_loss,
            node_ids=node_ids,
            emit=lambda e: None,
            device="cpu",
            epochs=1,
        )

    assert _hooks_remaining(tiny_mlp) == 0


def test_optimizer_step_meta_loss_is_finite(tiny_mlp, tiny_mlp_dataloader):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []

    run_training(
        model=tiny_mlp,
        dataloader=tiny_mlp_dataloader,
        optimizer=optim.Adam(tiny_mlp.parameters()),
        loss_fn=nn.CrossEntropyLoss(),
        node_ids=node_ids,
        emit=emitted.append,
        device="cpu",
        epochs=1,
    )

    optimizer_steps = [e for e in emitted if e.type == EventType.OPTIMIZER_STEP]
    assert optimizer_steps, "expected at least one OPTIMIZER_STEP event"
    for e in optimizer_steps:
        assert isinstance(e.meta["loss"], float)
        assert math.isfinite(e.meta["loss"])


def test_layer_events_appear_between_step_start_and_optimizer_step(tiny_mlp, tiny_mlp_dataloader):
    node_ids = build_module_id_map(tiny_mlp)
    emitted = []

    run_training(
        model=tiny_mlp,
        dataloader=tiny_mlp_dataloader,
        optimizer=optim.Adam(tiny_mlp.parameters()),
        loss_fn=nn.CrossEntropyLoss(),
        node_ids=node_ids,
        emit=emitted.append,
        device="cpu",
        epochs=1,
        max_steps=1,
    )

    types = [e.type for e in emitted]
    step_start_idx = types.index(EventType.STEP_START)
    optimizer_step_idx = types.index(EventType.OPTIMIZER_STEP)

    layer_event_types = {EventType.LAYER_FORWARD_START, EventType.LAYER_FORWARD_END, EventType.LAYER_BACKWARD_END}
    layer_event_indices = [i for i, t in enumerate(types) if t in layer_event_types]

    assert layer_event_indices, "expected per-layer events during the step"
    assert all(step_start_idx < i < optimizer_step_idx for i in layer_event_indices)



    