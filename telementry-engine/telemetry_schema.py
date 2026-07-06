# IMPORTANT: all comments in this file are AI-generated and may not reflect the original author's intent. Please verify before using in production.




"""
telemetry_schema.py

Single source of truth for the JSON shape sent over the wire to the
frontend (stream-server -> Three.js visualizer).

Every other module in telemetry-engine/ constructs or consumes these
dataclasses instead of raw dicts, so the wire format can't silently drift
between nvml_poller, kernel_tracer, memory_tracker, and ws_publisher.

IMPORTANT: if you change a field name or shape here, mirror the change in
shared-schemas/telemetry-types.js on the frontend side, or the JS side will
silently deserialize into undefined fields instead of failing loudly.

SCHEMA_VERSION exists specifically so the frontend can detect a mismatch
and warn instead of rendering garbage.
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Tuple, Any

SCHEMA_VERSION = "1.0.0"


def now_ms() -> float:
    """Monotonic-ish wall clock timestamp in milliseconds, used for all frames."""
    return time.time() * 1000.0


# ---------------------------------------------------------------------------
# SM / device state — produced by nvml_poller.py
# ---------------------------------------------------------------------------
@dataclass
class SMState:
    timestamp_ms: float
    gpu_index: int
    sm_utilization_pct: float          # 0-100
    memory_used_mb: float
    memory_total_mb: float
    power_draw_w: Optional[float]      # None if unsupported on this card
    power_limit_w: Optional[float]
    temperature_c: Optional[float]
    clock_sm_mhz: Optional[float]
    clock_mem_mhz: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Kernel launch events — produced by kernel_tracer.py (real CUPTI or fallback)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Per-process memory — produced by memory_tracker.py
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Training-loop metrics — optional, forwarded from the training harness
# (e.g. event_hooks.py) if/when that side of the system exists.
# ---------------------------------------------------------------------------
@dataclass
class TrainingMetrics:
    step: Optional[int] = None
    loss: Optional[float] = None
    throughput_samples_per_sec: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# The unit actually sent over the wire.
# ---------------------------------------------------------------------------
@dataclass
class TelemetryFrame:
    frame_id: int
    schema_version: str
    tick_rate_hz: float
    sm_state: Optional[SMState]
    kernel_events: List[KernelEvent] = field(default_factory=list)
    memory_snapshot: Optional[MemorySnapshot] = None
    training_metrics: Optional[TrainingMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "schema_version": self.schema_version,
            "tick_rate_hz": self.tick_rate_hz,
            "sm_state": self.sm_state.to_dict() if self.sm_state else None,
            "kernel_events": [k.to_dict() for k in self.kernel_events],
            "memory_snapshot": self.memory_snapshot.to_dict() if self.memory_snapshot else None,
            "training_metrics": self.training_metrics.to_dict() if self.training_metrics else None,
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

    