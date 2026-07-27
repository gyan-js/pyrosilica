from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Tuple, Any

SCHEMA_VERSION = "1.0.0"


def now_ms() -> float:
   
    return time.time() * 1000.0



@dataclass
class SMState:
    timestamp_ms: float
    gpu_index: int
    sm_utilization_pct: float          
    memory_used_mb: float
    memory_total_mb: float
    power_draw_w: Optional[float]      
    power_limit_w: Optional[float]
    temperature_c: Optional[float]
    clock_sm_mhz: Optional[float]
    clock_mem_mhz: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



@dataclass
class KernelEvent:
    name: str
    start_ts_ms: float
    duration_ms: float
    grid_dim: Tuple[int, int, int]
    block_dim: Tuple[int, int, int]
    source: str                        # "cupti" | "sampled"
    stream_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["grid_dim"] = list(self.grid_dim)
        d["block_dim"] = list(self.block_dim)
        return d



@dataclass
class LayerMemoryDelta:
    layer_name: str
    delta_mb: float
    timestamp_ms: float


@dataclass
class MemorySnapshot:
    timestamp_ms: float
    pid: int
    process_memory_mb: float
    per_layer_deltas: List[LayerMemoryDelta] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "pid": self.pid,
            "process_memory_mb": self.process_memory_mb,
            "per_layer_deltas": [asdict(d) for d in self.per_layer_deltas],
        }



@dataclass
class TrainingMetrics:
    step: Optional[int] = None
    loss: Optional[float] = None
    throughput_samples_per_sec: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



@dataclass
class TelemetryFrame:
    frame_id: int
    schema_version: str
    tick_rate_hz: float
    sm_state: Optional[SMState]
    kernel_events: List[KernelEvent] = field(default_factory=list)
    memory_snapshot: Optional[MemorySnapshot] = None
    training_metrics: Optional[TrainingMetrics] = None
    stream: str = "telemetry"  
   
    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "schema_version": self.schema_version,
            "tick_rate_hz": self.tick_rate_hz,
            "sm_state": self.sm_state.to_dict() if self.sm_state else None,
            "kernel_events": [k.to_dict() for k in self.kernel_events],
            "memory_snapshot": self.memory_snapshot.to_dict() if self.memory_snapshot else None,
            "training_metrics": self.training_metrics.to_dict() if self.training_metrics else None,
            "stream": self.stream,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def new_frame(
    frame_id: int,
    tick_rate_hz: float,
    sm_state: Optional[SMState],
    kernel_events: Optional[List[KernelEvent]] = None,
    memory_snapshot: Optional[MemorySnapshot] = None,
    training_metrics: Optional[TrainingMetrics] = None,
) -> TelemetryFrame:
    return TelemetryFrame(
        frame_id=frame_id,
        schema_version=SCHEMA_VERSION,
        tick_rate_hz=tick_rate_hz,
        sm_state=sm_state,
        kernel_events=kernel_events or [],
        memory_snapshot=memory_snapshot,
        training_metrics=training_metrics,
    )