# IMPORTANT: all comments in this file are AI-generated for better understanding of the code, and "may" not reflect the original author's intent.

"""
memory_tracker.py

Filters NVML's per-process memory stats down to just the training run's
own PID, so the visualization isn't polluted by unrelated GPU processes
(a browser using the GPU, other users on a shared box, etc.).

Also maintains a rolling per-layer memory delta timeline by combining
that PID-filtered VRAM number with layer-boundary events forwarded from
the training harness's event_hooks.py (not part of this package - this
module just exposes the ingestion point `record_layer_event` for it to
call, over whatever IPC main.py's deployment wires up: same-process
callback, a local socket, etc.)
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Deque, List, Optional

from telemetry_schema import LayerMemoryDelta, MemorySnapshot, now_ms

logger = logging.getLogger("telemetry_engine.memory_tracker")

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:  # pragma: no cover
    pynvml = None
    NVML_AVAILABLE = False


class MemoryTracker:
    """
    Usage:
        tracker = MemoryTracker(pid=os.getpid(), nvml_handle=poller_handle)
        snapshot = tracker.poll()

        # called from wherever the training harness's event_hooks.py
        # forwards layer boundaries into this process:
        tracker.record_layer_event("transformer.layer.12.mlp", delta_mb=42.3)
    """

    def __init__(self, pid: int, nvml_handle, layer_history_size: int = 512):
        self.pid = pid
        self._handle = nvml_handle
        self._layer_events: Deque[LayerMemoryDelta] = deque(maxlen=layer_history_size)
        self._lock = threading.Lock()  # record_layer_event may be called from another thread

    def poll(self) -> MemorySnapshot:
        """Snapshots this PID's current VRAM footprint plus any layer
        deltas recorded since the last snapshot was consumed by main.py."""
        process_memory_mb = self._get_process_memory_mb()

        with self._lock:
            pending = list(self._layer_events)
            self._layer_events.clear()

        return MemorySnapshot(
            timestamp_ms=now_ms(),
            pid=self.pid,
            process_memory_mb=process_memory_mb,
            per_layer_deltas=pending,
        )

    def record_layer_event(self, layer_name: str, delta_mb: float) -> None:
        """Ingestion point for the training harness's event_hooks.py.
        Thread-safe: safe to call from a different thread/process bridge
        than the one running poll()."""
        with self._lock:
            self._layer_events.append(
                LayerMemoryDelta(
                    layer_name=layer_name,
                    delta_mb=delta_mb,
                    timestamp_ms=now_ms(),
                )
            )

    def _get_process_memory_mb(self) -> float:
        if not NVML_AVAILABLE or self._handle is None:
            return 0.0
        try:
            procs = pynvml.nvmlDeviceGetComputeRunningProcesses(self._handle)
        except pynvml.NVMLError as e:
            logger.debug("nvmlDeviceGetComputeRunningProcesses failed: %s", e)
            return 0.0

        for p in procs:
            if p.pid == self.pid:
                used = getattr(p, "usedGpuMemory", None)
                if used is None or used == pynvml.NVML_VALUE_NOT_AVAILABLE:
                    return 0.0
                return used / (1024 * 1024)

        # Training PID isn't (yet) showing up as a GPU process - normal
        # during early startup before the CUDA context is created.
        return 0.0