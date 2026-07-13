from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

SCHEMA_VERSION = "1.0.0"


class EventType(str, Enum):
    LAYER_FORWARD_START = "layer_forward_start"
    LAYER_FORWARD_END = "layer_forward_end"
    LAYER_BACKWARD_START = "layer_backward_start"
    LAYER_BACKWARD_END = "layer_backward_end"
    OPTIMIZER_STEP = "optimizer_step"
    STEP_START = "step_start"
    STEP_END = "step_end"
    EPOCH_START = "epoch_start"
    EPOCH_END = "epoch_end"
    RUN_START = "run_start"
    RUN_END = "run_end"


@dataclass
class TrainingEvent:
    type: EventType
    node_id: Optional[str]
    step: int
    epoch: int
    timestamp: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    stream: str = "training" 

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d