from __future__ import annotations

from typing import Callable, Optional

import torch
import torch.nn as nn

from event_schema import EventType, TrainingEvent

EmitFn = Callable[[TrainingEvent], None]


def _shape_of(x) -> Optional[list[int]]:
    if isinstance(x, torch.Tensor):
        return list(x.shape)
    if isinstance(x, (tuple, list)) and x and isinstance(x[0], torch.Tensor):
        return list(x[0].shape)
    return None


class HookManager:

    def __init__(self, model: nn.Module, node_ids: dict[str, str], emit: EmitFn):
      
        self.model = model
        self.node_ids = node_ids
        self.emit = emit
        self._handles: list[torch.utils.hooks.RemovableHandle] = []
        self._step = 0
        self._epoch = 0

    def set_progress(self, step: int, epoch: int) -> None:
        self._step = step
        self._epoch = epoch

    def register(self) -> None:
        has_backward_pre_hook = hasattr(nn.Module, "register_full_backward_pre_hook")

        for qualified_name, module in self.model.named_modules():
            if qualified_name == "" or qualified_name not in self.node_ids:
                continue
            node_id = self.node_ids[qualified_name]

            self._handles.append(module.register_forward_pre_hook(self._make_forward_pre(node_id)))
            self._handles.append(module.register_forward_hook(self._make_forward_post(node_id)))

            if any(p.requires_grad for p in module.parameters(recurse=False)):
                if has_backward_pre_hook:
                    self._handles.append(
                        module.register_full_backward_pre_hook(self._make_backward_pre(node_id))
                    )
                self._handles.append(module.register_full_backward_hook(self._make_backward_post(node_id)))

    def unregister(self) -> None:
        for h in self._handles:
            h.remove()
        self._handles.clear()

  

    def _make_forward_pre(self, node_id: str):
        def _hook(module, inputs):
            self.emit(TrainingEvent(
                type=EventType.LAYER_FORWARD_START, node_id=node_id,
                step=self._step, epoch=self._epoch,
                meta={"input_shape": _shape_of(inputs)},
            ))
        return _hook

    def _make_forward_post(self, node_id: str):
        def _hook(module, inputs, output):
            self.emit(TrainingEvent(
                type=EventType.LAYER_FORWARD_END, node_id=node_id,
                step=self._step, epoch=self._epoch,
                meta={"output_shape": _shape_of(output)},
            ))
        return _hook

    def _make_backward_pre(self, node_id: str):
        def _hook(module, grad_output):
            self.emit(TrainingEvent(
                type=EventType.LAYER_BACKWARD_START, node_id=node_id,
                step=self._step, epoch=self._epoch,
                meta={"grad_output_shape": _shape_of(grad_output)},
            ))
        return _hook

    def _make_backward_post(self, node_id: str):
        def _hook(module, grad_input, grad_output):
            self.emit(TrainingEvent(
                type=EventType.LAYER_BACKWARD_END, node_id=node_id,
                step=self._step, epoch=self._epoch,
                meta={"grad_output_shape": _shape_of(grad_output)},
            ))
        return _hook


def register_hooks(model: nn.Module, node_ids: dict[str, str], emit: EmitFn) -> HookManager:
    mgr = HookManager(model, node_ids, emit)
    mgr.register()
    return mgr