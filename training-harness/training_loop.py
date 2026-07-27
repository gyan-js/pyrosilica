from __future__ import annotations

from typing import Callable, Iterable, Optional

import torch
import torch.nn as nn

from event_hooks import HookManager, register_hooks
from event_schema import EventType, TrainingEvent

EmitFn = Callable[[TrainingEvent], None]
LossFn = Callable[[torch.Tensor, torch.Tensor], torch.Tensor]


def run_training(
    model: nn.Module,
    dataloader: Iterable,
    optimizer: torch.optim.Optimizer,
    loss_fn: LossFn,
    node_ids: dict[str, str],
    emit: EmitFn,
    device: str = "cuda",
    epochs: int = 1,
    max_steps: Optional[int] = None,
) -> None:
    hooks: HookManager = register_hooks(model, node_ids, emit)
    global_step = 0

    try:
        emit(TrainingEvent(type=EventType.RUN_START, node_id=None, step=0, epoch=0))

        for epoch in range(epochs):
            emit(TrainingEvent(type=EventType.EPOCH_START, node_id=None, step=global_step, epoch=epoch))

            for batch_inputs, batch_targets in dataloader:
                if max_steps is not None and global_step >= max_steps:
                    break

                hooks.set_progress(global_step, epoch)
                batch_inputs = batch_inputs.to(device)
                batch_targets = batch_targets.to(device)

                emit(TrainingEvent(type=EventType.STEP_START, node_id=None, step=global_step, epoch=epoch))

                optimizer.zero_grad(set_to_none=True)

              
                predictions = model(batch_inputs)
                loss = loss_fn(predictions, batch_targets)
                loss.backward()

                optimizer.step()
                emit(TrainingEvent(
                    type=EventType.OPTIMIZER_STEP, node_id=None,
                    step=global_step, epoch=epoch,
                    meta={"loss": float(loss.detach().item())},
                ))

                emit(TrainingEvent(type=EventType.STEP_END, node_id=None, step=global_step, epoch=epoch))
                global_step += 1

            emit(TrainingEvent(type=EventType.EPOCH_END, node_id=None, step=global_step, epoch=epoch))

            if max_steps is not None and global_step >= max_steps:
                break

        emit(TrainingEvent(type=EventType.RUN_END, node_id=None, step=global_step, epoch=epochs - 1))

    finally:
        hooks.unregister()